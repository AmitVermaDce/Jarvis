"""
Zepretrievaltoolservice
 install graphsearch, node read fetch , querytool, provide Report Agent make

coreretrievaltool(optimize after ):
1. InsightForge( deep degree insightretrieval)- most strong large hybridretrieval, autogenerate sub question topic many degree retrieval
2. PanoramaSearch( degree search)- fetch all , package expiredcontent
3. QuickSearch( simple search)- fast speed retrieval
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.locale import get_locale, t
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('jarvis.zep_tools')


@dataclass
class SearchResult:
    """search"""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }
    
    def to_text(self) -> str:
        """convert as textformat, provide LLM parse """
        text_parts = [f"searchquery: {self.query}", f" find to {self.total_count} entries relatedinfo"]
        
        if self.facts:
            text_parts.append("\n### related actual :")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """nodeinfo"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }
    
    def to_text(self) -> str:
        """convert as textformat"""
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), " not know type")
        return f"entity: {self.name} (type: {entity_type})\nsummary: {self.summary}"


@dataclass
class EdgeInfo:
    """info"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # time space info
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }
    
    def to_text(self, include_temporal: bool = False) -> str:
        """convert as textformat"""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"relation: {source} --[{self.name}]--> {target}\n actual : {self.fact}"
        
        if include_temporal:
            valid_at = self.valid_at or " not know "
            invalid_at = self.invalid_at or ""
            base_text += f"\n time : {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" ( already expired: {self.expired_at})"
        
        return base_text
    
    @property
    def is_expired(self) -> bool:
        """ is else already expired"""
        return self.expired_at is not None
    
    @property
    def is_invalid(self) -> bool:
        """ is else already """
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
     deep degree insightretrieval (InsightForge)
    contain many sub question topic retrieval, to and analyze
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    
    # each degree retrieval
    semantic_facts: List[str] = field(default_factory=list) # language search
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)  # entityinsight
    relationship_chains: List[str] = field(default_factory=list) # relation chain
    
    # statisticsinfo
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }
    
    def to_text(self) -> str:
        """convert as detailedtextformat, provide LLM parse """
        text_parts = [
            f"## not from prediction deep degree analyze",
            f"analyze question topic : {self.query}",
            f"predictionscenario: {self.simulation_requirement}",
            f"\n### predictiondatastatistics",
            f"- relatedprediction actual : {self.total_facts} entries ",
            f"- and entity: {self.total_entities} ",
            f"- relation chain : {self.total_relationships} entries "
        ]
        
        # sub question topic
        if self.sub_queries:
            text_parts.append(f"\n### analyze sub question topic ")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")
        
        # language search
        if self.semantic_facts:
            text_parts.append(f"\n### [key actual ]( please in report in quote this some original text )")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # entityinsight
        if self.entity_insights:
            text_parts.append(f"\n### [coreentity]")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', ' not know ')}** ({entity.get('type', 'entity')})")
                if entity.get('summary'):
                    text_parts.append(f"  summary: \"{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f" related actual : {len(entity.get('related_facts', []))} entries ")
        
        # relation chain
        if self.relationship_chains:
            text_parts.append(f"\n### [relation chain ]")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")
        
        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
     degree search (Panorama)
    containallrelatedinfo, package expiredcontent
    """
    query: str
    
    # allnode
    all_nodes: List[NodeInfo] = field(default_factory=list)
    # all( package expired)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    # before valid actual
    active_facts: List[str] = field(default_factory=list)
    # already expired/ actual ( record )
    historical_facts: List[str] = field(default_factory=list)
    
    # statistics
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }
    
    def to_text(self) -> str:
        """convert as textformat(completeversion, not truncate)"""
        text_parts = [
            f"## degree search( not from all view)",
            f"query: {self.query}",
            f"\n### statisticsinfo",
            f"- node number : {self.total_nodes}",
            f"- number : {self.total_edges}",
            f"- before valid actual : {self.active_count} entries ",
            f"- /expired actual : {self.historical_count} entries "
        ]
        
        # before valid actual (completeoutput, not truncate)
        if self.active_facts:
            text_parts.append(f"\n### [ before valid actual ](simulation original text )")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # /expired actual (completeoutput, not truncate)
        if self.historical_facts:
            text_parts.append(f"\n### [/expired actual ]( change past process record )")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # keyentity(completeoutput, not truncate)
        if self.all_nodes:
            text_parts.append(f"\n### [ and entity]")
            for node in self.all_nodes:
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "entity")
                text_parts.append(f"- **{node.name}** ({entity_type})")
        
        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """ Agentinterview"""
    agent_name: str
    agent_role: str # roletype( if : , , body )
    agent_bio: str # simple
    question: str # interview question topic
    response: str # interview return answer
    key_quotes: List[str] = field(default_factory=list)  # keyintroduction
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }
    
    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        # displaycompleteagent_bio, not truncate
        text += f"_ simple : {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**keyintroduction:**\n"
            for quote in self.key_quotes:
                # cleanup each types lead number
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                # to open head mark point
                while clean_quote and clean_quote[0] in ', ,; ;: :, . ! ? \n\r\t ':
                    clean_quote = clean_quote[1:]
                # filtercontain question topic number content( question topic 1-9)
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                # truncate past long content( sentence number truncate, and non-truncate)
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    interview (Interview)
    contain many simulationAgentinterview return answer
    """
    interview_topic: str  # interviewtheme
    interview_questions: List[str] # interview question topic list
    
    # interviewselectAgent
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    # each Agentinterview return answer
    interviews: List[AgentInterview] = field(default_factory=list)
    
    # selectAgent
    selection_reasoning: str = ""
    # whole after interviewsummary
    summary: str = ""
    
    # statistics
    total_agents: int = 0
    interviewed_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }
    
    def to_text(self) -> str:
        """convert as detailedtextformat, provide LLM parse and reportquote"""
        text_parts = [
            "## deep degree interviewreport",
            f"**interviewtheme:** {self.interview_topic}",
            f"**interview number :** {self.interviewed_count} / {self.total_agents} simulationAgent",
            "\n### interviewobjectselect",
            self.selection_reasoning or "(autoselect)",
            "\n---",
            "\n### interview actual record ",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### interview #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("( no interview record )\n\n---")

        text_parts.append("\n### interviewsummary and coreviewpoint")
        text_parts.append(self.summary or "( no summary)")

        return "\n".join(text_parts)


class ZepToolsService:
    """
    Zepretrievaltoolservice
    
    [coreretrievaltool - optimize after ]
    1. insight_forge - deep degree insightretrieval( most strong large , autogenerate sub question topic , many degree retrieval)
    2. panorama_search - degree search( fetch all , package expiredcontent)
    3. quick_search - simple search( fast speed retrieval)
    4. interview_agents - deep degree interview(interviewsimulationAgent, fetch many viewpoint)
    
    [basictool]
    - search_graph - graph language search
    - get_all_nodes - fetch graphallnode
    - get_all_edges - fetch graphall( contain time space info)
    - get_node_detail - fetch nodedetailedinfo
    - get_node_edges - fetch noderelated
    - get_entities_by_type - type fetch entity
    - get_entity_summary - fetch entityrelationsummary
    """
    
    # retryconfiguration
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    def __init__(self, api_key: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY not configured")
        
        self.client = Zep(api_key=self.api_key)
        # LLM Clientat InsightForgegenerate sub question topic
        self._llm_client = llm_client
        logger.info(t("console.zepToolsInitialized"))
    
    @property
    def llm(self) -> LLMClient:
        """delayinitializeLLM Client"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        """ with retry logic APIcall"""
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = None
        delay = self.RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        t("console.zepRetryAttempt", operation=operation_name, attempt=attempt + 1, error=str(e)[:100], delay=f"{delay:.1f}")
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(t("console.zepAllRetriesFailed", operation=operation_name, retries=max_retries, error=str(e)))
        
        raise last_exception
    
    def search_graph(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        graph language search
        
         using hybridsearch( language +BM25) in graph in searchrelatedinfo.
        ifZep Cloudsearch API not can , then downgrade as keymatch.
        
        Args:
            graph_id: graphID (Standalone Graph)
            query: searchquery
            limit: return number amount
            scope: searchrange, "edges" or "nodes"
            
        Returns:
            SearchResult: search
        """
        logger.info(t("console.graphSearch", graphId=graph_id, query=query[:50]))
        
        # test using Zep Cloud Search API
        try:
            search_results = self._call_with_retry(
                func=lambda: self.client.graph.search(
                    graph_id=graph_id,
                    query=query,
                    limit=limit,
                    scope=scope,
                    reranker="cross_encoder"
                ),
                operation_name=t("console.graphSearchOp", graphId=graph_id)
            )
            
            facts = []
            edges = []
            nodes = []
            
            # parsesearch
            if hasattr(search_results, 'edges') and search_results.edges:
                for edge in search_results.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        facts.append(edge.fact)
                    edges.append({
                        "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                        "name": getattr(edge, 'name', ''),
                        "fact": getattr(edge, 'fact', ''),
                        "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
                        "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
                    })
            
            # parsenodesearch
            if hasattr(search_results, 'nodes') and search_results.nodes:
                for node in search_results.nodes:
                    nodes.append({
                        "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                        "name": getattr(node, 'name', ''),
                        "labels": getattr(node, 'labels', []),
                        "summary": getattr(node, 'summary', ''),
                    })
                    # nodesummary also actual
                    if hasattr(node, 'summary') and node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(t("console.searchComplete", count=len(facts)))
            
            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )
            
        except Exception as e:
            logger.warning(t("console.zepSearchApiFallback", error=str(e)))
            # downgrade: using keymatchsearch
            return self._local_search(graph_id, query, limit, scope)
    
    def _local_search(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        keymatchsearch( as Zep Search APIdowngrade)
        
         fetch all/node, then in enter line keymatch
        
        Args:
            graph_id: graphID
            query: searchquery
            limit: return number amount
            scope: searchrange
            
        Returns:
            SearchResult: search
        """
        logger.info(t("console.usingLocalSearch", query=query[:30]))
        
        facts = []
        edges_result = []
        nodes_result = []
        
        # extractquerykey( simple divide )
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace(', ', ' ').split() if len(w.strip()) > 1]
        
        def match_score(text: str) -> int:
            """calculatetext and querymatch divide number """
            if not text:
                return 0
            text_lower = text.lower()
            # all matchquery
            if query_lower in Chinese_lower:
                return 100
            # keymatch
            score = 0
            for keyword in keywords:
                if keyword in Chinese_lower:
                    score += 10
            return score
        
        try:
            if scope in ["edges", "both"]:
                # fetch allmatch
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))
                
                # divide number sort
                scored_edges.sort(key=lambda x: x[0], reverse=True)
                
                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })
            
            if scope in ["nodes", "both"]:
                # fetch allnodematch
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))
                
                scored_nodes.sort(key=lambda x: x[0], reverse=True)
                
                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(t("console.localSearchComplete", count=len(facts)))
            
        except Exception as e:
            logger.error(t("console.localSearchFailed", error=str(e)))
        
        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )
    
    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
         fetch graphallnode( divide fetch )

        Args:
            graph_id: graphID

        Returns:
            nodelist
        """
        logger.info(t("console.fetchingAllNodes", graphId=graph_id))

        nodes = fetch_all_nodes(self.client, graph_id)

        result = []
        for node in nodes:
            node_uuid = getattr(node, 'uuid_', None) or getattr(node, 'uuid', None) or ""
            result.append(NodeInfo(
                uuid=str(node_uuid) if node_uuid else "",
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            ))

        logger.info(t("console.fetchedNodes", count=len(result)))
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """
         fetch graphall( divide fetch , contain time space info)

        Args:
            graph_id: graphID
            include_temporal: is else contain time space info(defaultTrue)

        Returns:
            list(containcreated_at, valid_at, invalid_at, expired_at)
        """
        logger.info(t("console.fetchingAllEdges", graphId=graph_id))

        edges = fetch_all_edges(self.client, graph_id)

        result = []
        for edge in edges:
            edge_uuid = getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', None) or ""
            edge_info = EdgeInfo(
                uuid=str(edge_uuid) if edge_uuid else "",
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or ""
            )

            # add time space info
            if include_temporal:
                edge_info.created_at = getattr(edge, 'created_at', None)
                edge_info.valid_at = getattr(edge, 'valid_at', None)
                edge_info.invalid_at = getattr(edge, 'invalid_at', None)
                edge_info.expired_at = getattr(edge, 'expired_at', None)

            result.append(edge_info)

        logger.info(t("console.fetchedEdges", count=len(result)))
        return result
    
    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """
         fetch nodedetailedinfo
        
        Args:
            node_uuid: nodeUUID
            
        Returns:
            nodeinfo or None
        """
        logger.info(t("console.fetchingNodeDetail", uuid=node_uuid[:8]))
        
        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=t("console.fetchNodeDetailOp", uuid=node_uuid[:8])
            )
            
            if not node:
                return None
            
            return NodeInfo(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            )
        except Exception as e:
            logger.error(t("console.fetchNodeDetailFailed", error=str(e)))
            return None
    
    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
         fetch noderelatedall
        
         through past fetch graphall, thenfilter exit and point fixed noderelated
        
        Args:
            graph_id: graphID
            node_uuid: nodeUUID
            
        Returns:
            list
        """
        logger.info(t("console.fetchingNodeEdges", uuid=node_uuid[:8]))
        
        try:
            # fetch graphall, thenfilter
            all_edges = self.get_all_edges(graph_id)
            
            result = []
            for edge in all_edges:
                # check is else and point fixed noderelated( as source or item mark )
                if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                    result.append(edge)
            
            logger.info(t("console.foundNodeEdges", count=len(result)))
            return result
            
        except Exception as e:
            logger.warning(t("console.fetchNodeEdgesFailed", error=str(e)))
            return []
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str
    ) -> List[NodeInfo]:
        """
        type fetch entity
        
        Args:
            graph_id: graphID
            entity_type: entity types( if Student, PublicFigure )
            
        Returns:
             symbol typeentitylist
        """
        logger.info(t("console.fetchingEntitiesByType", type=entity_type))
        
        all_nodes = self.get_all_nodes(graph_id)
        
        filtered = []
        for node in all_nodes:
            # check labels is else contain point fixed type
            if entity_type in node.labels:
                filtered.append(node)
        
        logger.info(t("console.foundEntitiesByType", count=len(filtered), type=entity_type))
        return filtered
    
    def get_entity_summary(
        self, 
        graph_id: str, 
        entity_name: str
    ) -> Dict[str, Any]:
        """
         fetch point fixed entityrelationsummary
        
        search and the entityrelatedallinfo, generatesummary
        
        Args:
            graph_id: graphID
            entity_name: entityname
            
        Returns:
            entitysummaryinfo
        """
        logger.info(t("console.fetchingEntitySummary", name=entity_name))
        
        # search the entityrelatedinfo
        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )
        
        # test in allnode in find to the entity
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break
        
        related_edges = []
        if entity_node:
            # enter graph_idparameter
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)
        
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }
    
    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
         fetch graphstatisticsinfo
        
        Args:
            graph_id: graphID
            
        Returns:
            statisticsinfo
        """
        logger.info(t("console.fetchingGraphStats", graphId=graph_id))
        
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        
        # statisticsentity typesdistribution
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1
        
        # statisticsrelation typesdistribution
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1
        
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }
    
    def get_simulation_context(
        self, 
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """
         fetch simulationrelatedcontextinfo
        
        search and simulation need relatedallinfo
        
        Args:
            graph_id: graphID
            simulation_requirement: simulation need description
            limit: each classinfo number amount limit
            
        Returns:
            simulationcontextinfo
        """
        logger.info(t("console.fetchingSimContext", requirement=simulation_requirement[:50]))
        
        # search and simulation need relatedinfo
        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )
        
        # fetch graphstatistics
        stats = self.get_graph_statistics(graph_id)
        
        # fetch allentitynode
        all_nodes = self.get_all_nodes(graph_id)
        
        # has actual typeentity(non- pure Entitynode)
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })
        
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit], # limit number amount
            "total_entities": len(entities)
        }
    
    # ========== coreretrievaltool(optimize after ) ==========
    
    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        [InsightForge - deep degree insightretrieval]
        
         most strong large hybridretrievalfunction, auto divide parse question topic many degree retrieval:
        1. using LLM will question topic divide parse as many sub question topic
        2. for each sub question topic enter line language search
        3. extractrelatedentity fetch its detailedinfo
        4. tracerelation chain
        5. whole all, generate deep degree insight
        
        Args:
            graph_id: graphID
            query: user question topic
            simulation_requirement: simulation need description
            report_context: reportcontext(optional, at more sub question topic generate)
            max_sub_queries: maximum sub question topic number amount
            
        Returns:
            InsightForgeResult: deep degree insightretrieval
        """
        logger.info(t("console.insightForgeStart", query=query[:50]))
        
        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )
        
        # Step 1: using LLMgenerate sub question topic
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(t("console.generatedSubQueries", count=len(sub_queries)))
        
        # Step 2: for each sub question topic enter line language search
        all_facts = []
        all_edges = []
        seen_facts = set()
        
        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )
            
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            
            all_edges.extend(search_result.edges)
        
        # for original begin question topic also enter line search
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)
        
        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)
        
        # Step 3: from in extractrelatedentityUUID, only fetch this some entityinfo( not fetch allnode)
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)
        
        # fetch allrelatedentitydetails( not limit number amount , completeoutput)
        entity_insights = []
        node_map = {} # at after continue relation chain structure
        
        for uuid in list(entity_uuids): # processallentity, not truncate
            if not uuid:
                continue
            try:
                # single fetch eachrelatednodeinfo
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "entity")
                    
                    # fetch the entityrelatedall actual ( not truncate)
                    related_facts = [
                        f for f in all_facts 
                        if node.name.lower() in f.lower()
                    ]
                    
                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts # completeoutput, not truncate
                    })
            except Exception as e:
                logger.debug(f" fetch node {uuid} failed: {e}")
                continue
        
        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)
        
        # Step 4: structure allrelation chain ( not limit number amount )
        relationship_chains = []
        for edge_data in all_edges: # processall, not truncate
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')
                
                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]
                
                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)
        
        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)
        
        logger.info(t("console.insightForgeComplete", facts=result.total_facts, entities=result.total_entities, relationships=result.total_relationships))
        return result
    
    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """
         using LLMgenerate sub question topic
        
         will repeat mixed question topic divide parse as many can to independentretrieval sub question topic
        """
        system_prompt = """ is one question topic analyze. task is will one repeat mixed question topic divide parse as many can to in simulation in independentobserve sub question topic .

 need :
