"""
Zepentity reading fetch and filterservice
 from Zepgraph in read fetch node, exit symbol definitionentity typesnode
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('jarvis.zep_entity_reader')

# at type return type
T = TypeVar('T')


@dataclass
class EntityNode:
    """entitynodedata structure"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    # relatedinfo
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    # related its nodeinfo
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }
    
    def get_entity_type(self) -> Optional[str]:
        """ fetch entity types(excludedefaultEntitylabel)"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """filter after entity set """
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    Zepentity reading fetch and filterservice
    
    mainfeature:
    1. from Zepgraph read fetch allnode
    2. exit symbol definitionentity typesnode(Labels not only is Entitynode)
    3. fetch eachentityrelated and associatednodeinfo
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY not configured")
        
        self.client = Zep(api_key=self.api_key)
    
    def _call_with_retry(
        self, 
        func: Callable[[], T], 
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """
         with retry logic Zep APIcall
        
        Args:
            func: need executefunction( no parameterlambda or callable)
            operation_name: name, at log
            max_retries: maximum retry times number (default3 times , immediately most many test 3 times )
            initial_delay: initialdelay second number
            
        Returns:
            APIcall
        """
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} # {attempt + 1} times test failed: {str(e)[:100]}, "
                        f"{delay:.1f} second after retry..."
                    )
                    time.sleep(delay)
                    delay *= 2 # point number avoid
                else:
                    logger.error(f"Zep {operation_name} in {max_retries} times test after failed: {str(e)}")
        
        raise last_exception
    
    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
         fetch graphallnode( divide fetch )

        Args:
            graph_id: graphID

        Returns:
            nodelist
        """
        logger.info(f" fetch graph {graph_id} allnode...")

        nodes = fetch_all_nodes(self.client, graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f" fetch {len(nodes_data)} node")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
         fetch graphall( divide fetch )

        Args:
            graph_id: graphID

        Returns:
            list
        """
        logger.info(f" fetch graph {graph_id} all...")

        edges = fetch_all_edges(self.client, graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f" fetch {len(edges_data)} entries ")
        return edges_data
    
    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
         fetch point fixed nodeallrelated( with retry logic )
        
        Args:
            node_uuid: nodeUUID
            
        Returns:
            list
        """
        try:
            # using retry logic callZep API
            edges = self._call_with_retry(
                func=lambda: self.client.graph.node.get_entity_edges(node_uuid=node_uuid),
                operation_name=f" fetch node(node={node_uuid[:8]}...)"
            )
            
            edges_data = []
            for edge in edges:
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                    "attributes": edge.attributes or {},
                })
            
            return edges_data
        except Exception as e:
            logger.warning(f" fetch node {node_uuid} failed: {str(e)}")
            return []
    
    def filter_defined_entities(
        self, 
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
         exit symbol definitionentity typesnode
        
        logic:
        - ifnodeLabels only has one "Entity", description this entity not symbol definitiontype, skip
        - ifnodeLabelscontain"Entity" and "Node" outside label, description symbol definitiontype, protect
        
        Args:
            graph_id: graphID
            defined_entity_types: definitionentity typeslist(optional, if provide then only protect this some type)
            enrich_with_edges: is else fetch eachentityrelatedinfo
            
        Returns:
            FilteredEntities: filter after entity set
        """
        logger.info(f"startgraph {graph_id} entity...")
        
        # fetch allnode
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        
        # fetch all( at after continue associated check find )
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        
        # structure nodeUUID to nodedatamapping
        node_map = {n["uuid"]: n for n in all_nodes}
        
        # symbol conditionentity
        filtered_entities = []
        entity_types_found = set()
        
        for node in all_nodes:
            labels = node.get("labels", [])
            
            # logic: Labelsmustcontain"Entity" and "Node" outside label
            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]
            
            if not custom_labels:
                # only has defaultlabel, skip
                continue
            
            # if point fixed definitiontype, check is else match
            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]
            
            entity_types_found.add(entity_type)
            
            # createentitynodeobject
            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )
            
            # fetch related and node
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()
                
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])
                
                entity.related_edges = related_edges
                
                # fetch associatednodeinfo
                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })
                
                entity.related_nodes = related_nodes
            
            filtered_entities.append(entity)
        
        logger.info(f"complete: node {total_count}, symbol condition {len(filtered_entities)}, "
                   f"entity types: {entity_types_found}")
        
        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )
    
    def get_entity_with_context(
        self, 
        graph_id: str, 
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
         fetch entity and its completecontext( and associatednode, with retry logic )
        
        Args:
            graph_id: graphID
            entity_uuid: entityUUID
            
        Returns:
            EntityNode or None
        """
        try:
            # using retry logic fetch node
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=entity_uuid),
                operation_name=f" fetch nodedetails(uuid={entity_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
            # fetch node
            edges = self.get_node_edges(entity_uuid)
            
            # fetch allnode at associated check find
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}
            
            # processrelated and node
            related_edges = []
            related_node_uuids = set()
            
            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])
            
            # fetch associatednodeinfo
            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })
            
            return EntityNode(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )
            
        except Exception as e:
            logger.error(f" fetch entity {entity_uuid} failed: {str(e)}")
            return None
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
         fetch point fixed typeallentity
        
        Args:
            graph_id: graphID
            entity_type: entity types( if "Student", "PublicFigure" )
            enrich_with_edges: is else fetch relatedinfo
            
        Returns:
            entitylist
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities


