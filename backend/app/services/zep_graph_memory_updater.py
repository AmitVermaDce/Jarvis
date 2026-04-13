"""
Zepgraphmemoryupdateservice
 will simulation in Agent dynamic dynamic update to Zepgraph in
"""

import os
import time
import threading
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_locale, set_locale

logger = get_logger('jarvis.zep_graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent dynamic record """
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str
    
    def to_episode_text(self) -> str:
        """
         will dynamic convert as can to send to Zeptextdescription
        
         self language speech descriptionformat, let Zep can enough from in extractentity and relation
         not addsimulationrelated before , avoid exempt mistake guide graphupdate
        """
        # root different dynamic typegenerate different description
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }
        
        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()
        
        # directly return "agentname: dynamic description" format, not addsimulation before
        return f"{self.agent_name}: {description}"
    
    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"publish one entries sub : '{content}'"
        return "publish one entries sub "
    
    def _describe_like_post(self) -> str:
        """like sub - contain sub original text and info"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"like{post_author} sub : '{post_content}'"
        elif post_content:
            return f"like one entries sub : '{post_content}'"
        elif post_author:
            return f"like{post_author} one entries sub "
        return "like one entries sub "
    
    def _describe_dislike_post(self) -> str:
        """ sub - contain sub original text and info"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"{post_author} sub : '{post_content}'"
        elif post_content:
            return f" one entries sub : '{post_content}'"
        elif post_author:
            return f"{post_author} one entries sub "
        return " one entries sub "
    
    def _describe_repost(self) -> str:
        """ turn posting sub - contain original content and info"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        
        if original_content and original_author:
            return f"repost{original_author} sub : '{original_content}'"
        elif original_content:
            return f"repost one entries sub : '{original_content}'"
        elif original_author:
            return f"repost{original_author} one entries sub "
        return "repost one entries sub "
    
    def _describe_quote_post(self) -> str:
        """quote sub - contain original content, info and quotecomment"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")
        
        base = ""
        if original_content and original_author:
            base = f"quote{original_author} sub '{original_content}'"
        elif original_content:
            base = f"quote one entries sub '{original_content}'"
        elif original_author:
            base = f"quote{original_author} one entries sub "
        else:
            base = "quote one entries sub "
        
        if quote_content:
            base += f", comment: '{quote_content}'"
        return base
    
    def _describe_follow(self) -> str:
        """followuser - contain was followusername"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"followuser'{target_user_name}'"
        return "follow one user"
    
    def _describe_create_comment(self) -> str:
        """ send table comment - containcommentcontent and comment sub info"""
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if content:
            if post_content and post_author:
                return f" in {post_author} sub '{post_content}' below comment: '{content}'"
            elif post_content:
                return f" in sub '{post_content}' below comment: '{content}'"
            elif post_author:
                return f" in {post_author} sub below comment: '{content}'"
            return f"comment: '{content}'"
        return " send table comment"
    
    def _describe_like_comment(self) -> str:
        """likecomment - containcommentcontent and info"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"like{comment_author}comment: '{comment_content}'"
        elif comment_content:
            return f"like one entries comment: '{comment_content}'"
        elif comment_author:
            return f"like{comment_author} one entries comment"
        return "like one entries comment"
    
    def _describe_dislike_comment(self) -> str:
        """comment - containcommentcontent and info"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"{comment_author}comment: '{comment_content}'"
        elif comment_content:
            return f" one entries comment: '{comment_content}'"
        elif comment_author:
            return f"{comment_author} one entries comment"
        return " one entries comment"
    
    def _describe_search(self) -> str:
        """search sub - containsearchkey"""
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"search'{query}'' if query else ' enter line search"
    
    def _describe_search_user(self) -> str:
        """searchuser - containsearchkey"""
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"searchuser'{query}'' if query else 'searchuser"
    
    def _describe_mute(self) -> str:
        """muteuser - contain was muteusername"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"muteuser'{target_user_name}'"
        return "mute one user"
    
    def _describe_generic(self) -> str:
        # for at not know dynamic type, generate through description
        return f"execute{self.action_type}"


