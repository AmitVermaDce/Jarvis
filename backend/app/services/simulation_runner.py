"""
OASIS simulation run
 in after runsimulation record eachAgent dynamic , support actual time statusmonitor
"""

import os
import sys
import json
import time
import asyncio
import threading
import subprocess
import signal
import atexit
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_locale, set_locale
from .zep_graph_memory_updater import ZepGraphMemoryManager
from .simulation_ipc import SimulationIPCClient, CommandType, IPCResponse

logger = get_logger('jarvis.simulation_runner')

# mark is else already registeredcleanupfunction
_cleanup_registered = False

#
IS_WINDOWS = sys.platform == 'win32'


class RunnerStatus(str, Enum):
    """runstatus"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Agent dynamic record """
    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class RoundSummary:
    """ each roundsummary"""
    round_num: int
    start_time: str
    end_time: Optional[str] = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: List[int] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """simulation runstatus( actual time )"""
    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE
    
    # progressinfo
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0
    
    # each independentround and simulation time space ( at dual paralleldisplay)
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0
    
    # status
    twitter_running: bool = False
    reddit_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0
    
    # completestatus( through past actions.jsonl in simulation_end event)
    twitter_completed: bool = False
    reddit_completed: bool = False
    
    # each roundsummary
    rounds: List[RoundSummary] = field(default_factory=list)
    
    # most near dynamic ( at frontend actual time )
    recent_actions: List[AgentAction] = field(default_factory=list)
    max_recent_actions: int = 50
    
    # time space
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    # errorinfo
    error: Optional[str] = None
    
    # processID( at stop)
    process_pid: Optional[int] = None
    
    def add_action(self, action: AgentAction):
        """add dynamic to most near dynamic list"""
        self.recent_actions.insert(0, action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[:self.max_recent_actions]
        
        if action.platform == "twitter":
            self.twitter_actions_count += 1
        else:
            self.reddit_actions_count += 1
        
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(self.current_round / max(self.total_rounds, 1) * 100, 1),
            # each independentround and time space
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "total_actions_count": self.twitter_actions_count + self.reddit_actions_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
        }
    
    def to_detail_dict(self) -> Dict[str, Any]:
        """contain most near dynamic detailedinfo"""
        result = self.to_dict()
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result


