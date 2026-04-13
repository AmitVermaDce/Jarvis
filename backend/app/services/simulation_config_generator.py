"""
simulation configuration can generate
 using LLM root simulation need , text content, graphinfoautogeneratesimulation parameters
implementation all process auto, no need settingsparameter

 divide stepgeneratestrategy, avoid exempt one times generate past long content guide failed:
1. generate time space configuration
2. generateeventconfiguration
3. divide generateAgentconfiguration
4. generateconfiguration
"""

import json
import math
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, t
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('jarvis.simulation_config')

# in schedule time space configuration( time space )
CHINA_TIMEZONE_CONFIG = {
    # late nighttime period( several no dynamic )
    "dead_hours": [0, 1, 2, 3, 4, 5],
    # early space time period( from )
    "morning_hours": [6, 7, 8],
    # time period
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    # eveningpeak( most active)
    "peak_hours": [19, 20, 21, 22],
    # space time period(active degree below )
    "night_hours": [23],
    # active degree coefficient
    "activity_multipliers": {
        "dead": 0.05, # early morning several no
        "morning": 0.4, # early space active
        "work": 0.7, # time period in
        "peak": 1.5,       # eveningpeak
        "night": 0.5 # late night below
    }
}


@dataclass
class AgentActivityConfig:
    """ Agent dynamic configuration"""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str
    
    # active degree configuration (0.0-1.0)
    activity_level: float = 0.5 # whole body active degree
    
    # send speech frequency( each small time period send speech times number )
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0
    
    # active time space segment (24 small time control , 0-23)
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))
    
    # response speed degree ( for trendingevent should delay, : simulation divide )
    response_delay_min: int = 5
    response_delay_max: int = 60
    
    # toward (-1.0 to 1.0, surface to positive surface )
    sentiment_bias: float = 0.0
    
    # position( for special fixed speech topic stance)
    stance: str = "neutral"  # supportive, opposing, neutral, observer
    
    # influenceweight( fixed its send speech was its Agent see to probability)
    influence_weight: float = 1.0


