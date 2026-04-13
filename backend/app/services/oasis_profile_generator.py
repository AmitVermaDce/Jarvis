"""
OASIS Agent Profilegenerate
 will Zepgraph in entityconvert as OASIS simulation need Agent Profileformat

optimize enter :
1. callZepretrievalfeature two times nodeinfo
2. optimizehintgeneratenon- normal detailedpersona
3. distinguish entity and abstractgroupentity
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, get_locale, set_locale, t
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('jarvis.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profiledata structure"""
    # through char segment
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # optional char segment - Reddit
    karma: int = 1000
    
    # optional char segment - Twitter
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # outside personainfo
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # from source entityinfo
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """convert as Redditformat"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name, # OASIS lib need char segment name as username( no underline)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        # add outside personainfo(if has )
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """convert as Twitterformat"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name, # OASIS lib need char segment name as username( no underline)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # add outside personainfo
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """convert as completedictionaryformat"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profilegenerate
    
     will Zepgraph in entityconvert as OASIS simulation need Agent Profile
    
    optimize special :
    1. callZepgraphretrievalfeature fetch more context
    2. generatenon- normal detailedpersona( package info, , special , social media line as )
    3. distinguish entity and abstractgroupentity
    """
    
    # MBTItypelist
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # normal view list
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    # typeentity( need to generate tool body persona)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    # group/institutiontypeentity( need to generategroup table persona)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY not configured")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Zep endpoint at retrievalcontext
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = None
        self.graph_id = graph_id
        
        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zep endpoint initializefailed: {e}")
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
         from ZepentitygenerateOASIS Agent Profile
        
        Args:
            entity: Zepentitynode
            user_id: userID( at OASIS)
            use_llm: is else using LLMgeneratedetailedpersona
            
        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # basicinfo
        name = entity.name
        user_name = self._generate_username(name)
        
        # structure contextinfo
        context = self._build_entity_context(entity)
        
        if use_llm:
            # using LLMgeneratedetailedpersona
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # using rulegeneratebasicpersona
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """generateuser name """
        # remove special character, convert as small write
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # addrandom after avoid exempt duplicate
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
         using Zepgraphhybridsearchfeature fetch entityrelatedinfo
        
        Zepnobuilt-inhybridsearchAPI, need to divide searchedges and nodesthenmerge.
         using parallelrequestmeanwhilesearch, high rate .
        
        Args:
            entity: entitynodeobject
            
        Returns:
            containfacts, node_summaries, contextdictionary
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        # must has graph_id can enter line search
        if not self.graph_id:
            logger.debug(f"skipZepretrieval: not settingsgraph_id")
            return results
        
        comprehensive_query = t('progress.zepSearchQuery', name=entity_name)
        
        def search_edges():
            """search( actual /relation)- with retry logic """
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zepsearch # {attempt + 1} times failed: {str(e)[:80]}, retry in ...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zepsearch in {max_retries} times test after failed: {e}")
            return None
        
        def search_nodes():
            """searchnode(entitysummary)- with retry logic """
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zepnodesearch # {attempt + 1} times failed: {str(e)[:80]}, retry in ...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zepnodesearch in {max_retries} times test after failed: {e}")
            return None
        
        try:
            # parallelexecuteedges and nodessearch
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                # fetch
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)
            
            # processsearch
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            # processnodesearch
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"relatedentity: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            # structure context
            context_parts = []
            if results["facts"]:
                context_parts.append(" actual info:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("relatedentity:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zephybridretrievalcomplete: {entity_name}, fetch {len(results['facts'])} entries actual , {len(results['node_summaries'])} relatednode")
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zepretrievaltimeout ({entity_name})")
        except Exception as e:
            logger.warning(f"Zepretrievalfailed ({entity_name}): {e}")
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
         structure entitycompletecontextinfo
        
         package :
        1. entityinfo( actual )
        2. associatednodedetailedinfo
        3. Zephybridretrieval to info
        """
        context_parts = []
        
        # 1. addentityattributeinfo
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### entityattribute\n" + "\n".join(attrs))
        
        # 2. addrelatedinfo( actual /relation)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges: # not limit number amount
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (relatedentity)")
                    else:
                        relationships.append(f"- (relatedentity) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### related actual and relation\n" + "\n".join(relationships))
        
        # 3. addassociatednodedetailedinfo
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes: # not limit number amount
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # filterdefaultlabel
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### associatedentityinfo\n" + "\n".join(related_info))
        
        # 4. using Zephybridretrieval fetch more info
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # deduplicate: exclude already exists in actual
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zepretrieval to actual info\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zepretrieval to relatednode\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """check is else is typeentity"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """check is else is group/institutiontypeentity"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
         using LLMgeneratenon- normal detailedpersona
        
         root entity typesdistinguish:
        - entity: generate tool body fixed
        - group/institutionentity: generate table number fixed
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # test many times generate, straight to success or reach to maximum retry times number
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1) # each times retry low degree
                    # not settingsmax_tokens, let LLM self send
                )
                
                content = response.choices[0].message.content
                
                # check is else was truncate(finish_reason not is 'stop')
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(f"LLMoutput was truncate (attempt {attempt+1}), test repeat ...")
                    content = self._fix_truncated_json(content)
                
                # test parseJSON
                try:
                    result = json.loads(content)
                    
                    # validaterequired char segment
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name} is one {entity_type}. "
                    
                    return result
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSONparsefailed (attempt {attempt+1}): {str(je)[:80]}")
                    
                    # test repeat JSON
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result
                    
                    last_error = je
                    
            except Exception as e:
                logger.warning(f"LLMcallfailed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1)) # point number avoid
        
        logger.warning(f"LLMgeneratepersonafailed({max_attempts} times test ): {last_error}, using rulegenerate")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """ repeat was truncateJSON(output was max_tokenslimittruncate)"""
        import re
        
        # ifJSON was truncate, test close it
        content = content.strip()
        
        # calculate not close number
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # check is else has not close string
        # simple check : iffinally one lead number after no number or close number , may is string was truncate
        if content and content[-1] not in '",}]':
            # test close string
            content += '"'
        
        # close number
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """ test repeat bad JSON"""
        import re
        
        # 1. first test repeat was truncate
        content = self._fix_truncated_json(content)
        
        # 2. test extractJSONpartial
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. processstring in switch line symbol question topic
            # find to allstring value replace switch its in switch line symbol
            def fix_string_newlines(match):
                s = match.group(0)
                # replace switch string within actual switch line symbol as empty
                s = s.replace('\n', ' ').replace('\r', ' ')
                # replace switch many remaining empty
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # matchJSONstring value
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. test parse
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. if also is failed, test more enter repeat
                try:
                    # removeall control control character
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # replace switch all continue empty
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. test from content in extractpartialinfo
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content) # may was truncate
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name} is one {entity_type}. ")
        
        # ifextract to has meaning content, mark as already repeat
        if bio_match or persona_match:
            logger.info(f" from bad JSON in extractpartialinfo")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. all failed, return basic structure
        logger.warning(f"JSON repeat failed, return basic structure ")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name} is one {entity_type}. "
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """ fetch system unified hint"""
        base_prompt = " is social media userprofilegenerate. generatedetailed, actual persona at public opinionsimulation, maximum process degree also original already has actual . must return validJSONformat, allstring value not can contain not turn switch line symbol . "
        return f"{base_prompt}\n\n{get_language_instruction()}"
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """ structure entitydetailedpersonahint"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else " no "
        context_str = context[:3000] if context else " no outside context"
        
        return f""" as entitygeneratedetailedsocial media userpersona, maximum process degree also original already has actual .

