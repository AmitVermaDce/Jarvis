"""
graph buildingingservice
API2: using Zep API structure Standalone Graph
"""

import os
import uuid
import time
import threading
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

import httpx
from zep_cloud.client import Zep
from zep_cloud import EpisodeData, EntityEdgeSourceTarget

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from .text_processor import TextProcessor
from ..utils.locale import t, get_locale, set_locale


@dataclass
class GraphInfo:
    """graphinfo"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    graph buildingingservice
    callZep API structure knowledge graph
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY not configured")
        
        self.client = Zep(api_key=self.api_key)
        self.task_manager = TaskManager()
    
    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "Jarvis Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        async structure graph
        
        Args:
            text: inputtext
            ontology: ontologydefinition( from self API1output)
            graph_name: graphname
            chunk_size: text block large small
            chunk_overlap: block large small
            batch_size: each send block number amount
            
        Returns:
            taskID
        """
        # createtask
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # in after thread in execute structure
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size, current_locale)
        )
        thread.daemon = True
        thread.start()
        
        return task_id
    
    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        locale: str = 'zh'
    ):
        """graph buildingingthread"""
        set_locale(locale)
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message=t('progress.startBuildingGraph')
            )
            
            # 1. creategraph
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=t('progress.graphCreated', graphId=graph_id)
            )
            
            # 2. settingsontology
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message=t('progress.ontologySet')
            )
            
            # 3. text divide block
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=t('progress.textSplit', count=total_chunks)
            )
            
            # 4. divide senddata
            episode_uuids = self.add_text_batches(
                graph_id, chunks, batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.4),  # 20-60%
                    message=msg
                )
            )
            
            # 5. waitingZepprocesscomplete
            self.task_manager.update_task(
                task_id,
                progress=60,
                message=t('progress.waitingZepProcess')
            )
            
            self._wait_for_episodes(
                episode_uuids,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=60 + int(prog * 0.3),  # 60-90%
                    message=msg
                )
            )
            
            # 6. fetch graphinfo
            self.task_manager.update_task(
                task_id,
                progress=90,
                message=t('progress.fetchingGraphInfo')
            )
            
            graph_info = self._get_graph_info(graph_id)
            
            # complete
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)
    
    def create_graph(self, name: str) -> str:
        """createZepgraph(publicmethod)"""
        graph_id = f"jarvis_{uuid.uuid4().hex[:16]}"
        
        self.client.graph.create(
            graph_id=graph_id,
            name=name,
            description="Jarvis Social Simulation Graph"
        )
        
        return graph_id
    
    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """settingsgraphontology(publicmethod)"""
        import warnings
        from typing import Optional
        from pydantic import Field
        from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel
        
        # control Pydantic v2 at Field(default=None) warning
        # this is Zep SDK need method , warning from autoclasscreate, can to safe all ignore
        warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')
        
        # Zep protect name, not can as attribute name
        RESERVED_NAMES = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}
        
        def safe_attr_name(attr_name: str) -> str:
            """ will protect nameconvert as safe all name"""
            if attr_name.lower() in RESERVED_NAMES:
                return f"entity_{attr_name}"
            return attr_name
        
        # dynamic createentity types
        entity_types = {}
        for entity_def in ontology.get("entity_types", []):
            name = entity_def["name"]
            description = entity_def.get("description", f"A {name} entity.")
            
            # createattributedictionary and type parse (Pydantic v2 need to )
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in entity_def.get("attributes", []):
                # Handle malformed attributes: string, missing 'name', etc.
                if isinstance(attr_def, str):
                    attr_name = safe_attr_name(attr_def)
                    attr_desc = attr_def
                elif isinstance(attr_def, dict):
                    attr_name = attr_def.get("name") or attr_def.get("attribute") or attr_def.get("field")
                    if not attr_name:
                        logger.warning(f"Skipping attribute with no name in entity '{name}': {attr_def}")
                        continue
                    attr_name = safe_attr_name(attr_name)
                    attr_desc = attr_def.get("description", attr_name)
                else:
                    logger.warning(f"Skipping invalid attribute in entity '{name}': {attr_def}")
                    continue
                # Zep API need to Field description, this is required
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[EntityText] # type parse
            
            attrs["__annotations__"] = annotations
            
            # dynamic createclass
            entity_class = type(name, (EntityModel,), attrs)
            entity_class.__doc__ = description
            entity_types[name] = entity_class
        
        # dynamic createtype
        edge_definitions = {}
        for edge_def in ontology.get("edge_types", []):
            name = edge_def["name"]
            description = edge_def.get("description", f"A {name} relationship.")
            
            # createattributedictionary and type parse
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in edge_def.get("attributes", []):
                # Handle malformed attributes: string, missing 'name', etc.
                if isinstance(attr_def, str):
                    attr_name = safe_attr_name(attr_def)
                    attr_desc = attr_def
                elif isinstance(attr_def, dict):
                    attr_name = attr_def.get("name") or attr_def.get("attribute") or attr_def.get("field")
                    if not attr_name:
                        logger.warning(f"Skipping attribute with no name in edge '{name}': {attr_def}")
                        continue
                    attr_name = safe_attr_name(attr_name)
                    attr_desc = attr_def.get("description", attr_name)
                else:
                    logger.warning(f"Skipping invalid attribute in edge '{name}': {attr_def}")
                    continue
                # Zep API need to Field description, this is required
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[str] # attributestrtype
            
            attrs["__annotations__"] = annotations
            
            # dynamic createclass
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            edge_class = type(class_name, (EdgeModel,), attrs)
            edge_class.__doc__ = description
            
            # structure source_targets
            source_targets = []
            for st in edge_def.get("source_targets", []):
                source_targets.append(
                    EntityEdgeSourceTarget(
                        source=st.get("source", "Entity"),
                        target=st.get("target", "Entity")
                    )
                )
            
            if source_targets:
                edge_definitions[name] = (edge_class, source_targets)
        
        # callZep APIsettingsontology
        if entity_types or edge_definitions:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    self.client.graph.set_ontology(
                        graph_ids=[graph_id],
                        entities=entity_types if entity_types else None,
                        edges=edge_definitions if edge_definitions else None,
                    )
                    break
                except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError, ConnectionError, OSError) as e:
                    if attempt < MAX_RETRIES:
                        logger.warning(f"set_ontology attempt {attempt}/{MAX_RETRIES} failed: {e}. Retrying in {RETRY_DELAY * attempt}s...")
                        time.sleep(RETRY_DELAY * attempt)
                    else:
                        logger.error(f"set_ontology failed after {MAX_RETRIES} attempts: {e}")
                        raise
    
    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """ divide addtext to graph, return all episode uuid list"""
        episode_uuids = []
        total_chunks = len(chunks)
        
        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size
            
            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    t('progress.sendingBatch', current=batch_num, total=total_batches, chunks=len(batch_chunks)),
                    progress
                )
            
            # structure episodedata
            episodes = [
                EpisodeData(data=chunk, type="text")
                for chunk in batch_chunks
            ]
            
            # send to Zep (with retry for transient SSL/network errors)
            try:
                batch_result = None
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        batch_result = self.client.graph.add_batch(
                            graph_id=graph_id,
                            episodes=episodes
                        )
                        break
                    except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError, ConnectionError, OSError) as e:
                        if attempt < MAX_RETRIES:
                            logger.warning(f"add_batch attempt {attempt}/{MAX_RETRIES} failed: {e}. Retrying in {RETRY_DELAY * attempt}s...")
                            time.sleep(RETRY_DELAY * attempt)
                        else:
                            raise
                
                # collect return episode uuid
                if batch_result and isinstance(batch_result, list):
                    for ep in batch_result:
                        ep_uuid = getattr(ep, 'uuid_', None) or getattr(ep, 'uuid', None)
                        if ep_uuid:
                            episode_uuids.append(ep_uuid)
                
                # avoid exempt request past fast
                time.sleep(1)
                
            except Exception as e:
                if progress_callback:
                    progress_callback(t('progress.batchFailed', batch=batch_num, error=str(e)), 0)
                raise
        
        return episode_uuids
    
    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600
    ):
        """waitingall episode processcomplete( through past queryeach episode processed status)"""
        if not episode_uuids:
            if progress_callback:
                progress_callback(t('progress.noEpisodesWait'), 1.0)
            return
        
        start_time = time.time()
        pending_episodes = set(episode_uuids)
        completed_count = 0
        total_episodes = len(episode_uuids)
        
        if progress_callback:
            progress_callback(t('progress.waitingEpisodes', count=total_episodes), 0)
        
        while pending_episodes:
            if time.time() - start_time > timeout:
                if progress_callback:
                    progress_callback(
                        t('progress.episodesTimeout', completed=completed_count, total=total_episodes),
                        completed_count / total_episodes
                    )
                break
            
            # check each episode processstatus
            for ep_uuid in list(pending_episodes):
                try:
                    episode = self.client.graph.episode.get(uuid_=ep_uuid)
                    is_processed = getattr(episode, 'processed', False)
                    
                    if is_processed:
                        pending_episodes.remove(ep_uuid)
                        completed_count += 1
                        
                except Exception as e:
                    # ignore queryerror, continue
                    pass
            
            elapsed = int(time.time() - start_time)
            if progress_callback:
                progress_callback(
                    t('progress.zepProcessing', completed=completed_count, total=total_episodes, pending=len(pending_episodes), elapsed=elapsed),
                    completed_count / total_episodes if total_episodes > 0 else 0
                )
            
            if pending_episodes:
                time.sleep(3) # each 3 second check one times
        
        if progress_callback:
            progress_callback(t('progress.processingComplete', completed=completed_count, total=total_episodes), 1.0)
    
    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """ fetch graphinfo"""
        # fetch node( divide )
        nodes = fetch_all_nodes(self.client, graph_id)

        # fetch ( divide )
        edges = fetch_all_edges(self.client, graph_id)

        # statisticsentity types
        entity_types = set()
        for node in nodes:
            if node.labels:
                for label in node.labels:
                    if label not in ["Entity", "Node"]:
                        entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types)
        )
    
    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
         fetch completegraphdata(containdetailedinfo)
        
        Args:
            graph_id: graphID
            
        Returns:
            containnodes and edgesdictionary, package time space info, attributedetaileddata
        """
        nodes = fetch_all_nodes(self.client, graph_id)
        edges = fetch_all_edges(self.client, graph_id)

        # createnodemapping at fetch nodename
        node_map = {}
        for node in nodes:
            node_map[node.uuid_] = node.name or ""
        
        nodes_data = []
        for node in nodes:
            # fetch create time space
            created_at = getattr(node, 'created_at', None)
            if created_at:
                created_at = str(created_at)
            
            nodes_data.append({
                "uuid": node.uuid_,
                "name": node.name,
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
                "created_at": created_at,
            })
        
        edges_data = []
        for edge in edges:
            # fetch time space info
            created_at = getattr(edge, 'created_at', None)
            valid_at = getattr(edge, 'valid_at', None)
            invalid_at = getattr(edge, 'invalid_at', None)
            expired_at = getattr(edge, 'expired_at', None)
            
            # fetch episodes
            episodes = getattr(edge, 'episodes', None) or getattr(edge, 'episode_ids', None)
            if not isinstance(episodes, list):
                episodes = [str(episodes)]
            elif episodes:
                episodes = [str(e) for e in episodes]
            
            # fetch fact_type
            fact_type = getattr(edge, 'fact_type', None) or edge.name or ""
            
            edges_data.append({
                "uuid": edge.uuid_,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "fact_type": fact_type,
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": node_map.get(edge.source_node_uuid, ""),
                "target_node_name": node_map.get(edge.target_node_uuid, ""),
                "attributes": edge.attributes or {},
                "created_at": str(created_at) if created_at else None,
                "valid_at": str(valid_at) if valid_at else None,
                "invalid_at": str(invalid_at) if invalid_at else None,
                "expired_at": str(expired_at) if expired_at else None,
                "episodes": episodes or [],
            })
        
        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }
    
    def delete_graph(self, graph_id: str):
        """deletegraph"""
        self.client.graph.delete(graph_id=graph_id)