@dataclass  
class TimeSimulationConfig:
    """ time space simulation configuration( at in schedulehabits)"""
    # simulation time long (simulation small time number )
    total_simulation_hours: int = 72 # defaultsimulation72 small time (3 day )
    
    # each round table time space (simulation divide )- default60 divide (1 small time ), fast time space flow speed
    minutes_per_round: int = 60
    
    # each small time activateAgent number amount range
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20
    
    # peaktime period(evening19-22 point , in most active time space )
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5
    
    # off-peaktime period(early morning0-5 point , several no dynamic )
    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05 # early morningactive degree low
    
    # early space time period
    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4
    
    # time period
    work_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """eventconfiguration"""
    # initialevent(simulationstart time triggerevent)
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)
    
    # scheduledevent( in special scheduled space triggerevent)
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # trending speech topic key
    hot_topics: List[str] = field(default_factory=list)
    
    # public opinion lead guide toward
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """ special fixed configuration"""
    platform: str  # twitter or reddit
    
    # recommendalgorithmweight
    recency_weight: float = 0.4 # time space new degree
    popularity_weight: float = 0.3 # degree
    relevance_weight: float = 0.3 # related
    
    # propagationthreshold( reach to many few interaction after trigger scattered )
    viral_threshold: int = 10
    
    # return should strong degree (viewpoint set process degree )
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """completesimulation parametersconfiguration"""
    # basicinfo
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str
    
    # time space configuration
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)
    
    # Agentconfigurationlist
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)
    
    # eventconfiguration
    event_config: EventConfig = field(default_factory=EventConfig)
    
    # configuration
    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None
    
    # LLM configuration
    llm_model: str = ""
    llm_base_url: str = ""
    
    # generatedata
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = "" # LLMreasoningdescription
    
    def to_dict(self) -> Dict[str, Any]:
        """convert as dictionary"""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """convert as JSONstring"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
    simulation configuration can generate
    
     using LLManalyzesimulation need , text content, graphentityinfo,
    autogenerate most simulation parametersconfiguration
    
     divide stepgeneratestrategy:
    1. generate time space configuration and eventconfiguration( amount level )
    2. divide generateAgentconfiguration( each 10-20 )
    3. generateconfiguration
    """
    
    # context maximum character number
    MAX_CONTEXT_LENGTH = 50000
    # each generateAgent number amount
    AGENTS_PER_BATCH = 15
    
    # each stepcontexttruncate long degree (character number )
    TIME_CONFIG_CONTEXT_LENGTH = 10000 # time space configuration
    EVENT_CONFIG_CONTEXT_LENGTH = 8000   # eventconfiguration
    ENTITY_SUMMARY_LENGTH = 300          # entitysummary
    AGENT_SUMMARY_LENGTH = 300 # Agentconfiguration in entitysummary
    ENTITIES_PER_TYPE_DISPLAY = 20 # each classentitydisplay number amount
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
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
    
    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
         can generatecompletesimulation configuration( divide stepgenerate)
        
        Args:
            simulation_id: simulationID
            project_id: projectID
            graph_id: graphID
            simulation_requirement: simulation need description
            document_text: original begin Chinese content
            entities: filter after entitylist
            enable_twitter: is else enableTwitter
            enable_reddit: is else enableReddit
            progress_callback: progresscallbackfunction(current_step, total_steps, message)
            
        Returns:
            SimulationParameters: completesimulation parameters
        """
        logger.info(f"start can generatesimulation configuration: simulation_id={simulation_id}, entity number ={len(entities)}")
        
        # calculatestep number
        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches # time space configuration + eventconfiguration + NAgent + configuration
        current_step = 0
        
        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")
        
        # 1. structure basiccontextinfo
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities
        )
        
        reasoning_parts = []
        
        # ========== step1: generate time space configuration ==========
        report_progress(1, t('progress.generatingTimeConfig'))
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"{t('progress.timeConfigLabel')}: {time_config_result.get('reasoning', t('common.success'))}")
        
        # ========== step2: generateeventconfiguration ==========
        report_progress(2, t('progress.generatingEventConfig'))
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(f"{t('progress.eventConfigLabel')}: {event_config_result.get('reasoning', t('common.success'))}")
        
        # ========== step3-N: divide generateAgentconfiguration ==========
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]
            
            report_progress(
                3 + batch_idx,
                t('progress.generatingAgentConfig', start=start_idx + 1, end=end_idx, total=len(entities))
            )
            
            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement
            )
            all_agent_configs.extend(batch_configs)
        
        reasoning_parts.append(t('progress.agentConfigResult', count=len(all_agent_configs)))
        
        # ========== as initial sub allocatepublish Agent ==========
        logger.info(" as initial sub allocatepublish Agent...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(t('progress.postAssignResult', count=assigned_count))
        
        # ========== finally one step: generateconfiguration ==========
        report_progress(total_steps, t('progress.generatingPlatformConfig'))
        twitter_config = None
        reddit_config = None
        
        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5
            )
        
        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6
            )
        
        # structure most end parameter
        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts)
        )
        
        logger.info(f"simulation configurationgeneratecomplete: {len(params.agent_configs)} Agentconfiguration")
        
        return params
    
    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode]
    ) -> str:
        """ structure LLMcontext, truncate to maximum long degree """
        
        # entitysummary
        entity_summary = self._summarize_entities(entities)
        
        # structure context
        context_parts = [
            f"## simulation need \n{simulation_requirement}",
            f"\n## entityinfo ({len(entities)} )\n{entity_summary}",
        ]
        
        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500 # 500character remaining amount
        
        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...( text already truncate)"
            context_parts.append(f"\n## original begin Chinese content\n{doc_text}")
        
        return "\n".join(context_parts)
    
    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """generateentitysummary"""
        lines = []
        
        # type divide group
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)
        
        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)} )")
            # using configurationdisplay number amount and summary long degree
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (e.summary[:summary_len] + "...") if len(e.summary) > summary_len else e.summary
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f" ... also has {len(type_entities) - display_count} ")
        
        return "\n".join(lines)
    
    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """ with retryLLMcall, containJSON repeat logic"""
        import re
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1) # each times retry low degree
                    # not settingsmax_tokens, let LLM self send
                )
                
                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason
                
                # check is else was truncate
                if finish_reason == 'length':
                    logger.warning(f"LLMoutput was truncate (attempt {attempt+1})")
                    content = self._fix_truncated_json(content)
                
                # test parseJSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSONparsefailed (attempt {attempt+1}): {str(e)[:80]}")
                    
                    # test repeat JSON
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed
                    
                    last_error = e
                    
            except Exception as e:
                logger.warning(f"LLMcallfailed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(2 * (attempt + 1))
        
        raise last_error or Exception("LLMcallfailed")
    
    def _fix_truncated_json(self, content: str) -> str:
        """ repeat was truncateJSON"""
        content = content.strip()
        
        # calculate not close number
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # check is else has not close string
        if content and content[-1] not in '",}]':
            content += '"'
        
        # close number
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """ test repeat configurationJSON"""
        import re
        
        # repeat was truncate
        content = self._fix_truncated_json(content)
        
        # extractJSONpartial
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # removestring in switch line symbol
            def fix_string(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s
            
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)
            
            try:
                return json.loads(json_str)
            except:
                # test removeall control control character
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass
        
        return None
    
    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """generate time space configuration"""
        # using configurationcontexttruncate long degree
        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]
        
        # calculate maximum value (80%agent number )
        max_agents_allowed = max(1, int(num_entities * 0.9))
        
        prompt = f""" at to below simulation need , generate time space simulation configuration.