entityname: {entity_name}
entity types: {entity_type}
entitysummary: {entity_summary}
entityattribute: {attrs_str}

contextinfo:
{context_str}

 please generateJSON, contain to below char segment :

1. bio: social media simple , 200 char
2. persona: detailedpersonadescription(2000 char pure text), need contain:
   - info( year , , background, in )
   - background(important, and eventassociated, will relation)
   - special (MBTItype, core, table reach type )
   - social media line as (postingfrequency, content good , interaction, language speech special point )
   - positionviewpoint( for speech topic stance, may was / dynamic content)
   - single special special ( port head , special , good )
   - memory(personaimportantpartial, need this body and eventassociated, to and this body in event in already has dynamic and should )
3. age: year number char (must is whole number )
4. gender: , must is text : "male" or "female"
5. mbti: MBTItype( if INTJ, ENFP)
6. country: ( using in Chinese , if " in ")
7. profession:
8. interested_topics: speech topic array

important:
- all char segment value must is string or number char , not need using switch line symbol
- personamust is one segment text char description
- {get_language_instruction()} (gender char segment must text male/female)
- content need and entityinfo protect hold one
- agemust is valid whole number , gendermust is "male" or "female"
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """ structure group/institutionentitydetailedpersonahint"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else " no "
        context_str = context[:3000] if context else " no outside context"
        
        return f""" as institution/groupentitygeneratedetailedsocial media number fixed , maximum process degree also original already has actual .

