"""
simulationIPC through model block
 at Flaskbackend and simulation space process space through

 through past file system unified implementation simple order /responsemode:
1. Flask write enter order to commands/ directory
2. simulationpolling order directory, execute order write enter response to responses/ directory
3. Flaskpollingresponsedirectory fetch
"""

import os
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger('jarvis.simulation_ipc')


class CommandType(str, Enum):
    """ order type"""
    INTERVIEW = "interview" # Agentinterview
    BATCH_INTERVIEW = "batch_interview" # amount interview
    CLOSE_ENV = "close_env" # close loop


class CommandStatus(str, Enum):
    """ order status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IPCCommand:
    """IPC order """
    command_id: str
    command_type: CommandType
    args: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "args": self.args,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCCommand':
        return cls(
            command_id=data["command_id"],
            command_type=CommandType(data["command_type"]),
            args=data.get("args", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class IPCResponse:
    """IPCresponse"""
    command_id: str
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCResponse':
        return cls(
            command_id=data["command_id"],
            status=CommandStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


class SimulationIPCClient:
    """
    simulationIPC endpoint (Flask endpoint using )
    
     at toward simulationprocesssend order waitingresponse
    """
    
    def __init__(self, simulation_dir: str):
        """
        initializeIPC endpoint
        
        Args:
            simulation_dir: simulationdatadirectory
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
        # correctly protect directory exist in
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def send_command(
        self,
        command_type: CommandType,
        args: Dict[str, Any],
        timeout: float = 60.0,
        poll_interval: float = 0.5
    ) -> IPCResponse:
        """
        send order waitingresponse
        
        Args:
            command_type: order type
            args: order parameter
            timeout: timeout time space ( second )
            poll_interval: polling space ( second )
            
        Returns:
            IPCResponse
            
        Raises:
            TimeoutError: waitingresponsetimeout
        """
        command_id = str(uuid.uuid4())
        command = IPCCommand(
            command_id=command_id,
            command_type=command_type,
            args=args
        )
        
        # write enter order file
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        with open(command_file, 'w', encoding='utf-8') as f:
            json.dump(command.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"sendIPC order : {command_type.value}, command_id={command_id}")
        
        # waitingresponse
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r', encoding='utf-8') as f:
                        response_data = json.load(f)
                    response = IPCResponse.from_dict(response_data)
                    
                    # cleanup order and responsefile
                    try:
                        os.remove(command_file)
                        os.remove(response_file)
                    except OSError:
                        pass
                    
                    logger.info(f" collect to IPCresponse: command_id={command_id}, status={response.status.value}")
                    return response
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"parseresponsefailed: {e}")
            
            time.sleep(poll_interval)
        
        # timeout
        logger.error(f"waitingIPCresponsetimeout: command_id={command_id}")
        
        # cleanup order file
        try:
            os.remove(command_file)
        except OSError:
            pass
        
        raise TimeoutError(f"waiting order responsetimeout ({timeout} second )")
    
    def send_interview(
        self,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> IPCResponse:
        """
        send Agentinterview order
        
        Args:
            agent_id: Agent ID
            prompt: interview question topic
            platform: point fixed (optional)
                - "twitter": only interviewTwitter
                - "reddit": only interviewReddit
                - None: dual simulation time meanwhileinterview , simulation time interview the
            timeout: timeout time space
            
        Returns:
            IPCResponse, result char segment containinterview
        """
        args = {
            "agent_id": agent_id,
            "prompt": prompt
        }
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_batch_interview(
        self,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> IPCResponse:
        """
        send amount interview order
        
        Args:
            interviews: interviewlist, eachcontain {"agent_id": int, "prompt": str, "platform": str(optional)}
            platform: default(optional, will was eachinterview items platformoverride)
                - "twitter": default only interviewTwitter
                - "reddit": default only interviewReddit
                - None: dual simulation time eachAgentmeanwhileinterview
            timeout: timeout time space
            
        Returns:
            IPCResponse, result char segment containallinterview
        """
        args = {"interviews": interviews}
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.BATCH_INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_close_env(self, timeout: float = 30.0) -> IPCResponse:
        """
        sendclose loop order
        
        Args:
            timeout: timeout time space
            
        Returns:
            IPCResponse
        """
        return self.send_command(
            command_type=CommandType.CLOSE_ENV,
            args={},
            timeout=timeout
        )
    
    def check_env_alive(self) -> bool:
        """
         check simulation environment is else exist
        
         through past check env_status.json file from check
        """
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        if not os.path.exists(status_file):
            return False
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return status.get("status") == "alive"
        except (json.JSONDecodeError, OSError):
            return False


class SimulationIPCServer:
    """
    simulationIPCservice(simulation endpoint using )
    
    polling order directory, execute order return response
    """
    
    def __init__(self, simulation_dir: str):
        """
        initializeIPCservice
        
        Args:
            simulation_dir: simulationdatadirectory
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
        # correctly protect directory exist in
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
        
        # loop status
        self._running = False
    
    def start(self):
        """markservice as runstatus"""
        self._running = True
        self._update_env_status("alive")
    
    def stop(self):
        """markservice as stopstatus"""
        self._running = False
        self._update_env_status("stopped")
    
    def _update_env_status(self, status: str):
        """update loop statusfile"""
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_commands(self) -> Optional[IPCCommand]:
        """
        polling order directory, return # one process order
        
        Returns:
            IPCCommand or None
        """
        if not os.path.exists(self.commands_dir):
            return None
        
        # time space sort fetch order file
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))
        
        command_files.sort(key=lambda x: x[1])
        
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return IPCCommand.from_dict(data)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f" read fetch order filefailed: {filepath}, {e}")
                continue
        
        return None
    
    def send_response(self, response: IPCResponse):
        """
        sendresponse
        
        Args:
            response: IPCresponse
        """
        response_file = os.path.join(self.responses_dir, f"{response.command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response.to_dict(), f, ensure_ascii=False, indent=2)
        
        # delete order file
        command_file = os.path.join(self.commands_dir, f"{response.command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    def send_success(self, command_id: str, result: Dict[str, Any]):
        """sendsuccessresponse"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.COMPLETED,
            result=result
        ))
    
    def send_error(self, command_id: str, error: str):
        """senderrorresponse"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.FAILED,
            error=error
        ))