{context_truncated}

## task
 please generate time space configurationJSON.

### original then ( only provide reference, need root tool body event and and groupadjust):
- please root simulationscenario push break item mark usergroup in timezone and schedulehabits, to below as eight area (UTC+8)referenceexample
- early morning0-5 point several no dynamic (active degree coefficient0.05)
- early on 6-8 point active(active degree coefficient0.4)
- time space 9-18 point in active(active degree coefficient0.7)
- evening19-22 point is peak period (active degree coefficient1.5)
- 23 point after active degree below (active degree coefficient0.5)
- generally: early morning low active, early space increase , time period in , eveningpeak
- **important**: to below example value only provide reference, need to root event, and group special point from adjust tool body time period
  - if : grouppeakmay is 21-23 point ; body all day active; institution only in time space
  - if : breakingtrendingmay guide late night also has discuss , off_peak_hours can short

### return JSONformat( not need markdown)

example:
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": " for the event time space configurationdescription"
}}

 char segment description:
- total_simulation_hours (int): simulation time long , 24-168 small time , breakingevent short , hold continue speech topic long
- minutes_per_round (int): each round time long , 30-120 divide , recommend60 divide
- agents_per_hour_min (int): each small time most few activateAgent number ( fetch value range: 1-{max_agents_allowed})
- agents_per_hour_max (int): each small time most many activateAgent number ( fetch value range: 1-{max_agents_allowed})
- peak_hours (intarray): peaktime period, root event and groupadjust
- off_peak_hours (intarray): off-peaktime period, usuallylate nightearly morning
- morning_hours (intarray): early space time period
- work_hours (intarray): time period
- reasoning (string): briefdescription as this pattern configuration"""

        system_prompt = " is social media simulation. return pure JSONformat, time space configuration need symbol simulationscenario in item mark usergroupschedulehabits. "
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f" time space configurationLLMgeneratefailed: {e}, using defaultconfiguration")
            return self._get_default_time_config(num_entities)
    
    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """ fetch default time space configuration( in schedule)"""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60, # each round1 small time , fast time space flow speed
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": " using default in scheduleconfiguration( each round1 small time )"
        }
    
    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        """parse time space configuration, validateagents_per_hour value not exceed past agent number """
        # fetch original begin value
        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))
        
        # validate positive : correctly protect not exceed past agent number
        if agents_per_hour_min > num_entities:
            logger.warning(f"agents_per_hour_min ({agents_per_hour_min}) exceed past Agent number ({num_entities}), already positive ")
            agents_per_hour_min = max(1, num_entities // 10)
        
        if agents_per_hour_max > num_entities:
            logger.warning(f"agents_per_hour_max ({agents_per_hour_max}) exceed past Agent number ({num_entities}), already positive ")
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)
        
        # correctly protect min < max
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(f"agents_per_hour_min >= max, already positive as {agents_per_hour_min}")
        
        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60), # default each round1 small time
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05, # early morning several no
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5
        )
    
    def _generate_event_config(
        self, 
        context: str, 
        simulation_requirement: str,
        entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """generateeventconfiguration"""
        
        # fetch can entity typeslist, provide LLM reference
        entity_types_available = list(set(
            e.get_entity_type() or "Unknown" for e in entities
        ))
        
        # as each types type column exit table entityname
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)
        
        type_info = "\n".join([
            f"- {t}: {', '.join(examples)}" 
            for t, examples in type_examples.items()
        ])
        
        # using configurationcontexttruncate long degree
        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]
        
        prompt = f""" at to below simulation need , generateeventconfiguration.