entityname: {entity_name}
entity types: {entity_type}
entitysummary: {entity_summary}
entityattribute: {attrs_str}

contextinfo:
{context_str}

 please generateJSON, contain to below char segment :

1. bio: number simple , 200 char , body
2. persona: detailed number fixed description(2000 char pure text), need contain:
   - institutioninfo( positive type name, institution, background, main can )
   - number fixed ( number type, item mark , corefeature)
   - send speech ( language speech special point , normal table reach , speech topic )
   - publishcontent special point (contenttype, publishfrequency, active time space segment )
   - positionstance( for core speech topic position, surface for process type )
   - special description( table groupprofile, run habits)
   - institutionmemory(institutionpersonaimportantpartial, need this institution and eventassociated, to and this institution in event in already has dynamic and should )
3. age: fixed fixed fill 30(institution number year )
4. gender: fixed fixed fill "other"(institution number using other table non- )
5. mbti: MBTItype, at description number , if ISTJ table protect keep
6. country: ( using in Chinese , if " in ")
7. profession: institution can description
8. interested_topics: follow domain array

important:
- all char segment value must is string or number char , not null value
- personamust is one segment text char description, not need using switch line symbol
- {get_language_instruction()} (gender char segment must text "other")
- agemust is whole number 30, gendermust is string"other"
- institution number send speech need symbol its fixed """
    
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """ using rulegeneratebasicpersona"""
        
        # root entity typesgenerate different persona
        entity_type_lower = entity_type.lower()
        
        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
                "age": 30, # institution year
                "gender": "other", # institution using other
                "mbti": "ISTJ", # institution: protect keep
                "country": " in ",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }
        
        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
                "age": 30, # institution year
                "gender": "other", # institution using other
                "mbti": "ISTJ", # institution: protect keep
                "country": " in ",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }
        
        else:
            # defaultpersona
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
    
    def set_graph_id(self, graph_id: str):
        """settingsgraphID at Zepretrieval"""
        self.graph_id = graph_id
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
         amount from entitygenerateAgent Profile(supportparallelgenerate)
        
        Args:
            entities: entitylist
            use_llm: is else using LLMgeneratedetailedpersona
            progress_callback: progresscallbackfunction (current, total, message)
            graph_id: graphID, at Zepretrieval fetch more context
            parallel_count: parallelgenerate number amount , default5
            realtime_output_path: actual time write enter filepath(if provide , each generate one then write enter one times )
            output_platform: outputformat ("reddit" or "twitter")
            
        Returns:
            Agent Profilelist
        """
        import concurrent.futures
        from threading import Lock
        
        # settingsgraph_id at Zepretrieval
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total # allocatelist protect hold order
        completed_count = [0] # using listso that in close package in modify
        lock = Lock()
        
        # actual time write enter file assist function
        def save_profiles_realtime():
            """ actual time save already generate profiles to file"""
            if not realtime_output_path:
                return
            
            with lock:
                # filter exit already generate profiles
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        # Reddit JSON format
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV format
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f" actual time save profiles failed: {e}")
        
        # Capture locale before spawning thread pool workers
        current_locale = get_locale()

        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """generate profilefunction"""
            set_locale(current_locale)
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                # actual time outputgeneratepersona to console and log
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, None
                
            except Exception as e:
                logger.error(f"generateentity {entity.name} personafailed: {str(e)}")
                # create one basicprofile
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"startparallelgenerate {total} Agentpersona(parallel number : {parallel_count})...")
        print(f"\n{'='*60}")
        print(f"startgenerateAgentpersona - {total} entity, parallel number : {parallel_count}")
        print(f"{'='*60}\n")
        
        # using threadparallelexecute
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # submitalltask
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # collect
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    # actual time write enter file
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f" already complete {current}/{total}: {entity.name}({entity_type})"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} using backup persona: {error}")
                    else:
                        logger.info(f"[{current}/{total}] successgeneratepersona: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"processentity {entity.name} time send exception: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # actual time write enter file( immediately using is backup persona)
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"personageneratecomplete! generate {len([p for p in profiles if p])} Agent")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """ actual time outputgeneratepersona to console(completecontent, not truncate)"""
        separator = "-" * 70
        
        # structure completeoutputcontent( not truncate)
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else ' no '
        
        output_lines = [
            f"\n{separator}",
            t('progress.profileGenerated', name=entity_name, type=entity_type),
            f"{separator}",
            f"user name : {profile.user_name}",
            f"",
            f"[ simple ]",
            f"{profile.bio}",
            f"",
            f"[detailedpersona]",
            f"{profile.persona}",
            f"",
            f"[attribute]",
            f" year : {profile.age} | : {profile.gender} | MBTI: {profile.mbti}",
            f": {profile.profession} | : {profile.country}",
            f" speech topic : {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        # only output to console( avoid exempt duplicate, loggerno longeroutputcompletecontent)
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        saveProfile to file( root select positive correct format)
        
        OASISformat need :
        - Twitter: CSVformat
        - Reddit: JSONformat
        
        Args:
            profiles: Profilelist
            file_path: filepath
            platform: type ("reddit" or "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        saveTwitter Profile as CSVformat( symbol OASIS need )
        
        OASIS Twitter need CSV char segment :
        - user_id: userID( root CSV order from 0start)
        - name: user actual name
        - username: system unified in user name
        - user_char: detailedpersonadescription(inject to LLM system unified hint in , point guide Agent line as )
        - description: simple short public simple (display in userpage)
        
        user_char vs description area :
        - user_char: internal using , LLM system unified hint, fixed Agent if think and line dynamic
        - description: externaldisplay, its uservisible simple
        """
        import csv
        
        # correctly protect fileextend name is .csv
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # write enter OASIS need table head
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # write enter data line
            for idx, profile in enumerate(profiles):
                # user_char: completepersona(bio + persona), at LLM system unified hint
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # process switch line symbol (CSV in empty replace )
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                # description: simple short simple , at externaldisplay
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx, # user_id: from 0start order ID
                    profile.name, # name: actual name
                    profile.user_name, # username: user name
                    user_char, # user_char: completepersona(internalLLM using )
                    description # description: simple short simple (externaldisplay)
                ]
                writer.writerow(row)
        
        logger.info(f" already save {len(profiles)} Twitter Profile to {file_path} (OASIS CSVformat)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        standardgender char segment as OASIS need text format
        
        OASIS need : male, female, other
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        # in Chinese mapping
        gender_map = {
            "": "male",
            "": "female",
            "institution": "other",
            " its ": "other",
            # text already has
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        saveReddit Profile as JSONformat
        
         using and to_reddit_format() one format, correctly protect OASIS can positive correct read fetch .
        mustcontain user_id char segment , this is OASIS agent_graph.get_agent() matchkey!
        
        required char segment :
        - user_id: userID( whole number , at match initial_posts in poster_agent_id)
        - username: user name
        - name: displayname
        - bio: simple
        - persona: detailedpersona
        - age: year ( whole number )
        - gender: "male", "female", or "other"
        - mbti: MBTItype
        - country:
        """
        data = []
        for idx, profile in enumerate(profiles):
            # using and to_reddit_format() one format
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx, # key: mustcontain user_id
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASISrequired char segment - correctly protect all has default value
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else " in ",
            }
            
            # optional char segment
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f" already save {len(profiles)} Reddit Profile to {file_path} (JSONformat, containuser_id char segment )")
    
    # protect old method name as name , protect hold toward after compatible
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[ already ] please using save_profiles() method"""
        logger.warning("save_profiles_to_json already , please using save_profilesmethod")
        self.save_profiles(profiles, file_path, platform)