class SimulationRunner:
    """
    simulation run
    
    :
    1. in after process in runOASIS simulation
    2. parserunlog, record eachAgent dynamic
    3. provide actual time statusqueryAPI
    4. supportpause/stop/resume
    """
    
    # runstatusstoragedirectory
    RUN_STATE_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/simulations'
    )
    
    # directory
    SCRIPTS_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../scripts'
    )
    
    # within exist in runstatus
    _run_states: Dict[str, SimulationRunState] = {}
    _processes: Dict[str, subprocess.Popen] = {}
    _action_queues: Dict[str, Queue] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _stdout_files: Dict[str, Any] = {} # storage stdout file sentence
    _stderr_files: Dict[str, Any] = {} # storage stderr file sentence
    
    # graphmemoryupdateconfiguration
    _graph_memory_enabled: Dict[str, bool] = {}  # simulation_id -> enabled
    
    @classmethod
    def get_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """ fetch runstatus"""
        if simulation_id in cls._run_states:
            return cls._run_states[simulation_id]
        
        # test from fileload
        state = cls._load_run_state(simulation_id)
        if state:
            cls._run_states[simulation_id] = state
        return state
    
    @classmethod
    def _load_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """ from fileloadrunstatus"""
        state_file = os.path.join(cls.RUN_STATE_DIR, simulation_id, "run_state.json")
        if not os.path.exists(state_file):
            return None
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = SimulationRunState(
                simulation_id=simulation_id,
                runner_status=RunnerStatus(data.get("runner_status", "idle")),
                current_round=data.get("current_round", 0),
                total_rounds=data.get("total_rounds", 0),
                simulated_hours=data.get("simulated_hours", 0),
                total_simulation_hours=data.get("total_simulation_hours", 0),
                # each independentround and time space
                twitter_current_round=data.get("twitter_current_round", 0),
                reddit_current_round=data.get("reddit_current_round", 0),
                twitter_simulated_hours=data.get("twitter_simulated_hours", 0),
                reddit_simulated_hours=data.get("reddit_simulated_hours", 0),
                twitter_running=data.get("twitter_running", False),
                reddit_running=data.get("reddit_running", False),
                twitter_completed=data.get("twitter_completed", False),
                reddit_completed=data.get("reddit_completed", False),
                twitter_actions_count=data.get("twitter_actions_count", 0),
                reddit_actions_count=data.get("reddit_actions_count", 0),
                started_at=data.get("started_at"),
                updated_at=data.get("updated_at", datetime.now().isoformat()),
                completed_at=data.get("completed_at"),
                error=data.get("error"),
                process_pid=data.get("process_pid"),
            )
            
            # load most near dynamic
            actions_data = data.get("recent_actions", [])
            for a in actions_data:
                state.recent_actions.append(AgentAction(
                    round_num=a.get("round_num", 0),
                    timestamp=a.get("timestamp", ""),
                    platform=a.get("platform", ""),
                    agent_id=a.get("agent_id", 0),
                    agent_name=a.get("agent_name", ""),
                    action_type=a.get("action_type", ""),
                    action_args=a.get("action_args", {}),
                    result=a.get("result"),
                    success=a.get("success", True),
                ))
            
            return state
        except Exception as e:
            logger.error(f"loadrunstatusfailed: {str(e)}")
            return None
    
    @classmethod
    def _save_run_state(cls, state: SimulationRunState):
        """saverunstatus to file"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        state_file = os.path.join(sim_dir, "run_state.json")
        
        data = state.to_detail_dict()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        cls._run_states[state.simulation_id] = state
    
    @classmethod
    def start_simulation(
        cls,
        simulation_id: str,
        platform: str = "parallel",  # twitter / reddit / parallel
        max_rounds: int = None, # maximum simulationround number (optional, at truncate past long simulation)
        enable_graph_memory_update: bool = False, # is else will dynamic update to Zepgraph
        graph_id: str = None # ZepgraphID(enablegraphupdate time required)
    ) -> SimulationRunState:
        """
        startsimulation
        
        Args:
            simulation_id: simulationID
            platform: run (twitter/reddit/parallel)
            max_rounds: maximum simulationround number (optional, at truncate past long simulation)
            enable_graph_memory_update: is else will Agent dynamic dynamic update to Zepgraph
            graph_id: ZepgraphID(enablegraphupdate time required)
            
        Returns:
            SimulationRunState
        """
        # check is else already in run
        existing = cls.get_run_state(simulation_id)
        if existing and existing.runner_status in [RunnerStatus.RUNNING, RunnerStatus.STARTING]:
            raise ValueError(f"simulation already in run in : {simulation_id}")
        
        # loadsimulation configuration
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            raise ValueError(f"simulation configuration not exist in , please call /prepare API")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # initializerunstatus
        time_config = config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = int(total_hours * 60 / minutes_per_round)
        
        # if point fixed maximum round number , then truncate
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                logger.info(f"round number already truncate: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")
        
        state = SimulationRunState(
            simulation_id=simulation_id,
            runner_status=RunnerStatus.STARTING,
            total_rounds=total_rounds,
            total_simulation_hours=total_hours,
            started_at=datetime.now().isoformat(),
        )
        
        cls._save_run_state(state)
        
        # ifenablegraphmemoryupdate, createupdate
        if enable_graph_memory_update:
            if not graph_id:
                raise ValueError("enablegraphmemoryupdate time must provide graph_id")
            
            try:
                ZepGraphMemoryManager.create_updater(simulation_id, graph_id)
                cls._graph_memory_enabled[simulation_id] = True
                logger.info(f" already enablegraphmemoryupdate: simulation_id={simulation_id}, graph_id={graph_id}")
            except Exception as e:
                logger.error(f"creategraphmemoryupdatefailed: {e}")
                cls._graph_memory_enabled[simulation_id] = False
        else:
            cls._graph_memory_enabled[simulation_id] = False
        
        # correct fixed run ( at backend/scripts/ directory)
        if platform == "twitter":
            script_name = "run_twitter_simulation.py"
            state.twitter_running = True
        elif platform == "reddit":
            script_name = "run_reddit_simulation.py"
            state.reddit_running = True
        else:
            script_name = "run_parallel_simulation.py"
            state.twitter_running = True
            state.reddit_running = True
        
        script_path = os.path.join(cls.SCRIPTS_DIR, script_name)
        
        if not os.path.exists(script_path):
            raise ValueError(f" not exist in : {script_path}")
        
        # create dynamic queue
        action_queue = Queue()
        cls._action_queues[simulation_id] = action_queue
        
        # startsimulationprocess
        try:
            # structure run order , using completepath
            # new log structure :
            # twitter/actions.jsonl - Twitter dynamic log
            # reddit/actions.jsonl - Reddit dynamic log
            # simulation.log - main processlog
            
            cmd = [
                sys.executable, # Python parse
                script_path,
                "--config", config_path, # using completeconfigurationfilepath
            ]
            
            # if point fixed maximum round number , add to command lineparameter
            if max_rounds is not None and max_rounds > 0:
                cmd.extend(["--max-rounds", str(max_rounds)])
            
            # create main log files, avoid exempt stdout/stderr buffer full guide process
            main_log_path = os.path.join(sim_dir, "simulation.log")
            main_log_file = open(main_log_path, 'w', encoding='utf-8')
            
            # settingssubprocessenvironment variable, correctly protect Windows on using UTF-8 encoding
            # this can to repeat # three lib ( if OASIS) read fetch file time not point fixed encoding question topic
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1' # Python 3.7+ support, let all open() default using UTF-8
            env['PYTHONIOENCODING'] = 'utf-8' # correctly protect stdout/stderr using UTF-8
            
            # settingsdirectory as simulationdirectory(databasefile will generate in this )
            # using start_new_session=True create new process group , correctly protect can to through past os.killpg end stop allsubprocess
            process = subprocess.Popen(
                cmd,
                cwd=sim_dir,
                stdout=main_log_file,
                stderr=subprocess.STDOUT, # stderr also write enter same one file
                text=True,
                encoding='utf-8', # type point fixed encoding
                bufsize=1,
                env=env, # with has UTF-8 settingsenvironment variable
                start_new_session=True, # create new process group , correctly protect serviceclose time can end stop allrelatedprocess
            )
            
            # savefile sentence so that after continue close
            cls._stdout_files[simulation_id] = main_log_file
            cls._stderr_files[simulation_id] = None # no longer need to single stderr
            
            state.process_pid = process.pid
            state.runner_status = RunnerStatus.RUNNING
            cls._processes[simulation_id] = process
            cls._save_run_state(state)
            
            # Capture locale before spawning monitor thread
            current_locale = get_locale()

            # startmonitorthread
            monitor_thread = threading.Thread(
                target=cls._monitor_simulation,
                args=(simulation_id, current_locale),
                daemon=True
            )
            monitor_thread.start()
            cls._monitor_threads[simulation_id] = monitor_thread
            
            logger.info(f"simulationstartsuccess: {simulation_id}, pid={process.pid}, platform={platform}")
            
        except Exception as e:
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)
            raise
        
        return state
    
    @classmethod
    def _monitor_simulation(cls, simulation_id: str, locale: str = 'zh'):
        """monitorsimulationprocess, parse dynamic log"""
        set_locale(locale)
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        # new log structure : divide dynamic log
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        process = cls._processes.get(simulation_id)
        state = cls.get_run_state(simulation_id)
        
        if not process or not state:
            return
        
        twitter_position = 0
        reddit_position = 0
        
        try:
            while process.poll() is None: # process in run
                # read fetch Twitter dynamic log
                if os.path.exists(twitter_actions_log):
                    twitter_position = cls._read_action_log(
                        twitter_actions_log, twitter_position, state, "twitter"
                    )
                
                # read fetch Reddit dynamic log
                if os.path.exists(reddit_actions_log):
                    reddit_position = cls._read_action_log(
                        reddit_actions_log, reddit_position, state, "reddit"
                    )
                
                # updatestatus
                cls._save_run_state(state)
                time.sleep(2)
            
            # processend after , finally read fetch one times log
            if os.path.exists(twitter_actions_log):
                cls._read_action_log(twitter_actions_log, twitter_position, state, "twitter")
            if os.path.exists(reddit_actions_log):
                cls._read_action_log(reddit_actions_log, reddit_position, state, "reddit")
            
            # processend
            exit_code = process.returncode
            
            if exit_code == 0:
                state.runner_status = RunnerStatus.COMPLETED
                state.completed_at = datetime.now().isoformat()
                logger.info(f"simulationcomplete: {simulation_id}")
            else:
                state.runner_status = RunnerStatus.FAILED
                # from main log files read fetch errorinfo
                main_log_path = os.path.join(sim_dir, "simulation.log")
                error_info = ""
                try:
                    if os.path.exists(main_log_path):
                        with open(main_log_path, 'r', encoding='utf-8') as f:
                            error_info = f.read()[-2000:] # fetch finally2000character
                except Exception:
                    pass
                state.error = f"process exit code : {exit_code}, error: {error_info}"
                logger.error(f"simulationfailed: {simulation_id}, error={state.error}")
            
            state.twitter_running = False
            state.reddit_running = False
            cls._save_run_state(state)
            
        except Exception as e:
            logger.error(f"monitorthreadexception: {simulation_id}, error={str(e)}")
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)
        
        finally:
            # stopgraphmemoryupdate
            if cls._graph_memory_enabled.get(simulation_id, False):
                try:
                    ZepGraphMemoryManager.stop_updater(simulation_id)
                    logger.info(f" already stopgraphmemoryupdate: simulation_id={simulation_id}")
                except Exception as e:
                    logger.error(f"stopgraphmemoryupdatefailed: {e}")
                cls._graph_memory_enabled.pop(simulation_id, None)
            
            # cleanupprocess source
            cls._processes.pop(simulation_id, None)
            cls._action_queues.pop(simulation_id, None)
            
            # closelog files sentence
            if simulation_id in cls._stdout_files:
                try:
                    cls._stdout_files[simulation_id].close()
                except Exception:
                    pass
                cls._stdout_files.pop(simulation_id, None)
            if simulation_id in cls._stderr_files and cls._stderr_files[simulation_id]:
                try:
                    cls._stderr_files[simulation_id].close()
                except Exception:
                    pass
                cls._stderr_files.pop(simulation_id, None)
    
    @classmethod
    def _read_action_log(
        cls, 
        log_path: str, 
        position: int, 
        state: SimulationRunState,
        platform: str
    ) -> int:
        """
         read fetch dynamic log files
        
        Args:
            log_path: log filespath
            position: the previously read position
            state: runstatusobject
            platform: name (twitter/reddit)
            
        Returns:
             new read fetch position
        """
        # check is else enablegraphmemoryupdate
        graph_memory_enabled = cls._graph_memory_enabled.get(state.simulation_id, False)
        graph_updater = None
        if graph_memory_enabled:
            graph_updater = ZepGraphMemoryManager.get_updater(state.simulation_id)
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                f.seek(position)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            action_data = json.loads(line)
                            
                            # processeventtype entries item
                            if "event_type" in action_data:
                                event_type = action_data.get("event_type")
                                
                                # simulation_end event, mark already complete
                                if event_type == "simulation_end":
                                    if platform == "twitter":
                                        state.twitter_completed = True
                                        state.twitter_running = False
                                        logger.info(f"Twitter simulation already complete: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    elif platform == "reddit":
                                        state.reddit_completed = True
                                        state.reddit_running = False
                                        logger.info(f"Reddit simulation already complete: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    
                                    # check is else allenable all already complete
                                    # if only run one , only check that
                                    # ifrun , need to all complete
                                    all_completed = cls._check_all_platforms_completed(state)
                                    if all_completed:
                                        state.runner_status = RunnerStatus.COMPLETED
                                        state.completed_at = datetime.now().isoformat()
                                        logger.info(f"allsimulation already complete: {state.simulation_id}")
                                
                                # updateroundinfo( from round_end event)
                                elif event_type == "round_end":
                                    round_num = action_data.get("round", 0)
                                    simulated_hours = action_data.get("simulated_hours", 0)
                                    
                                    # update each independentround and time space
                                    if platform == "twitter":
                                        if round_num > state.twitter_current_round:
                                            state.twitter_current_round = round_num
                                        state.twitter_simulated_hours = simulated_hours
                                    elif platform == "reddit":
                                        if round_num > state.reddit_current_round:
                                            state.reddit_current_round = round_num
                                        state.reddit_simulated_hours = simulated_hours
                                    
                                    # body round get maximum value
                                    if round_num > state.current_round:
                                        state.current_round = round_num
                                    # body time space get maximum value
                                    state.simulated_hours = max(state.twitter_simulated_hours, state.reddit_simulated_hours)
                                
                                continue
                            
                            action = AgentAction(
                                round_num=action_data.get("round", 0),
                                timestamp=action_data.get("timestamp", datetime.now().isoformat()),
                                platform=platform,
                                agent_id=action_data.get("agent_id", 0),
                                agent_name=action_data.get("agent_name", ""),
                                action_type=action_data.get("action_type", ""),
                                action_args=action_data.get("action_args", {}),
                                result=action_data.get("result"),
                                success=action_data.get("success", True),
                            )
                            state.add_action(action)
                            
                            # updateround
                            if action.round_num and action.round_num > state.current_round:
                                state.current_round = action.round_num
                            
                            # ifenablegraphmemoryupdate, will dynamic send to Zep
                            if graph_updater:
                                graph_updater.add_activity_from_dict(action_data, platform)
                            
                        except json.JSONDecodeError:
                            pass
                return f.tell()
        except Exception as e:
            logger.warning(f" read fetch dynamic logfailed: {log_path}, error={e}")
            return position
    
    @classmethod
    def _check_all_platforms_completed(cls, state: SimulationRunState) -> bool:
        """
         check allenable is else all already completesimulation
        
         through past check for should actions.jsonl file is else exist in from check is else was enable
        
        Returns:
            True ifallenable all already complete
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        twitter_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        # check some was enable( through past file is else exist in check)
        twitter_enabled = os.path.exists(twitter_log)
        reddit_enabled = os.path.exists(reddit_log)
        
        # if was enable but not complete, then return False
        if twitter_enabled and not state.twitter_completed:
            return False
        if reddit_enabled and not state.reddit_completed:
            return False
        
        # few has one was enable and already complete
        return twitter_enabled or reddit_enabled
    
    @classmethod
    def _terminate_process(cls, process: subprocess.Popen, simulation_id: str, timeout: int = 10):
        """
         end stop process and its subprocess
        
        Args:
            process: need end stop process
            simulation_id: simulationID( at log)
            timeout: waitingprocess exit timeout time space ( second )
        """
        if IS_WINDOWS:
            # Windows: using taskkill order end stop process
            # /F = strong control end stop , /T = end stop process( package subprocess)
            logger.info(f" end stop process (Windows): simulation={simulation_id}, pid={process.pid}")
            try:
                # test end stop
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T'],
                    capture_output=True,
                    timeout=5
                )
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # strong control end stop
                    logger.warning(f"process not response, strong control end stop : {simulation_id}")
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(process.pid), '/T'],
                        capture_output=True,
                        timeout=5
                    )
                    process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"taskkill failed, test terminate: {e}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        else:
            # Unix: using process group end stop
            # due to using start_new_session=True, process group ID at main process PID
            pgid = os.getpgid(process.pid)
            logger.info(f" end stop process group (Unix): simulation={simulation_id}, pgid={pgid}")
            
            # send SIGTERM to whole process group
            os.killpg(pgid, signal.SIGTERM)
            
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # iftimeout after also end, strong control send SIGKILL
                logger.warning(f"process group not response SIGTERM, strong control end stop : {simulation_id}")
                os.killpg(pgid, signal.SIGKILL)
                process.wait(timeout=5)
    
    @classmethod
    def stop_simulation(cls, simulation_id: str) -> SimulationRunState:
        """stopsimulation"""
        state = cls.get_run_state(simulation_id)
        if not state:
            raise ValueError(f"simulation not exist in : {simulation_id}")
        
        if state.runner_status not in [RunnerStatus.RUNNING, RunnerStatus.PAUSED]:
            raise ValueError(f"simulation not in run: {simulation_id}, status={state.runner_status}")
        
        state.runner_status = RunnerStatus.STOPPING
        cls._save_run_state(state)
        
        # end stop process
        process = cls._processes.get(simulation_id)
        if process and process.poll() is None:
            try:
                cls._terminate_process(process, simulation_id)
            except ProcessLookupError:
                # processalready not exist in
                pass
            except Exception as e:
                logger.error(f" end stop process group failed: {simulation_id}, error={e}")
                # fallback to directly end stop process
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
        
        state.runner_status = RunnerStatus.STOPPED
        state.twitter_running = False
        state.reddit_running = False
        state.completed_at = datetime.now().isoformat()
        cls._save_run_state(state)
        
        # stopgraphmemoryupdate
        if cls._graph_memory_enabled.get(simulation_id, False):
            try:
                ZepGraphMemoryManager.stop_updater(simulation_id)
                logger.info(f" already stopgraphmemoryupdate: simulation_id={simulation_id}")
            except Exception as e:
                logger.error(f"stopgraphmemoryupdatefailed: {e}")
            cls._graph_memory_enabled.pop(simulation_id, None)
        
        logger.info(f"simulation already stop: {simulation_id}")
        return state
    
    @classmethod
    def _read_actions_from_file(
        cls,
        file_path: str,
        default_platform: Optional[str] = None,
        platform_filter: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
         from dynamic file in read fetch dynamic
        
        Args:
            file_path: dynamic log filespath
            default_platform: default( dynamic record in no platform char segment time using )
            platform_filter: filter
            agent_id: filter Agent ID
            round_num: filterround
        """
        if not os.path.exists(file_path):
            return []
        
        actions = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # skipnon- dynamic record ( if simulation_start, round_start, round_end event)
                    if "event_type" in data:
                        continue
                    
                    # skipno agent_id record (non- Agent dynamic )
                    if "agent_id" not in data:
                        continue
                    
                    # fetch : using record in platform, otherwise using default
                    record_platform = data.get("platform") or default_platform or ""
                    
                    # filter
                    if platform_filter and record_platform != platform_filter:
                        continue
                    if agent_id is not None and data.get("agent_id") != agent_id:
                        continue
                    if round_num is not None and data.get("round") != round_num:
                        continue
                    
                    actions.append(AgentAction(
                        round_num=data.get("round", 0),
                        timestamp=data.get("timestamp", ""),
                        platform=record_platform,
                        agent_id=data.get("agent_id", 0),
                        agent_name=data.get("agent_name", ""),
                        action_type=data.get("action_type", ""),
                        action_args=data.get("action_args", {}),
                        result=data.get("result"),
                        success=data.get("success", True),
                    ))
                    
                except json.JSONDecodeError:
                    continue
        
        return actions
    
    @classmethod
    def get_all_actions(
        cls,
        simulation_id: str,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
         fetch allcomplete dynamic ( no divide limit)
        
        Args:
            simulation_id: simulationID
            platform: filter(twitter/reddit)
            agent_id: filterAgent
            round_num: filterround
            
        Returns:
            complete dynamic list( time space sort, new in before )
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        actions = []
        
        # read fetch Twitter dynamic file( root filepathautosettings platform as twitter)
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        if not platform or platform == "twitter":
            actions.extend(cls._read_actions_from_file(
                twitter_actions_log,
                default_platform="twitter", # auto fill platform char segment
                platform_filter=platform,
                agent_id=agent_id, 
                round_num=round_num
            ))
        
        # read fetch Reddit dynamic file( root filepathautosettings platform as reddit)
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        if not platform or platform == "reddit":
            actions.extend(cls._read_actions_from_file(
                reddit_actions_log,
                default_platform="reddit", # auto fill platform char segment
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            ))
        
        # if divide file not exist in , test read fetch old one fileformat
        if not actions:
            actions_log = os.path.join(sim_dir, "actions.jsonl")
            actions = cls._read_actions_from_file(
                actions_log,
                default_platform=None, # old formatfile in should has platform char segment
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            )
        
        # time space sort( new in before )
        actions.sort(key=lambda x: x.timestamp, reverse=True)
        
        return actions
    
    @classmethod
    def get_actions(
        cls,
        simulation_id: str,
        limit: int = 100,
        offset: int = 0,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
         fetch dynamic ( with divide )
        
        Args:
            simulation_id: simulationID
            limit: return number amount limit
            offset: offset amount
            platform: filter
            agent_id: filterAgent
            round_num: filterround
            
        Returns:
             dynamic list
        """
        actions = cls.get_all_actions(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        # divide
        return actions[offset:offset + limit]
    
    @classmethod
    def get_timeline(
        cls,
        simulation_id: str,
        start_round: int = 0,
        end_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
         fetch simulation time space line (round)
        
        Args:
            simulation_id: simulationID
            start_round: begin round
            end_round: endround
            
        Returns:
             each roundinfo
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        # round divide group
        rounds: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            round_num = action.round_num
            
            if round_num < start_round:
                continue
            if end_round is not None and round_num > end_round:
                continue
            
            if round_num not in rounds:
                rounds[round_num] = {
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "active_agents": set(),
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            r = rounds[round_num]
            
            if action.platform == "twitter":
                r["twitter_actions"] += 1
            else:
                r["reddit_actions"] += 1
            
            r["active_agents"].add(action.agent_id)
            r["action_types"][action.action_type] = r["action_types"].get(action.action_type, 0) + 1
            r["last_action_time"] = action.timestamp
        
        # convert as list
        result = []
        for round_num in sorted(rounds.keys()):
            r = rounds[round_num]
            result.append({
                "round_num": round_num,
                "twitter_actions": r["twitter_actions"],
                "reddit_actions": r["reddit_actions"],
                "total_actions": r["twitter_actions"] + r["reddit_actions"],
                "active_agents_count": len(r["active_agents"]),
                "active_agents": list(r["active_agents"]),
                "action_types": r["action_types"],
                "first_action_time": r["first_action_time"],
                "last_action_time": r["last_action_time"],
            })
        
        return result
    
    @classmethod
    def get_agent_stats(cls, simulation_id: str) -> List[Dict[str, Any]]:
        """
         fetch eachAgentstatisticsinfo
        
        Returns:
            Agentstatisticslist
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        agent_stats: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            agent_id = action.agent_id
            
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": action.agent_name,
                    "total_actions": 0,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            stats = agent_stats[agent_id]
            stats["total_actions"] += 1
            
            if action.platform == "twitter":
                stats["twitter_actions"] += 1
            else:
                stats["reddit_actions"] += 1
            
            stats["action_types"][action.action_type] = stats["action_types"].get(action.action_type, 0) + 1
            stats["last_action_time"] = action.timestamp
        
        # dynamic number sort
        result = sorted(agent_stats.values(), key=lambda x: x["total_actions"], reverse=True)
        
        return result
    
    @classmethod
    def cleanup_simulation_logs(cls, simulation_id: str) -> Dict[str, Any]:
        """
        cleanupsimulationrunlog( at strong control new startsimulation)
        
         will delete to below file:
        - run_state.json
        - twitter/actions.jsonl
        - reddit/actions.jsonl
        - simulation.log
        - stdout.log / stderr.log
        - twitter_simulation.db(simulationdatabase)
        - reddit_simulation.db(simulationdatabase)
        - env_status.json( loop status)
        
        note: not will deleteconfigurationfile(simulation_config.json) and profile file
        
        Args:
            simulation_id: simulationID
            
        Returns:
            cleanupinfo
        """
        import shutil
        
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return {"success": True, "message": "simulationdirectory not exist in , no need cleanup"}
        
        cleaned_files = []
        errors = []
        
        # need deletefilelist( package databasefile)
        files_to_delete = [
            "run_state.json",
            "simulation.log",
            "stdout.log",
            "stderr.log",
            "twitter_simulation.db", # Twitter database
            "reddit_simulation.db", # Reddit database
            "env_status.json", # loop statusfile
        ]
        
        # need deletedirectorylist(contain dynamic log)
        dirs_to_clean = ["twitter", "reddit"]
        
        # deletefile
        for filename in files_to_delete:
            file_path = os.path.join(sim_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_files.append(filename)
                except Exception as e:
                    errors.append(f"delete {filename} failed: {str(e)}")
        
        # cleanupdirectory in dynamic log
        for dir_name in dirs_to_clean:
            dir_path = os.path.join(sim_dir, dir_name)
            if os.path.exists(dir_path):
                actions_file = os.path.join(dir_path, "actions.jsonl")
                if os.path.exists(actions_file):
                    try:
                        os.remove(actions_file)
                        cleaned_files.append(f"{dir_name}/actions.jsonl")
                    except Exception as e:
                        errors.append(f"delete {dir_name}/actions.jsonl failed: {str(e)}")
        
        # cleanup within exist in runstatus
        if simulation_id in cls._run_states:
            del cls._run_states[simulation_id]
        
        logger.info(f"cleanupsimulationlogcomplete: {simulation_id}, deletefile: {cleaned_files}")
        
        return {
            "success": len(errors) == 0,
            "cleaned_files": cleaned_files,
            "errors": errors if errors else None
        }
    
    # prevent duplicatecleanup mark log
    _cleanup_done = False
    
    @classmethod
    def cleanup_all_simulations(cls):
        """
        cleanupallrun in simulationprocess
        
        in serviceclose time call, correctly protect allsubprocess was end stop
        """
        # prevent duplicatecleanup
        if cls._cleanup_done:
            return
        cls._cleanup_done = True
        
        # check is else has content need to cleanup( avoid exempt empty processprocess no log)
        has_processes = bool(cls._processes)
        has_updaters = bool(cls._graph_memory_enabled)
        
        if not has_processes and not has_updaters:
            return # no need to cleanupcontent, static return
        
        logger.info("currentlycleanupallsimulationprocess...")
        
        # firststopallgraphmemoryupdate(stop_all internal will log)
        try:
            ZepGraphMemoryManager.stop_all()
        except Exception as e:
            logger.error(f"stopgraphmemoryupdatefailed: {e}")
        cls._graph_memory_enabled.clear()
        
        # copydictionary to avoid exempt in iterate time modify
        processes = list(cls._processes.items())
        
        for simulation_id, process in processes:
            try:
                if process.poll() is None: # process in run
                    logger.info(f" end stop simulationprocess: {simulation_id}, pid={process.pid}")
                    
                    try:
                        # using process end stop method
                        cls._terminate_process(process, simulation_id, timeout=5)
                    except (ProcessLookupError, OSError):
                        # processmayalready not exist in , test directly end stop
                        try:
                            process.terminate()
                            process.wait(timeout=3)
                        except Exception:
                            process.kill()
                    
                    # update run_state.json
                    state = cls.get_run_state(simulation_id)
                    if state:
                        state.runner_status = RunnerStatus.STOPPED
                        state.twitter_running = False
                        state.reddit_running = False
                        state.completed_at = datetime.now().isoformat()
                        state.error = "serviceclose, simulation was end stop "
                        cls._save_run_state(state)
                    
                    # meanwhileupdate state.json, will status as stopped
                    try:
                        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
                        state_file = os.path.join(sim_dir, "state.json")
                        logger.info(f" test update state.json: {state_file}")
                        if os.path.exists(state_file):
                            with open(state_file, 'r', encoding='utf-8') as f:
                                state_data = json.load(f)
                            state_data['status'] = 'stopped'
                            state_data['updated_at'] = datetime.now().isoformat()
                            with open(state_file, 'w', encoding='utf-8') as f:
                                json.dump(state_data, f, indent=2, ensure_ascii=False)
                            logger.info(f" already update state.json status as stopped: {simulation_id}")
                        else:
                            logger.warning(f"state.json not exist in : {state_file}")
                    except Exception as state_err:
                        logger.warning(f"update state.json failed: {simulation_id}, error={state_err}")
                        
            except Exception as e:
                logger.error(f"cleanupprocessfailed: {simulation_id}, error={e}")
        
        # cleanupfile sentence
        for simulation_id, file_handle in list(cls._stdout_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stdout_files.clear()
        
        for simulation_id, file_handle in list(cls._stderr_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stderr_files.clear()
        
        # cleanup within exist in status
        cls._processes.clear()
        cls._action_queues.clear()
        
        logger.info("simulationprocesscleanupcomplete")
    
    @classmethod
    def register_cleanup(cls):
        """
        registercleanupfunction
        
        in Flask should start time call, correctly protect serviceclose time cleanupallsimulationprocess
        """
        global _cleanup_registered
        
        if _cleanup_registered:
            return
        
        # Flask debug mode below , only in reloader subprocess registercleanup( actual run should process)
        # WERKZEUG_RUN_MAIN=true indicates this is the reloader subprocess
        # If not in debug mode, this env var won't exist, but we still need to register
        is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        is_debug_mode = os.environ.get('FLASK_DEBUG') == '1' or os.environ.get('WERKZEUG_RUN_MAIN') is not None
        
        # In debug mode, only register in reloader subprocess; in non-debug mode, always register
        if is_debug_mode and not is_reloader_process:
            _cleanup_registered = True  # Mark as registered to prevent duplicate registration
            return
        
        # save original signal handlersprocess
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        # SIGHUP only in Unix system unified exist in (macOS/Linux), Windows no
        original_sighup = None
        has_sighup = hasattr(signal, 'SIGHUP')
        if has_sighup:
            original_sighup = signal.getsignal(signal.SIGHUP)
        
        def cleanup_handler(signum=None, frame=None):
            """signalprocess: cleanupsimulationprocess, again call original process"""
            # only has in has process need to cleanup time log
            if cls._processes or cls._graph_memory_enabled:
                logger.info(f" collect to signal {signum}, startcleanup...")
            cls.cleanup_all_simulations()
            
            # call original has signalprocess, let Flask positive normal exit
            if signum == signal.SIGINT and callable(original_sigint):
                original_sigint(signum, frame)
            elif signum == signal.SIGTERM and callable(original_sigterm):
                original_sigterm(signum, frame)
            elif has_sighup and signum == signal.SIGHUP:
                # SIGHUP: end endpoint close time send
                if callable(original_sighup):
                    original_sighup(signum, frame)
                else:
                    # default line as : positive normal exit
                    sys.exit(0)
            else:
                # if original process not can call( if SIG_DFL), then using default line as
                raise KeyboardInterrupt
        
        # register atexit process( as backup )
        atexit.register(cls.cleanup_all_simulations)
        
        # registersignalprocess( only in main thread in )
        try:
            # SIGTERM: kill order defaultsignal
            signal.signal(signal.SIGTERM, cleanup_handler)
            # SIGINT: Ctrl+C
            signal.signal(signal.SIGINT, cleanup_handler)
            # SIGHUP: end endpoint close( only Unix system unified )
            if has_sighup:
                signal.signal(signal.SIGHUP, cleanup_handler)
        except ValueError:
            # not in main thread in , only can using atexit
            logger.warning(" no method registersignalprocess( not in main thread), only using atexit")
        
        _cleanup_registered = True
    
    @classmethod
    def get_running_simulations(cls) -> List[str]:
        """
         fetch allcurrentlyrunsimulationIDlist
        """
        running = []
        for sim_id, process in cls._processes.items():
            if process.poll() is None:
                running.append(sim_id)
        return running
    
    # ============== Interview feature ==============
    
    @classmethod
    def check_env_alive(cls, simulation_id: str) -> bool:
        """
         check simulation environment is else exist ( can to receiveInterview order )

        Args:
            simulation_id: simulationID

        Returns:
            True table loop exist , False table loop already close
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return False

        ipc_client = SimulationIPCClient(sim_dir)
        return ipc_client.check_env_alive()

    @classmethod
    def get_env_status_detail(cls, simulation_id: str) -> Dict[str, Any]:
        """
         fetch simulation environmentdetailedstatusinfo

        Args:
            simulation_id: simulationID

        Returns:
            statusdetailsdictionary, contain status, twitter_available, reddit_available, timestamp
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        status_file = os.path.join(sim_dir, "env_status.json")
        
        default_status = {
            "status": "stopped",
            "twitter_available": False,
            "reddit_available": False,
            "timestamp": None
        }
        
        if not os.path.exists(status_file):
            return default_status
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return {
                "status": status.get("status", "stopped"),
                "twitter_available": status.get("twitter_available", False),
                "reddit_available": status.get("reddit_available", False),
                "timestamp": status.get("timestamp")
            }
        except (json.JSONDecodeError, OSError):
            return default_status

    @classmethod
    def interview_agent(
        cls,
        simulation_id: str,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> Dict[str, Any]:
        """
        interview Agent

        Args:
            simulation_id: simulationID
            agent_id: Agent ID
            prompt: interview question topic
            platform: point fixed (optional)
                - "twitter": only interviewTwitter
                - "reddit": only interviewReddit
                - None: dual simulation time meanwhileinterview , return whole
            timeout: timeout time space ( second )

        Returns:
            interviewdictionary

        Raises:
            ValueError: simulation not exist in or loop not run
            TimeoutError: waitingresponsetimeout
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"simulation not exist in : {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"simulation environment not run or already close, no method executeInterview: {simulation_id}")

        logger.info(f"sendInterview order : simulation_id={simulation_id}, agent_id={agent_id}, platform={platform}")

        response = ipc_client.send_interview(
            agent_id=agent_id,
            prompt=prompt,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "agent_id": agent_id,
                "prompt": prompt,
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "agent_id": agent_id,
                "prompt": prompt,
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_agents_batch(
        cls,
        simulation_id: str,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
         amount interview many Agent

        Args:
            simulation_id: simulationID
            interviews: interviewlist, eachcontain {"agent_id": int, "prompt": str, "platform": str(optional)}
            platform: default(optional, will was eachinterview items platformoverride)
                - "twitter": default only interviewTwitter
                - "reddit": default only interviewReddit
                - None: dual simulation time eachAgentmeanwhileinterview
            timeout: timeout time space ( second )

        Returns:
             amount interviewdictionary

        Raises:
            ValueError: simulation not exist in or loop not run
            TimeoutError: waitingresponsetimeout
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"simulation not exist in : {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"simulation environment not run or already close, no method executeInterview: {simulation_id}")

        logger.info(f"send amount Interview order : simulation_id={simulation_id}, count={len(interviews)}, platform={platform}")

        response = ipc_client.send_batch_interview(
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "interviews_count": len(interviews),
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "interviews_count": len(interviews),
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_all_agents(
        cls,
        simulation_id: str,
        prompt: str,
        platform: str = None,
        timeout: float = 180.0
    ) -> Dict[str, Any]:
        """
        interviewallAgent(globalinterview)

         using same question topic interviewsimulation in allAgent

        Args:
            simulation_id: simulationID
            prompt: interview question topic (allAgent using same question topic )
            platform: point fixed (optional)
                - "twitter": only interviewTwitter
                - "reddit": only interviewReddit
                - None: dual simulation time eachAgentmeanwhileinterview
            timeout: timeout time space ( second )

        Returns:
            globalinterviewdictionary
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"simulation not exist in : {simulation_id}")

        # from configurationfile fetch allAgentinfo
        config_path = os.path.join(sim_dir, "simulation_config.json")
        if not os.path.exists(config_path):
            raise ValueError(f"simulation configuration not exist in : {simulation_id}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        agent_configs = config.get("agent_configs", [])
        if not agent_configs:
            raise ValueError(f"simulation configuration in noAgent: {simulation_id}")

        # structure amount interviewlist
        interviews = []
        for agent_config in agent_configs:
            agent_id = agent_config.get("agent_id")
            if agent_id is not None:
                interviews.append({
                    "agent_id": agent_id,
                    "prompt": prompt
                })

        logger.info(f"sendglobalInterview order : simulation_id={simulation_id}, agent_count={len(interviews)}, platform={platform}")

        return cls.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )
    
    @classmethod
    def close_simulation_env(
        cls,
        simulation_id: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        closesimulation environment( not as stopsimulationprocess)
        
         toward simulationsendclose loop order , using its exit waiting order mode
        
        Args:
            simulation_id: simulationID
            timeout: timeout time space ( second )
            
        Returns:
            dictionary
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"simulation not exist in : {simulation_id}")
        
        ipc_client = SimulationIPCClient(sim_dir)
        
        if not ipc_client.check_env_alive():
            return {
                "success": True,
                "message": " loop alreadyclose"
            }
        
        logger.info(f"sendclose loop order : simulation_id={simulation_id}")
        
        try:
            response = ipc_client.send_close_env(timeout=timeout)
            
            return {
                "success": response.status.value == "completed",
                "message": " loop close order already send",
                "result": response.result,
                "timestamp": response.timestamp
            }
        except TimeoutError:
            # timeoutmay is because loop currentlyclose
            return {
                "success": True,
                "message": " loop close order already send(waitingresponsetimeout, loop maycurrentlyclose)"
            }
    
    @classmethod
    def _get_interview_history_from_db(
        cls,
        db_path: str,
        platform_name: str,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """ from database fetch Interview"""
        import sqlite3
        
        if not os.path.exists(db_path):
            return []
        
        results = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if agent_id is not None:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview' AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (agent_id, limit))
            else:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            for user_id, info_json, created_at in cursor.fetchall():
                try:
                    info = json.loads(info_json) if info_json else {}
                except json.JSONDecodeError:
                    info = {"raw": info_json}
                
                results.append({
                    "agent_id": user_id,
                    "response": info.get("response", info),
                    "prompt": info.get("prompt", ""),
                    "timestamp": created_at,
                    "platform": platform_name
                })
            
            conn.close()
            
        except Exception as e:
            logger.error(f" read fetch Interviewfailed ({platform_name}): {e}")
        
        return results

    @classmethod
    def get_interview_history(
        cls,
        simulation_id: str,
        platform: str = None,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
         fetch Interview record ( from database read fetch )
        
        Args:
            simulation_id: simulationID
            platform: type(reddit/twitter/None)
                - "reddit": only fetch Reddit
                - "twitter": only fetch Twitter
                - None: fetch all
            agent_id: point fixed Agent ID(optional, only fetch the Agent)
            limit: each return number amount limit
            
        Returns:
            Interview record list
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        results = []
        
        # correct fixed need query
        if platform in ("reddit", "twitter"):
            platforms = [platform]
        else:
            # not point fixed platform time , query
            platforms = ["twitter", "reddit"]
        
        for p in platforms:
            db_path = os.path.join(sim_dir, f"{p}_simulation.db")
            platform_results = cls._get_interview_history_from_db(
                db_path=db_path,
                platform_name=p,
                agent_id=agent_id,
                limit=limit
            )
            results.extend(platform_results)
        
        # time space order sort
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # ifquery many , limit number
        if len(platforms) > 1 and len(results) > limit:
            results = results[:limit]
        
        return results