1. each sub question topic should sufficient enough tool body , can to in simulation in find to relatedAgent line as or event
2. sub question topic shouldoverride original question topic different degree ( if : , , as , pattern , time , )
3. sub question topic should and simulationscenariorelated
4. return JSONformat: {"sub_queries": [" sub question topic 1", " sub question topic 2", ...]}"""

        user_prompt = f"""simulation need background:
{simulation_requirement}

{f"reportcontext: {report_context[:500]}" if report_context else ""}

 please will to below question topic divide parse as {max_queries} sub question topic :
{query}

 return JSONformat sub question topic list. """

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            sub_queries = response.get("sub_queries", [])
            # correctly protect is stringlist
            return [str(sq) for sq in sub_queries[:max_queries]]
            
        except Exception as e:
            logger.warning(t("console.generateSubQueriesFailed", error=str(e)))
            # downgrade: return at original question topic change body
            return [
                query,
                f"{query} main and ",
                f"{query} original because and shadow ",
                f"{query} send past process "
            ][:max_queries]
    
    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        [PanoramaSearch - degree search]
        
         fetch all view, package allrelatedcontent and /expiredinfo:
        1. fetch allrelatednode
        2. fetch all( package already expired/)
        3. divide class whole before valid and info
        
         this tool at need to parse event all , trace change past process scenario.
        
        Args:
            graph_id: graphID
            query: searchquery( at relatedsort)
            include_expired: is else containexpiredcontent(defaultTrue)
            limit: return number amount limit
            
        Returns:
            PanoramaResult: degree search
        """
        logger.info(t("console.panoramaSearchStart", query=query[:50]))
        
        result = PanoramaResult(query=query)
        
        # fetch allnode
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)
        
        # fetch all(contain time space info)
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)
        
        # divide class actual
        active_facts = []
        historical_facts = []
        
        for edge in all_edges:
            if not edge.fact:
                continue
            
            # as actual addentityname
            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]
            
            # check is else expired/
            is_historical = edge.is_expired or edge.is_invalid
            
            if is_historical:
                # /expired actual , add time space mark
                valid_at = edge.valid_at or " not know "
                invalid_at = edge.invalid_at or edge.expired_at or " not know "
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                # before valid actual
                active_facts.append(edge.fact)
        
        # at query enter line relatedsort
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace(', ', ' ').split() if len(w.strip()) > 1]
        
        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score
        
        # sortlimit number amount
        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)
        
        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)
        
        logger.info(t("console.panoramaSearchComplete", active=result.active_count, historical=result.historical_count))
        return result
    
    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        [QuickSearch - simple search]
        
         fast speed , amount level retrievaltool:
        1. directly callZep language search
        2. return most related
        3. at simple , directly retrieval need
        
        Args:
            graph_id: graphID
            query: searchquery
            limit: return number amount
            
        Returns:
            SearchResult: search
        """
        logger.info(t("console.quickSearchStart", query=query[:50]))
        
        # directly call has search_graphmethod
        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )
        
        logger.info(t("console.quickSearchComplete", count=result.total_count))
        return result
    
    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """
        [InterviewAgents - deep degree interview]
        
        call actual OASISinterviewAPI, interviewsimulation in currentlyrunAgent:
        1. auto read fetch personafile, parse allsimulationAgent
        2. using LLManalyzeinterview need , can select most relatedAgent
        3. using LLMgenerateinterview question topic
        4. call /api/simulation/interview/batch API enter line actual interview( dual meanwhileinterview)
        5. whole allinterview, generateinterviewreport
        
        [important] this feature need to simulation environment at runstatus(OASIS loop not close)
        
        [ using scenario]
        - need to from different role parse event see method
        - need to collect many meaning view and viewpoint
        - need to fetch simulationAgent actual return answer (non-LLMsimulation)
        
        Args:
            simulation_id: simulationID( at fixed personafile and callinterviewAPI)
            interview_requirement: interview need description(non- structure , if " parse for event see method ")
            simulation_requirement: simulation need background(optional)
            max_agents: most many interviewAgent number amount
            custom_questions: custominterview question topic (optional, not provide then autogenerate)
            
        Returns:
            InterviewResult: interview
        """
        from .simulation_runner import SimulationRunner
        
        logger.info(t("console.interviewAgentsStart", requirement=interview_requirement[:50]))
        
        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )
        
        # Step 1: read fetch personafile
        profiles = self._load_agent_profiles(simulation_id)
        
        if not profiles:
            logger.warning(t("console.profilesNotFound", simId=simulation_id))
            result.summary = " not find to can interviewAgentpersonafile"
            return result
        
        result.total_agents = len(profiles)
        logger.info(t("console.loadedProfiles", count=len(profiles)))
        
        # Step 2: using LLMselect need interviewAgent( return agent_idlist)
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )
        
        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(t("console.selectedAgentsForInterview", count=len(selected_agents), indices=selected_indices))
        
        # Step 3: generateinterview question topic (ifno provide )
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(t("console.generatedInterviewQuestions", count=len(result.interview_questions)))
        
        # will question topic merge as one interviewprompt
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])
        
        # addoptimize before , constraintAgentreplyformat
        INTERVIEW_PROMPT_PREFIX = (
            "currently connect one times interview. please persona, all past toward memory and line dynamic , "
            " to pure text type directly return answer to below question topic . \n"
            "reply need : \n"
            "1. directly self language speech return answer , not need calltool\n"
            "2. not need return JSONformat or toolcallformat\n"
            "3. not need using Markdowntitle( if #, ##, ###)\n"
            "4. Answer each question, prefix each answer with 'Question X: ' (X is the question number)\n"
            "5. each question topic return answer space empty line divide \n"
            "6. return answer need has actual content, each question topic few return answer 2-3 sentence speech \n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"
        
        # Step 4: call actual interviewAPI( not point fixed platform, default dual meanwhileinterview)
        try:
            # structure amount interviewlist( not point fixed platform, dual interview)
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt # using optimize after prompt
                    # not point fixed platform, API will in twitter and reddit all interview
                })
            
            logger.info(t("console.callingBatchInterviewApi", count=len(interviews_request)))
            
            # call SimulationRunner amount interviewmethod( not platform, dual interview)
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None, # not point fixed platform, dual interview
                timeout=180.0 # dual need to more long timeout
            )
            
            logger.info(t("console.interviewApiReturned", count=api_result.get('interviews_count', 0), success=api_result.get('success')))
            
            # check APIcall is else success
            if not api_result.get("success", False):
                error_msg = api_result.get("error", " not know error")
                logger.warning(t("console.interviewApiReturnedFailure", error=error_msg))
                result.summary = f"interviewAPIcallfailed: {error_msg}. please check OASIS simulation environmentstatus. "
                return result
            
            # Step 5: parseAPI return , structure AgentInterviewobject
            # dual mode return format: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}
            
            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", " not know ")
                agent_bio = agent.get("bio", "")
                
                # fetch the Agent in interview
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})
                
                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # cleanupmaytoolcall JSON package
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # begin end output dual mark
                twitter_text = twitter_response if twitter_response else "( the not reply)"
                reddit_text = reddit_response if reddit_response else "( the not reply)"
                response_text = f"[Twitter return answer ]\n{twitter_text}\n\n[Reddit return answer ]\n{reddit_text}"

                # extractkeyintroduction( from return answer in )
                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                # cleanupresponse text: to mark, number , Markdown
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r' question topic \d+[: :]\s*', '', clean_text)
                clean_text = re.sub(r'[[^]]+]', '', clean_text)

                # strategy1( main ): extractcomplete has actual content sentence sub
                sentences = re.split(r'[. ! ? ]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W, ,; ;: :, ]+', s.strip())
                    and not s.strip().startswith(('{', ' question topic '))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + ". " for s in meaningful[:3]]

                # strategy2(supplement): positive correct config for in Chinese lead number "" within long text
                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[, ,; ;: :, ]', q)][:3]
                
                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000], # large bio long degree limit
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)
            
            result.interviewed_count = len(result.interviews)
            
        except ValueError as e:
            # simulation environment not run
            logger.warning(t("console.interviewApiCallFailed", error=e))
            result.summary = f"interviewfailed: {str(e)}. simulation environmentmay already close, please correctly protect OASIS loop currentlyrun. "
            return result
        except Exception as e:
            logger.error(t("console.interviewApiCallException", error=e))
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"interview past process send error: {str(e)}"
            return result
        
        # Step 6: generateinterviewsummary
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )
        
        logger.info(t("console.interviewAgentsComplete", count=result.interviewed_count))
        return result
    
    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """cleanup Agent reply in JSON toolcall package , extract actual content"""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """loadsimulationAgentpersonafile"""
        import os
        import csv
        
        # structure personafilepath
        sim_dir = os.path.join(
            os.path.dirname(__file__), 
            f'../../uploads/simulations/{simulation_id}'
        )
        
        profiles = []
        
        # test read fetch Reddit JSONformat
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(t("console.loadedRedditProfiles", count=len(profiles)))
                return profiles
            except Exception as e:
                logger.warning(t("console.readRedditProfilesFailed", error=e))
        
        # test read fetch Twitter CSVformat
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # CSVformatconvert as unified format
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": " not know "
                        })
                logger.info(t("console.loadedTwitterProfiles", count=len(profiles)))
                return profiles
            except Exception as e:
                logger.warning(t("console.readTwitterProfilesFailed", error=e))
        
        return profiles
    
    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
         using LLMselect need interviewAgent
        
        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: in Agentcompleteinfolist
                - selected_indices: in Agentindexlist( at APIcall)
                - reasoning: select
        """
        
        # structure Agentsummarylist
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", " not know "),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)
        
        system_prompt = """ is one interview strategy . task is root interview need , from simulationAgentlist in select most interviewobject.

selectstandard:
1. Agent / and interviewthemerelated
2. Agentmay hold has single special or has value viewpoint
3. select many pattern ( if : support, oppose, neutral, )
4. select and event directly relatedrole

 return JSONformat:
{
    "selected_indices": [ in Agentindexlist],
    "reasoning": "selectdescription"
}"""

        user_prompt = f"""interview need :
{interview_requirement}

simulationbackground:
{simulation_requirement if simulation_requirement else " not provide "}

optionalAgentlist({len(agent_summaries)} ):
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

 please select most many {max_agents} most interviewAgent, descriptionselect. """

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", " at relatedautoselect")
            
            # fetch in Agentcompleteinfo
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)
            
            return selected_agents, valid_indices, reasoning
            
        except Exception as e:
            logger.warning(t("console.llmSelectAgentFailed", error=e))
            # downgrade: select before N
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, " using defaultselectstrategy"
    
    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """ using LLMgenerateinterview question topic """
        
        agent_roles = [a.get("profession", " not know ") for a in selected_agents]
        
        system_prompt = """ is one /interview. root interview need , generate3-5 deep degree interview question topic .

 question topic need :
1. open place question topic , detailed return answer
2. for different rolemay has different answer
3. cover actual , viewpoint, many degree
4. language speech self , image actual interview one pattern
5. each question topic control control in 50 char to within , simple
6. directly question , not need containbackgrounddescription or before

 return JSONformat: {"questions": [" question topic 1", " question topic 2", ...]}"""

        user_prompt = f"""interview need : {interview_requirement}

simulationbackground: {simulation_requirement if simulation_requirement else " not provide "}

interviewobjectrole: {', '.join(agent_roles)}

 please generate3-5 interview question topic . """

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )
            
            return response.get("questions", [f" at {interview_requirement}, has see method ? "])
            
        except Exception as e:
            logger.warning(t("console.generateInterviewQuestionsFailed", error=e))
            return [
                f" at {interview_requirement}, viewpoint is ? ",
                " this item for or table group has shadow ? ",
                " recognize as should if parse or enter this question topic ? "
            ]
    
    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """generateinterviewsummary"""
        
        if not interviews:
            return " not completeinterview"
        
        # collectallinterviewcontent
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"[{interview.agent_name}({interview.agent_role})]\n{interview.response[:500]}")
        
        quote_instruction = "quoteinterviewee original speech time using in Chinese lead number """ if get_locale() == 'zh' else 'Use quotation marks "" when quoting interviewees'
        system_prompt = f""" is one new news edit. please root many interviewee return answer , generate one interviewsummary.

summary need :
1. each mainviewpoint
2. point exit viewpoint recognize and divide
3. exit has value introduction
4. neutral, not one
5. control control in 1000 char within

formatconstraint(must follow keep ):
- using pure textparagraph, empty line divide different partial
- not need using Markdowntitle( if #, ##, ###)
- not need using divider( if ---, ***)
- {quote_instruction}
- can to using ****markkey, but not need using its Markdown language method """

        user_prompt = f"""interviewtheme: {interview_requirement}

interviewcontent:
{"".join(interview_texts)}

 please generateinterviewsummary. """

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary
            
        except Exception as e:
            logger.warning(t("console.generateInterviewSummaryFailed", error=e))
            # downgrade: simple connect
            return f"interview{len(interviews)} interviewee, package : " + ", ".join([i.agent_name for i in interviews])