class ZepGraphMemoryUpdater:
    """
    Zepgraphmemoryupdate
    
    monitorsimulationactionslog files, will new agent dynamic actual time update to Zepgraph in .
     divide group , each BATCH_SIZE entries dynamic after amount send to Zep.
    
    all has meaning line as all will was update to Zep, action_args in will containcompletecontextinfo:
    - like/ sub original text
    - repost/quote sub original text
    - follow/muteuser name
    - like/comment original text
    """
    
    # amount send large small (each many few entries after send)
    BATCH_SIZE = 5
    
    # namemapping( at consoledisplay)
    PLATFORM_DISPLAY_NAMES = {
        'twitter': '1',
        'reddit': '2',
    }
    
    # send space ( second ), avoid exempt request past fast
    SEND_INTERVAL = 0.5
    
    # retryconfiguration
    MAX_RETRIES = 3
    RETRY_DELAY = 2 # second
    
    def __init__(self, graph_id: str, api_key: Optional[str] = None):
        """
        initializeupdate
        
        Args:
            graph_id: ZepgraphID
            api_key: Zep API Key(optional, default from configuration read fetch )
        """
        self.graph_id = graph_id
        self.api_key = api_key or Config.ZEP_API_KEY
        
        if not self.api_key:
            raise ValueError("ZEP_API_KEY not configured")
        
        self.client = Zep(api_key=self.api_key)
        
        # dynamic queue
        self._activity_queue: Queue = Queue()
        
        # divide group dynamic buffer(each each self to BATCH_SIZE after amount send)
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()
        
        # control control mark log
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # statistics
        self._total_activities = 0 # actual add to queue dynamic number
        self._total_sent = 0 # successsend to Zepbatch number
        self._total_items_sent = 0 # successsend to Zep dynamic entries number
        self._failed_count = 0 # sendfailedbatch number
        self._skipped_count = 0 # was filterskip dynamic number (DO_NOTHING)
        
        logger.info(f"ZepGraphMemoryUpdater initializecomplete: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")
    
    def _get_platform_display_name(self, platform: str) -> str:
        """ fetch displayname"""
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)
    
    def start(self):
        """start after thread"""
        if self._running:
            return

        # Capture locale before spawning background thread
        current_locale = get_locale()

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            args=(current_locale,),
            daemon=True,
            name=f"ZepMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"ZepGraphMemoryUpdater already start: graph_id={self.graph_id}")
    
    def stop(self):
        """stop after thread"""
        self._running = False
        
        # send remaining remaining dynamic
        self._flush_remaining()
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        
        logger.info(f"ZepGraphMemoryUpdater already stop: graph_id={self.graph_id}, "
                   f"total_activities={self._total_activities}, "
                   f"batches_sent={self._total_sent}, "
                   f"items_sent={self._total_items_sent}, "
                   f"failed={self._failed_count}, "
                   f"skipped={self._skipped_count}")
    
    def add_activity(self, activity: AgentActivity):
        """
        add one agent dynamic to queue
        
        all has meaning line as all will was add to queue, package :
        - CREATE_POST(posting)
        - CREATE_COMMENT(comment)
        - QUOTE_POST(quote sub )
        - SEARCH_POSTS(search sub )
        - SEARCH_USER(searchuser)
        - LIKE_POST/DISLIKE_POST(like/ sub )
        - REPOST(repost)
        - FOLLOW(follow)
        - MUTE(mute)
        - LIKE_COMMENT/DISLIKE_COMMENT(like/comment)
        
        action_args in will containcompletecontextinfo( if sub original text , user name ).
        
        Args:
            activity: Agent dynamic record
        """
        # skipDO_NOTHINGtype dynamic
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return
        
        self._activity_queue.put(activity)
        self._total_activities += 1
        logger.debug(f"add dynamic to Zepqueue: {activity.agent_name} - {activity.action_type}")
    
    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        """
         from dictionarydataadd dynamic
        
        Args:
            data: from actions.jsonlparsedictionarydata
            platform: name (twitter/reddit)
        """
        # skipeventtype entries item
        if "event_type" in data:
            return
        
        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )
        
        self.add_activity(activity)
    
    def _worker_loop(self, locale: str = 'zh'):
        """ after loop - amount send dynamic to Zep"""
        set_locale(locale)
        while self._running or not self._activity_queue.empty():
            try:
                # test from queue fetch dynamic (timeout1 second )
                try:
                    activity = self._activity_queue.get(timeout=1)
                    
                    # will dynamic add to for should buffer
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)
                        
                        # check the is else reach to amount large small
                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            # release after again send
                            self._send_batch_activities(batch, platform)
                            # send space , avoid exempt request past fast
                            time.sleep(self.SEND_INTERVAL)
                    
                except Empty:
                    pass
                    
            except Exception as e:
                logger.error(f"loopexception: {e}")
                time.sleep(1)
    
    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        """
         amount send dynamic to Zepgraph(merge as one entries text)
        
        Args:
            activities: Agent dynamic list
            platform: name
        """
        if not activities:
            return
        
        # will many entries dynamic merge as one entries text, switch line divide
        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)
        
        # with retrysend
        for attempt in range(self.MAX_RETRIES):
            try:
                self.client.graph.add(
                    graph_id=self.graph_id,
                    type="text",
                    data=combined_text
                )
                
                self._total_sent += 1
                self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(f"success amount send {len(activities)} entries {display_name} dynamic to graph {self.graph_id}")
                logger.debug(f" amount content: {combined_text[:200]}...")
                return
                
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f" amount send to Zepfailed ( test {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f" amount send to Zepfailed, already retry{self.MAX_RETRIES} times : {e}")
                    self._failed_count += 1
    
    def _flush_remaining(self):
        """sendqueue and buffer in remaining remaining dynamic """
        # firstprocessqueue in remaining remaining dynamic , add to buffer
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break
        
        # thensend each buffer in remaining remaining dynamic ( immediately using not sufficient BATCH_SIZE entries )
        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(f"send{display_name} remaining remaining {len(buffer)} entries dynamic ")
                    self._send_batch_activities(buffer, platform)
            # empty allbuffer
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []
    
    def get_stats(self) -> Dict[str, Any]:
        """ fetch statisticsinfo"""
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}
        
        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities, # add to queue dynamic number
            "batches_sent": self._total_sent, # successsendbatch number
            "items_sent": self._total_items_sent, # successsend dynamic entries number
            "failed_count": self._failed_count, # sendfailedbatch number
            "skipped_count": self._skipped_count, # was filterskip dynamic number (DO_NOTHING)
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes, # each buffer large small
            "running": self._running,
        }