simulation need : {simulation_requirement}

{context_truncated}

## can entity types and example
{type_info}

## task
 please generateeventconfigurationJSON:
- extracttrending speech topic key
- descriptionpublic opinion send toward
- initial sub content, **each sub must point fixed poster_type(publishtype)**

**important**: poster_type must from on surface " can entity types" in select, this pattern initial sub can allocate to Agent publish.
 if : declare should Official/University typepublish, new news MediaOutlet publish, viewpoint Student publish.

 return JSONformat( not need markdown):
{{
    "hot_topics": ["key1", "key2", ...],
    "narrative_direction": "<public opinion send toward description>",
    "initial_posts": [
        {{"content": " sub content", "poster_type": "entity types(must from can type in select)"}},
        ...
    ],
    "reasoning": "<briefdescription>"
}}"""

        system_prompt = " is public opinionanalyze. return pure JSONformat. note poster_type must correct match can entity types. "
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}\nIMPORTANT: The 'poster_type' field value MUST be in English PascalCase exactly matching the available entity types. Only 'content', 'narrative_direction', 'hot_topics' and 'reasoning' fields should use the specified language."

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"eventconfigurationLLMgeneratefailed: {e}, using defaultconfiguration")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": " using defaultconfiguration"
            }
    
    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """parseeventconfiguration"""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", "")
        )
    
    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
         as initial sub allocatepublish Agent
        
         root each sub poster_type match most agent_id
        """
        if not event_config.initial_posts:
            return event_config
        
        # entity types agent index
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)
        
        # typemapping table (process LLM mayoutput different format)
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }
        
        # record each types type already using agent index, avoid exempt duplicate using same one agent
        used_indices: Dict[str, int] = {}
        
        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")
            
            # test find to match agent
            matched_agent_id = None
            
            # 1. directly match
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. using name match
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break
            
            # 3. if not find to , using influence most high agent
            if matched_agent_id is None:
                logger.warning(f" not find to type '{poster_type}' match Agent, using influence most high Agent")
                if agent_configs:
                    # influencesort, selectinfluence most high
                    sorted_agents = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0
            
            updated_posts.append({
                "content": content,
                "poster_type": post.get("poster_type", "Unknown"),
                "poster_agent_id": matched_agent_id
            })
            
            logger.info(f"initial sub allocate: poster_type='{poster_type}' -> agent_id={matched_agent_id}")
        
        event_config.initial_posts = updated_posts
        return event_config
    
    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str
    ) -> List[AgentActivityConfig]:
        """ divide generateAgentconfiguration"""
        
        # structure entityinfo( using configurationsummary long degree )
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else ""
            })
        
        prompt = f""" at to below info, as eachentitygeneratesocial media dynamic configuration.

simulation need : {simulation_requirement}

## entitylist
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## task
 as eachentitygenerate dynamic configuration, note:
- ** time space symbol item mark usergroupschedule**: to below as reference( eight area ), please root simulationscenarioadjust
- **institution**(University/GovernmentAgency): active degree low (0.1-0.3), time space (9-17) dynamic , response slow (60-240 divide ), influence high (2.5-3.0)
- ** body **(MediaOutlet): active degree in (0.4-0.6), all day dynamic (8-23), response fast (5-30 divide ), influence high (2.0-2.5)
- ** **(Student/Person/Alumni): active degree high (0.6-0.9), mainevening dynamic (18-23), response fast (1-15 divide ), influence low (0.8-1.2)
- **/**: active degree in (0.4-0.6), influence in high (1.5-2.0)

 return JSONformat( not need markdown):
{{
    "agent_configs": [
        {{
            "agent_id": <must and input one >,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <postingfrequency>,
            "comments_per_hour": <commentfrequency>,
            "active_hours": [<active small time list, in schedule>],
            "response_delay_min": < most small responsedelay divide >,
            "response_delay_max": < maximum responsedelay divide >,
            "sentiment_bias": <-1.0 to 1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <influenceweight>
        }},
        ...
    ]
}}"""

        system_prompt = " is social media line as analyze. return pure JSON, configuration need symbol simulationscenario in item mark usergroupschedulehabits. "
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}\nIMPORTANT: The 'stance' field value MUST be one of the English strings: 'supportive', 'opposing', 'neutral', 'observer'. All JSON field names and numeric values must remain unchanged. Only natural language text fields should use the specified language."

        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"AgentconfigurationbatchLLMgeneratefailed: {e}, using rulegenerate")
            llm_configs = {}
        
        # structure AgentActivityConfigobject
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})
            
            # ifLLMnogenerate, using rulegenerate
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)
            
            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0)
            )
            configs.append(config)
        
        return configs
    
    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """ at rulegenerate Agentconfiguration( in schedule)"""
        entity_type = (entity.get_entity_type() or "Unknown").lower()
        
        if entity_type in ["university", "governmentagency", "ngo"]:
            # institution: time space dynamic , low frequency, high influence
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),  # 9:00-17:59
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0
            }
        elif entity_type in ["mediaoutlet"]:
            # body : all day dynamic , in frequency, high influence
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),  # 7:00-23:59
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5
            }
        elif entity_type in ["professor", "expert", "official"]:
            # /: +evening dynamic , in frequency
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),  # 8:00-21:59
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0
            }
        elif entity_type in ["student"]:
            # : evening as main , high frequency
            return {
                "activity_level": 0.8,
                "posts_per_hour": 0.6,
                "comments_per_hour": 1.5,
                "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # morning+evening
                "response_delay_min": 1,
                "response_delay_max": 15,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 0.8
            }
        elif entity_type in ["alumni"]:
            # : evening as main
            return {
                "activity_level": 0.6,
                "posts_per_hour": 0.4,
                "comments_per_hour": 0.8,
                "active_hours": [12, 13, 19, 20, 21, 22, 23], # +evening
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
        else:
            # common through : eveningpeak
            return {
                "activity_level": 0.7,
                "posts_per_hour": 0.5,
                "comments_per_hour": 1.2,
                "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23], # day +evening
                "response_delay_min": 2,
                "response_delay_max": 20,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
    