class ZepGraphMemoryManager:
    """
     many simulationZepgraphmemoryupdate
    
    eachsimulation can to has self self updateinstance
    """
    
    _updaters: Dict[str, ZepGraphMemoryUpdater] = {}
    _lock = threading.Lock()
    
    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> ZepGraphMemoryUpdater:
        """
         as simulationcreategraphmemoryupdate
        
        Args:
            simulation_id: simulationID
            graph_id: ZepgraphID
            
        Returns:
            ZepGraphMemoryUpdaterinstance
        """
        with cls._lock:
            # if already exists in , stop old
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
            
            updater = ZepGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater
            
            logger.info(f"creategraphmemoryupdate: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater
    
    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[ZepGraphMemoryUpdater]:
        """ fetch simulationupdate"""
        return cls._updaters.get(simulation_id)
    
    @classmethod
    def stop_updater(cls, simulation_id: str):
        """stopremovesimulationupdate"""
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f" already stopgraphmemoryupdate: simulation_id={simulation_id}")
    
    # prevent stop_all duplicatecall mark log
    _stop_all_done = False
    
    @classmethod
    def stop_all(cls):
        """stopallupdate"""
        # prevent duplicatecall
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        
        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"stopupdatefailed: simulation_id={simulation_id}, error={e}")
                cls._updaters.clear()
            logger.info(" already stopallgraphmemoryupdate")
    
    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """ fetch allupdatestatisticsinfo"""
        return {
            sim_id: updater.get_stats() 
            for sim_id, updater in cls._updaters.items()
        }
