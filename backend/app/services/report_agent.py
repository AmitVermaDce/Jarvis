"""
Report Agentservice
 using LangChain + ZepimplementationReACTmodesimulationreportgenerate

feature:
1. root simulation need and Zepgraphinfogeneratereport
2. directory structure , then divide segment generate
3. each segment ReACT many round think and think mode
4. support and user for speech , in for speech in self main callretrievaltool
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, t
from .zep_tools import (
    ZepToolsService, 
    SearchResult, 
    InsightForgeResult, 
    PanoramaResult,
    InterviewResult
)

logger = get_logger('jarvis.report_agent')


class ReportLogger:
    """
    Report Agent detailedlogging
    
    in reportfolder in generate agent_log.jsonl file, record each one stepdetailed dynamic .
     each line is one complete JSON object, contain time space , dynamic type, detailedcontent.
    """
    
    def __init__(self, report_id: str):
        """
        initializelogging
        
        Args:
            report_id: reportID, at correct fixed log filespath
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """ correctly protect log files in directory exist in """
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _get_elapsed_time(self) -> float:
        """ fetch from start to in time ( second )"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def log(
        self, 
        action: str, 
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None
    ):
        """
         record one entries log
        
        Args:
            action: dynamic type, if 'start', 'tool_call', 'llm_response', 'section_complete'
            stage: before segment , if 'planning', 'generating', 'completed'
            details: detailedcontentdictionary, not truncate
            section_title: before sectiontitle(optional)
            section_index: before sectionindex(optional)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details
        }
        
        # write enter JSONL file
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """ record reportgeneratestart"""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": t('report.taskStarted')
            }
        )
    
    def log_planning_start(self):
        """ record outlinestart"""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": t('report.planningStart')}
        )
    
    def log_planning_context(self, context: Dict[str, Any]):
        """ record time fetch contextinfo"""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": t('report.fetchSimContext'),
                "context": context
            }
        )
    
    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """ record outlinecomplete"""
        self.log(
            action="planning_complete",
            stage="planning",
            details={
                "message": t('report.planningComplete'),
                "outline": outline_dict
            }
        )
    
    def log_section_start(self, section_title: str, section_index: int):
        """ record sectiongeneratestart"""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": t('report.sectionStart', title=section_title)}
        )
    
    def log_react_thought(self, section_title: str, section_index: int, iteration: int, thought: str):
        """ record ReACT think past process """
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": t('report.reactThought', iteration=iteration)
            }
        )
    
    def log_tool_call(
        self, 
        section_title: str, 
        section_index: int,
        tool_name: str, 
        parameters: Dict[str, Any],
        iteration: int
    ):
        """ record toolcall"""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": t('report.toolCall', toolName=tool_name)
            }
        )
    
    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int
    ):
        """ record toolcall(completecontent, not truncate)"""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result, # complete, not truncate
                "result_length": len(result),
                "message": t('report.toolResult', toolName=tool_name)
            }
        )
    
    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool
    ):
        """ record LLM response(completecontent, not truncate)"""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response, # completeresponse, not truncate
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": t('report.llmResponse', hasToolCalls=has_tool_calls, hasFinalAnswer=has_final_answer)
            }
        )
    
    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int
    ):
        """ record sectioncontentgeneratecomplete( only record content, not table whole sectioncomplete)"""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content, # completecontent, not truncate
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": t('report.sectionContentDone', title=section_title)
            }
        )
    
    def log_section_full_complete(
        self,
        section_title: str,
        section_index: int,
        full_content: str
    ):
        """
         record sectiongeneratecomplete

        frontend should listen this log from check one section is else true positive complete, fetch completecontent
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": t('report.sectionComplete', title=section_title)
            }
        )
    
    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """ record reportgeneratecomplete"""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": t('report.reportComplete')
            }
        )
    
    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """ record error"""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": t('report.errorOccurred', error=error_message)
            }
        )


class ReportConsoleLogger:
    """
    Report Agent consolelogging
    
     will consolelog(INFO, WARNING) write enter reportfolder in console_log.txt file.
     this some log and agent_log.jsonl different , is pure textformatconsoleoutput.
    """
    
    def __init__(self, report_id: str):
        """
        initializeconsolelogging
        
        Args:
            report_id: reportID, at correct fixed log filespath
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'console_log.txt'
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()
    
    def _ensure_log_file(self):
        """ correctly protect log files in directory exist in """
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _setup_file_handler(self):
        """settingsfile processing, will logmeanwhile write enter file"""
        import logging
        
        # createfile processing
        self._file_handler = logging.FileHandler(
            self.log_file_path,
            mode='a',
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.INFO)
        
        # using and console same simple format
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self._file_handler.setFormatter(formatter)
        
        # add to report_agent related logger
        loggers_to_attach = [
            'jarvis.report_agent',
            'jarvis.zep_tools',
        ]
        
        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # avoid exempt duplicateadd
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)
    
    def close(self):
        """closefile processing from logger in remove"""
        import logging
        
        if self._file_handler:
            loggers_to_detach = [
                'jarvis.report_agent',
                'jarvis.zep_tools',
            ]
            
            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            
            self._file_handler.close()
            self._file_handler = None
    
    def __del__(self):
        """destruct time correctly protect closefile processing"""
        self.close()


class ReportStatus(str, Enum):
    """reportstatus"""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """reportsection"""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """convert as Markdownformat"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """reportoutline"""
    title: str
    summary: str
    sections: List[ReportSection]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    def to_markdown(self) -> str:
        """convert as Markdownformat"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """completereport"""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error
        }


# ═══════════════════════════════════════════════════════════════
# Prompt templateconstant
# ═══════════════════════════════════════════════════════════════

# ── tooldescription ──

TOOL_DESC_INSIGHT_FORGE = """\
[ deep degree insightretrieval - strong large retrievaltool]
 this is strong large retrievalfunction, as deep degree analyze. it will :
1. auto will question topic divide parse as many sub question topic
2. from many degree retrievalsimulationgraph in info
3. whole language search, entityanalyze, relation chain trace
4. return most all surface , most deep degree retrievalcontent

[ using scenario]
- need to deep enter analyze certain speech topic
- need to parse event many surface
- need to fetch reportsection

[ return content]
- related actual original text ( can directly quote)
- coreentityinsight
- relation chain analyze"""

TOOL_DESC_PANORAMA_SEARCH = """\
[ degree search - fetch all view]
 this tool at fetch simulationcomplete all , especially parse event change past process . it will :
1. fetch allrelatednode and relation
2. distinguish before valid actual and /expired actual
3. help assist parse public opinion is if change

[ using scenario]
- need to parse eventcomplete send network
- need to for different segment public opinion change
- need to fetch all surface entity and relationinfo

[ return content]
- before valid actual (simulation most new )
- /expired actual ( change record )
- all and entity"""

TOOL_DESC_QUICK_SEARCH = """\
[ simple search - fast speed retrieval]
 amount level fast speed retrievaltool, simple , directly infoquery.

[ using scenario]
- need to fast speed check find certain tool body info
- need to validate certain actual
- simple inforetrieval

[ return content]
- and query most related actual list"""

TOOL_DESC_INTERVIEW_AGENTS = """\
[ deep degree interview - actual Agentinterview( dual )]
callOASIS simulation environmentinterviewAPI, for currentlyrunsimulationAgent enter line actual interview!
 this not is LLMsimulation, and is call actual interviewAPI fetch simulationAgent original begin return answer .
default in Twitter and Reddit meanwhileinterview, fetch more all surface viewpoint.

featureflow:
1. auto read fetch personafile, parse allsimulationAgent
2. can select and interviewtheme most relatedAgent( if , body , )
3. autogenerateinterview question topic
4. call /api/simulation/interview/batch API in dual enter line actual interview
5. whole allinterview, provide many analyze

[ using scenario]
- need to from different role parse event see method ( see ? body see ? say ? )
- need to collect many meaning view and position
- need to fetch simulationAgent actual return answer ( from self OASIS simulation environment)
- think let report more dynamic , contain"interview actual record "

[ return content]
- was interviewAgent info
- each Agent in Twitter and Reddit interview return answer
- keyintroduction( can directly quote)
- interviewsummary and viewpoint for

[important] need to OASIS simulation environmentcurrentlyrun can using this feature! """

# ── outline prompt ──

PLAN_SYSTEM_PROMPT = """\
 is one " not from predictionreport" write , own has for simulation" on "-- can to insightsimulation in each one Agent line as , speech discuss and interaction.

[core]
 structure one simulation, toward its in inject special fixed "simulation need " as variable. simulation, then is for not from may send prediction. currentlyobserve not is " actual data", and is " not from ".

[task]
 write one " not from predictionreport", return answer :
1. in fixed condition below , not from send ?
2. each classAgent() is if should and line dynamic ?
3. this simulation some value follow not from trend and ?

[report fixed ]
- ✅ this is one at simulation not from predictionreport, "if this pattern , not from will pattern "
- ✅ at prediction: event toward , group should , emergence image , in
- ✅ simulation in Agent speech line then is for not from line as prediction
- ❌ not is for actual analyze
- ❌ not is and public opinion

[section number amount limit]
- most few 2 section, most many 5 section
- not need to sub section, eachsection directly write completecontent
- content need , at corepredictionfinding
- section structure root prediction self main

 please outputJSONformatreportoutline, formatas follows:
{
    "title": "reporttitle",
    "summary": "reportsummary( one sentence speech corepredictionfinding)",
    "sections": [
        {
            "title": "sectiontitle",
            "description": "sectioncontentdescription"
        }
    ]
}

note: sectionsarray most few 2 , most many 5 ! """

PLAN_USER_PROMPT_TEMPLATE = """\
[predictionscenario fixed ]
 toward simulationinjectvariable(simulation need ): {simulation_requirement}

[simulation model ]
- and simulationentity number amount : {total_nodes}
- entity space relation number amount : {total_edges}
- entity typesdistribution: {entity_types}
- activeAgent number amount : {total_entities}

[simulationprediction to partial not from actual pattern ]
{related_facts_json}

 please to " on " this not from :
1. in fixed condition below , not from exit pattern status?
2. each class(Agent) is if should and line dynamic ?
3. this simulation some value follow not from trend?

 root prediction, most reportsection structure .

[ retry ]reportsection number amount : most few 2 , most many 5 , content need at corepredictionfinding. """

# ── sectiongenerate prompt ──

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
 is one " not from predictionreport" write , currently write report one section.

reporttitle: {report_title}
reportsummary: {report_summary}
predictionscenario(simulation need ): {simulation_requirement}

 before need write section: {section_title}

═══════════════════════════════════════════════════════════════
[core]
═══════════════════════════════════════════════════════════════

simulation is for not from . toward simulationinject special fixed condition(simulation need ),
simulation in Agent line as and interaction, then is for not from line as prediction.

task is :
- in fixed condition below , not from send
- prediction each class(Agent) is if should and line dynamic
- finding value follow not from trend, and will

❌ not need write for actual analyze
✅ need at " not from will pattern "——simulation then is prediction not from

═══════════════════════════════════════════════════════════════
[ most importantrule - must follow keep ]
═══════════════════════════════════════════════════════════════

1. [mustcalltoolobservesimulation]
   - currently to " on "observe not from
   - allcontentmust from self simulation in send event and Agent speech line
   - stop using self self know recognize from write reportcontent
   - eachsection few call3 times tool( most many 5 times ) from observesimulation, it table not from

2. [mustquoteAgent original begin speech line ]
   - Agent send speech and line as is for not from line as prediction
   - in report in using quoteformat this some prediction, if :
     > " certain class will table : original text content..."
   - this some quote is simulationpredictioncore certificate

3. [ language speech one - quotecontentmust as report language speech ]
   - tool return contentmaycontain and report language speech different table
   - reportmustall using and user point fixed language speech one language speech write
   - quotetool return its language speech content time , must will its as report language speech after again write enter
   - time protect hold original meaning not change , correctly protect table self through
   - this one rulemeanwhile at positive text and quote block (> format) in content

4. [ actual prediction]
   - reportcontentmustsimulation in table not from simulation
   - not need addsimulation in not exist in info
   - if certain surface info not sufficient , if actual description

═══════════════════════════════════════════════════════════════
[⚠️ formatspecification - its important! ]
═══════════════════════════════════════════════════════════════

[ one section = most small content ]
- eachsection is report most small divide block
- ❌ stop in section within using Markdown title(#, ##, ###, #### )
- ❌ stop in content open head addsection main title
- ✅ sectiontitle system unified autoadd, only need write pure positive text content
- ✅ using **bold**, paragraph divide , quote, list from organizationcontent, but not need title

[ positive correct example]
```
sectionanalyzeeventpublic opinionpropagation. through past for simulationdata deep enter analyze, finding...

** first send lead segment **

 as public opinion # one , info first send corefeature:

> "68% first speak amount ..."

** place large segment **

 enter one step place large eventinfluence:

- sense strong
- degree high
```

[errorexample]
```
## executesummary ← error! not need addtitle
### one , first send segment ← error! not need ### divide small node
#### 1.1 detailedanalyze ← error! not need #### divide

sectionanalyze...
```

═══════════════════════════════════════════════════════════════
[ can retrievaltool]( each sectioncall3-5 times )
═══════════════════════════════════════════════════════════════

{tools_description}

[tool using recommend - please hybrid using different tool, not need only one types ]
- insight_forge: deep degree insightanalyze, auto divide parse question topic many degree retrieval actual and relation
- panorama_search: all search, parse event all , time space line and change past process
- quick_search: fast speed validate certain tool body info point
- interview_agents: interviewsimulationAgent, fetch different role # one viewpoint and actual should

═══════════════════════════════════════════════════════════════
[flow]
═══════════════════════════════════════════════════════════════

 each times reply only can to below item one ( not can meanwhile):

optionA - calltool:
output think , then to below formatcall one tool:
<tool_call>
{{"name": "toolname", "parameters": {{"parameter name ": "parameter value "}}}}
</tool_call>
 system unified will executetool return to . not need to also not can self self write tool return .

optionB - output most end content:
 already through past tool fetch sufficient enough info, to "Final Answer:" open head outputsectioncontent.

⚠️ stop :
- stop in one times reply in meanwhilecontaintoolcall and Final Answer
- stop self self tool return (Observation), alltool system unified inject
- each times reply most many call one tool

═══════════════════════════════════════════════════════════════
[sectioncontent need ]
═══════════════════════════════════════════════════════════════

1. contentmust at toolretrieval to simulationdata
2. large amount quote original text from simulation
3. using Markdownformat( but stop using title):
   - using **bold text char ** mark point ( replace sub title)
   - using list(- or 1.2.3.)organization need point
   - using empty line divide different paragraph
   - ❌ stop using #, ##, ###, #### title language method
4. [quoteformatspecification - must single segment ]
   quotemustindependent segment , before after each has one empty line , not can in paragraph in :

   ✅ positive correct format:
   ```
   respond was recognize as actual content.

   > " should for mode in ten-thousand change social media loop in and . "

    this one common not full .
   ```

   ❌ errorformat:
   ```
   respond was recognize as actual content. > " should for mode..." this one ...
   ```
5. protect hold and its sectionlogic
6. [ avoid exempt duplicate] read below already completesectioncontent, not need duplicatedescription same info
7. [ retry strong ] not need addtitle! **bold** replace small node title"""

SECTION_USER_PROMPT_TEMPLATE = """\
 already completesectioncontent( please read , avoid exempt duplicate):
{previous_content}

═══════════════════════════════════════════════════════════════
[ before task] write section: {section_title}
═══════════════════════════════════════════════════════════════

[important]
1. read on already completesection, avoid exempt duplicate same content!
2. start before mustcalltool fetch simulationdata
3. please hybrid using different tool, not need only one types
4. reportcontentmust from self retrieval, not need using self self know recognize

[⚠️ formatwarning - must follow keep ]
- ❌ not need write title(#, ##, ###, #### all not line )
- ❌ not need write "{section_title}" as open head
- ✅ sectiontitle system unified autoadd
- ✅ directly write positive text , **bold** replace small node title

 please start:
1. first think (Thought) this section need to info
2. thencalltool(Action) fetch simulationdata
3. collect sufficient enough info after output Final Answer( pure positive text , no title)"""

# ── ReACT loop within messagetemplate ──

REACT_OBSERVATION_TEMPLATE = """\
Observation(retrieval):

═══ tool {tool_name} return ═══
{result}

═══════════════════════════════════════════════════════════════
 already calltool {tool_calls_count}/{max_tool_calls} times ( already : {used_tools_str}){unused_hint}
- ifinfo divide : to "Final Answer:" open head outputsectioncontent(mustquote on original text )
- if need to more many info: call one toolcontinueretrieval
═══════════════════════════════════════════════════════════════"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "[note] only call{tool_calls_count} times tool, few need to {min_tool_calls} times . "
    " please again calltool fetch more many simulationdata, then again output Final Answer. {unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    " before only call {tool_calls_count} times tool, few need to {min_tool_calls} times . "
    " please calltool fetch simulationdata. {unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "toolcall times number already reach on limit ({tool_calls_count}/{max_tool_calls}), not can again calltool. "
    ' please immediately at already fetch info, to "Final Answer:" open head outputsectioncontent. '
)

REACT_UNUSED_TOOLS_HINT = "\n💡 also no using past : {unused_list}, recommend test different tool fetch many degree info"

REACT_FORCE_FINAL_MSG = " already reach to toolcalllimit, please directly output Final Answer: generatesectioncontent. "

# ── Chat prompt ──

CHAT_SYSTEM_PROMPT_TEMPLATE = """\
 is one simple high simulationprediction assist .

[background]
predictioncondition: {simulation_requirement}

[ already generateanalysis report]
{report_content}

[rule]
1. at on reportcontent return answer question topic
2. directly return answer question topic , avoid exempt long think discuss
3. only in reportcontent not sufficient to return answer time , calltoolretrieval more many data
4. return answer need simple , , has entries

[ can tool]( only in need to time using , most many call1-2 times )
{tools_description}

[toolcallformat]
<tool_call>
{{"name": "toolname", "parameters": {{"parameter name ": "parameter value "}}}}
</tool_call>

[ return answer ]
- simple directly , not need long large discuss
- using > formatquotekeycontent
- to exit conclusion, again parse original because """

CHAT_OBSERVATION_SUFFIX = "\n\n please simple return answer question topic . "


# ═══════════════════════════════════════════════════════════════
# ReportAgent main class
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - simulationreportgenerateAgent

    ReACT(Reasoning + Acting)mode:
    1. segment : analyzesimulation need , reportdirectory structure
    2. generate segment : sectiongeneratecontent, each section can many times calltool fetch info
    3. think segment : check contentcomplete and correct
    """
    
    # maximum toolcall times number (eachsection)
    MAX_TOOL_CALLS_PER_SECTION = 5
    
    # maximum think round number
    MAX_REFLECTION_ROUNDS = 3
    
    # for speech in maximum toolcall times number
    MAX_TOOL_CALLS_PER_CHAT = 2
    
    def __init__(
        self, 
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None
    ):
        """
        initializeReport Agent
        
        Args:
            graph_id: graphID
            simulation_id: simulationID
            simulation_requirement: simulation need description
            llm_client: LLM Client(optional)
            zep_tools: Zeptoolservice(optional)
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        
        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()
        
        # tooldefinition
        self.tools = self._define_tools()
        
        # logging( in generate_report in initialize)
        self.report_logger: Optional[ReportLogger] = None
        # consolelogging( in generate_report in initialize)
        self.console_logger: Optional[ReportConsoleLogger] = None
        
        logger.info(t('report.agentInitDone', graphId=graph_id, simulationId=simulation_id))
    
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """definition can tool"""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": " think deep enter analyze question topic or speech topic ",
                    "report_context": " before reportsectioncontext(optional, has assist at generate more sub question topic )"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "searchquery, at relatedsort",
                    "include_expired": " is else containexpired/content(defaultTrue)"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "searchquerystring",
                    "limit": " return number amount (optional, default10)"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "interviewtheme or need description( if : ' parse for event see method ')",
                    "max_agents": " most many interviewAgent number amount (optional, default5, maximum 10)"
                }
            }
        }
    
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        executetoolcall
        
        Args:
            tool_name: toolname
            parameters: toolparameter
            report_context: reportcontext( at InsightForge)
            
        Returns:
            toolexecute(textformat)
        """
        logger.info(t('report.executingTool', toolName=tool_name, params=parameters))
        
        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()
            
            elif tool_name == "panorama_search":
                # degree search - fetch all
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()
            
            elif tool_name == "quick_search":
                # simple search - fast speed retrieval
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                return result.to_text()
            
            elif tool_name == "interview_agents":
                # deep degree interview - call actual OASISinterviewAPI fetch simulationAgent return answer ( dual )
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                return result.to_text()
            
            # ========== toward after compatible old tool(internal fixed toward to new tool) ==========
            
            elif tool_name == "search_graph":
                # fixed toward to quick_search
                logger.info(t('report.redirectToQuickSearch'))
                return self._execute_tool("quick_search", parameters, report_context)
            
            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_simulation_context":
                # fixed toward to insight_forge, because it more strong large
                logger.info(t('report.redirectToInsightForge'))
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)
            
            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            else:
                return f" not know tool: {tool_name}. please using to below tool one : insight_forge, panorama_search, quick_search"
                
        except Exception as e:
            logger.error(t('report.toolExecFailed', toolName=tool_name, error=str(e)))
            return f"toolexecutefailed: {str(e)}"
    
    # method toolname set , at JSON parse time
    VALID_TOOL_NAMES = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
         from LLMresponse in parsetoolcall

        supportformat( level ):
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. JSON(response whole body or line then is one toolcall JSON)
        """
        tool_calls = []

        # format1: XML(standardformat)
        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # format2: - LLM directly output JSON( package <tool_call> label)
        # only in format1 not match time test , avoid exempt mistake match positive text in JSON
        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # responsemaycontain think text char + JSON, test extractfinally one JSON object
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """parse exit JSON is else is method toolcall"""
        # support {"name": ..., "parameters": ...} and {"tool": ..., "params": ...} types name
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # unified name as name / parameters
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False
    
    def _get_tools_description(self) -> str:
        """generatetooldescriptiontext"""
        desc_parts = [" can tool: "]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  parameter: {params_desc}")
        return "\n".join(desc_parts)
    
    def plan_outline(
        self, 
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        reportoutline
        
         using LLManalyzesimulation need , reportdirectory structure
        
        Args:
            progress_callback: progresscallbackfunction
            
        Returns:
            ReportOutline: reportoutline
        """
        logger.info(t('report.startPlanningOutline'))
        
        if progress_callback:
            progress_callback("planning", 0, t('progress.analyzingRequirements'))
        
        # first fetch simulationcontext
        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )
        
        if progress_callback:
            progress_callback("planning", 30, t('progress.generatingOutline'))
        
        system_prompt = f"{PLAN_SYSTEM_PROMPT}\n\n{get_language_instruction()}"
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            if progress_callback:
                progress_callback("planning", 80, t('progress.parsingOutline'))
            
            # parseoutline
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))
            
            outline = ReportOutline(
                title=response.get("title", "simulationanalysis report"),
                summary=response.get("summary", ""),
                sections=sections
            )
            
            if progress_callback:
                progress_callback("planning", 100, t('progress.outlinePlanComplete'))
            
            logger.info(t('report.outlinePlanDone', count=len(sections)))
            return outline
            
        except Exception as e:
            logger.error(t('report.outlinePlanFailed', error=str(e)))
            # return defaultoutline(3 section, as fallback)
            return ReportOutline(
                title=" not from predictionreport",
                summary=" at simulationprediction not from trend and analyze",
                sections=[
                    ReportSection(title="predictionscenario and corefinding"),
                    ReportSection(title=" line as predictionanalyze"),
                    ReportSection(title="trend and hint")
                ]
            )
    
    def _generate_section_react(
        self, 
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
         using ReACTmodegenerate sectioncontent
        
        ReACTloop:
        1. Thought( think )- analyze need to info
        2. Action( line dynamic )- calltool fetch info
        3. Observation(observe)- analyzetool return
        4. duplicate straight to info sufficient enough or reach to maximum times number
        5. Final Answer( most end return answer )- generatesectioncontent
        
        Args:
            section: need generatesection
            outline: completeoutline
            previous_sections: before sectioncontent( at protect hold )
            progress_callback: progresscallback
            section_index: sectionindex( at logging)
            
        Returns:
            sectioncontent(Markdownformat)
        """
        logger.info(t('report.reactGenerateSection', title=section.title))
        
        # record sectionstartlog
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)
        
        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        # structure userprompt - each already completesection each enter maximum 4000 char
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # eachsection most many 4000 char
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "( this is # one section)"
        
        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # ReACTloop
        tool_calls_count = 0
        max_iterations = 5 # maximum iterateround number
        min_tool_calls = 3 # most few toolcall times number
        conflict_retries = 0 # toolcall and Final Answermeanwhile exit continue times number
        used_tools = set() # record already call past tool name
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        # reportcontext, at InsightForge sub question topic generate
        report_context = f"sectiontitle: {section.title}\nsimulation need : {self.simulation_requirement}"
        
        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating", 
                    int((iteration / max_iterations) * 100),
                    t('progress.deepSearchAndWrite', current=tool_calls_count, max=self.MAX_TOOL_CALLS_PER_SECTION)
                )
            
            # callLLM
            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            # check LLM return is else as None(API exception or content as empty )
            if response is None:
                logger.warning(t('report.sectionIterNone', title=section.title, iteration=iteration + 1))
                # if also has iterate times number , addmessageretry
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "(response as empty )"})
                    messages.append({"role": "user", "content": " please continuegeneratecontent. "})
                    continue
                # finally one times iterate also return None, jump exit loop enter enter strong control collect tail
                break

            logger.debug(f"LLMresponse: {response[:200]}...")

            # parse one times , repeat
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # ── process: LLM meanwhileoutputtoolcall and Final Answer ──
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    t('report.sectionConflict', title=section.title, iteration=iteration+1, conflictCount=conflict_retries)
                )

                if conflict_retries <= 2:
                    # before times : times response, need LLM new reply
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[formaterror] in one times reply in meanwhilecontaintoolcall and Final Answer, this is not . \n"
                            " each times reply only can to below item one : \n"
                            "- call one tool(output one <tool_call> block , not need write Final Answer)\n"
                            "- output most end content( to 'Final Answer:' open head , not need contain <tool_call>)\n"
                            " please new reply, only its in one item . "
                        ),
                    })
                    continue
                else:
                    # # three times : downgradeprocess, truncate to # one toolcall, strong control execute
                    logger.warning(
                        t('report.sectionConflictDowngrade', title=section.title, conflictCount=conflict_retries)
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # record LLM responselog
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # ── 1: LLM output Final Answer ──
            if has_final_answer:
                # toolcall times number not sufficient , need continuetool
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"( this some tool also not using , recommend one below : {', '.join(unused_tools)})" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                # positive normal end
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(t('report.sectionGenDone', title=section.title, count=tool_calls_count))

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # ── 2: LLM test calltool ──
            if has_tool_calls:
                # tool degree already try → correct know , need output Final Answer
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                # only execute # one toolcall
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(t('report.multiToolOnlyFirst', total=len(tool_calls), toolName=call['name']))

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                # structure not using toolhint
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list=", ".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # ── 3: notoolcall, also no Final Answer ──
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # toolcall times number not sufficient , recommend not past tool
                unused_tools = all_tools - used_tools
                unused_hint = f"( this some tool also not using , recommend one below : {', '.join(unused_tools)})" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # toolcall already sufficient enough , LLM outputcontent but with "Final Answer:" before
            # directly will this segment content as most end answer , no longer empty turn
            logger.info(t('report.sectionNoPrefix', title=section.title, count=tool_calls_count))
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer
        
        # reach to maximum iterate times number , strong control generatecontent
        logger.warning(t('report.sectionMaxIter', title=section.title))
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})
        
        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        # check strong control collect tail time LLM return is else as None
        if response is None:
            logger.error(t('report.sectionForceFailed', title=section.title))
            final_answer = t('report.sectionGenFailedContent')
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response
        
        # record sectioncontentgeneratecompletelog
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )
        
        return final_answer
    
    def generate_report(
        self, 
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        generatecompletereport( divide section actual time output)
        
        eachsectiongeneratecomplete after immediately save to folder, not need to waiting whole reportcomplete.
        file structure :
        reports/{report_id}/
            meta.json - reportinfo
            outline.json    - reportoutline
            progress.json   - generateprogress
            section_01.md - #1section
            section_02.md - #2section
            ...
            full_report.md  - completereport
        
        Args:
            progress_callback: progresscallbackfunction (stage, progress, message)
            report_id: reportID(optional, if not then autogenerate)
            
        Returns:
            Report: completereport
        """
        import uuid
        
        # ifno enter report_id, then autogenerate
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()
        
        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        # already completesectiontitlelist( at progresstrace)
        completed_section_titles = []
        
        try:
            # initialize: createreportfoldersaveinitialstatus
            ReportManager._ensure_report_folder(report_id)
            
            # initializelogging( structure log agent_log.jsonl)
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement
            )
            
            # initializeconsolelogging(console_log.txt)
            self.console_logger = ReportConsoleLogger(report_id)
            
            ReportManager.update_progress(
                report_id, "pending", 0, t('progress.initReport'),
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            # segment 1: outline
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, t('progress.startPlanningOutline'),
                completed_sections=[]
            )
            
            # record startlog
            self.report_logger.log_planning_start()
            
            if progress_callback:
                progress_callback("planning", 0, t('progress.startPlanningOutline'))
            
            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: 
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline
            
            # record completelog
            self.report_logger.log_planning_complete(outline.to_dict())
            
            # saveoutline to file
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, t('progress.outlineDone', count=len(outline.sections)),
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            logger.info(t('report.outlineSavedToFile', reportId=report_id))
            
            # segment 2: sectiongenerate( divide sectionsave)
            report.status = ReportStatus.GENERATING
            
            total_sections = len(outline.sections)
            generated_sections = [] # savecontent at context
            
            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)
                
                # updateprogress
                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    t('progress.generatingSection', title=section.title, current=section_num, total=total_sections),
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        t('progress.generatingSection', title=section.title, current=section_num, total=total_sections)
                    )
                
                # generate main sectioncontent
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage, 
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )
                
                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # savesection
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # record sectioncompletelog
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(t('report.sectionSaved', reportId=report_id, sectionNum=f"{section_num:02d}"))
                
                # updateprogress
                ReportManager.update_progress(
                    report_id, "generating", 
                    base_progress + int(70 / total_sections),
                    t('progress.sectionDone', title=section.title),
                    current_section=None,
                    completed_sections=completed_section_titles
                )
            
            # segment 3: group install completereport
            if progress_callback:
                progress_callback("generating", 95, t('progress.assemblingReport'))
            
            ReportManager.update_progress(
                report_id, "generating", 95, t('progress.assemblingReport'),
                completed_sections=completed_section_titles
            )
            
            # using ReportManager group install completereport
            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()
            
            # calculate time
            total_time_seconds = (datetime.now() - start_time).total_seconds()
            
            # record reportcompletelog
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )
            
            # save most end report
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, t('progress.reportComplete'),
                completed_sections=completed_section_titles
            )
            
            if progress_callback:
                progress_callback("completed", 100, t('progress.reportComplete'))
            
            logger.info(t('report.reportGenDone', reportId=report_id))
            
            # closeconsolelogging
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
            
        except Exception as e:
            logger.error(t('report.reportGenFailed', error=str(e)))
            report.status = ReportStatus.FAILED
            report.error = str(e)
            
            # record errorlog
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")
            
            # savefailedstatus
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, t('progress.reportFailed', error=str(e)),
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass # ignoresavefailederror
            
            # closeconsolelogging
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
    
    def chat(
        self, 
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
         and Report Agent for speech
        
        in for speech in Agent can to self main callretrievaltool from return answer question topic
        
        Args:
            message: usermessage
            chat_history: for speech
            
        Returns:
            {
                "response": "Agentreply",
                "tool_calls": [calltoollist],
                "sources": [info from source ]
            }
        """
        logger.info(t('report.agentChat', message=message[:50]))
        
        chat_history = chat_history or []
        
        # fetch already generatereportcontent
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                # limitreport long degree , avoid exempt context past long
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [reportcontent already truncate] ..."
        except Exception as e:
            logger.warning(t('report.fetchReportFailed', error=e))
        
        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "( no report)",
            tools_description=self._get_tools_description(),
        )
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        # structure message
        messages = [{"role": "system", "content": system_prompt}]
        
        # add for speech
        for h in chat_history[-10:]: # limit long degree
            messages.append(h)
        
        # addusermessage
        messages.append({
            "role": "user", 
            "content": message
        })
        
        # ReACTloop(simplify)
        tool_calls_made = []
        max_iterations = 2 # decrease few iterateround number
        
        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )
            
            # parsetoolcall
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                # notoolcall, directly return response
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
                
                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }
            
            # executetoolcall(limit number amount )
            tool_results = []
            for call in tool_calls[:1]: # each round most many execute1 times toolcall
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500] # limit long degree
                })
                tool_calls_made.append(call)
            
            # will add to message
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']}]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })
        
        # reach to maximum iterate, fetch most end response
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )
        
        # cleanupresponse
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
        
        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


class ReportManager:
    """
    report
    
    report hold storage and retrieval
    
    file structure ( divide sectionoutput):
    reports/
      {report_id}/
        meta.json - reportinfo and status
        outline.json       - reportoutline
        progress.json      - generateprogress
        section_01.md - #1section
        section_02.md - #2section
        ...
        full_report.md     - completereport
    """
    
    # reportstoragedirectory
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'reports')
    
    @classmethod
    def _ensure_reports_dir(cls):
        """ correctly protect report root directory exist in """
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """ fetch reportfolderpath"""
        return os.path.join(cls.REPORTS_DIR, report_id)
    
    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """ correctly protect reportfolder exist in return path"""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder
    
    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """ fetch reportinfofilepath"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")
    
    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """ fetch completereportMarkdownfilepath"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")
    
    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """ fetch outlinefilepath"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")
    
    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """ fetch progressfilepath"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")
    
    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """ fetch sectionMarkdownfilepath"""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")
    
    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """ fetch Agent log filespath"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")
    
    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """ fetch consolelog filespath"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")
    
    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
         fetch consolelogcontent
        
         this is reportgenerate past process in consoleoutputlog(INFO, WARNING),
         and agent_log.jsonl structure log different .
        
        Args:
            report_id: reportID
            from_line: from # several line start read fetch ( at incremental fetch , 0 table from head start)
            
        Returns:
            {
                "logs": [log line list],
                "total_lines": line number ,
                "from_line": begin line number ,
                "has_more": is else also has more many log
            }
        """
        log_path = cls._get_console_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # protect original begin log line , to end tail switch line symbol
                    logs.append(line.rstrip('\n\r'))
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False # already read fetch to end tail
        }
    
    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
         fetch completeconsolelog( one times fetch all)
        
        Args:
            report_id: reportID
            
        Returns:
            log line list
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
         fetch Agent logcontent
        
        Args:
            report_id: reportID
            from_line: from # several line start read fetch ( at incremental fetch , 0 table from head start)
            
        Returns:
            {
                "logs": [log entries item list],
                "total_lines": line number ,
                "from_line": begin line number ,
                "has_more": is else also has more many log
            }
        """
        log_path = cls._get_agent_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # skipparsefailed line
                        continue
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False # already read fetch to end tail
        }
    
    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
         fetch complete Agent log( at one times fetch all)
        
        Args:
            report_id: reportID
            
        Returns:
            log entries item list
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        savereportoutline
        
        in segment complete after immediately call
        """
        cls._ensure_report_folder(report_id)
        
        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(t('report.outlineSaved', reportId=report_id))
    
    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """
        save section

        in eachsectiongeneratecomplete after immediately call, implementation divide sectionoutput

        Args:
            report_id: reportID
            section_index: sectionindex( from 1start)
            section: sectionobject

        Returns:
            savefilepath
        """
        cls._ensure_report_folder(report_id)

        # structure sectionMarkdowncontent - cleanupmay exist in duplicatetitle
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # savefile
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(t('report.sectionFileSaved', reportId=report_id, fileSuffix=file_suffix))
        return file_path
    
    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        cleanupsectioncontent
        
        1. removecontent open head and sectiontitleduplicateMarkdowntitle line
        2. will all ### and to below level titleconvert as boldtext
        
        Args:
            content: original begin content
            section_title: sectiontitle
            
        Returns:
            cleanup after content
        """
        import re
        
        if not content:
            return content
        
        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # check is else is Markdowntitle line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()
                
                # check is else is and sectiontitleduplicatetitle(skip before 5 line within duplicate)
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue
                
                # will all level title(#, ##, ###, ####)convert as bold
                # becausesectiontitle system unified add, content in not should has title
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("") # add empty line
                continue
            
            # if on one line is was skiptitle, and before line as empty , also skip
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue
            
            skip_next_empty = False
            cleaned_lines.append(line)
        
        # remove open head empty line
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        
        # remove open head divide line
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            # meanwhileremove divide line after empty line
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)
        
        return '\n'.join(cleaned_lines)
    
    @classmethod
    def update_progress(
        cls, 
        report_id: str, 
        status: str, 
        progress: int, 
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        updatereportgenerateprogress
        
        frontend can to through past read fetch progress.json fetch actual time progress
        """
        cls._ensure_report_folder(report_id)
        
        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """ fetch reportgenerateprogress"""
        path = cls._get_progress_path(report_id)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
         fetch already generatesectionlist
        
         return all already savesectionfileinfo
        """
        folder = cls._get_report_folder(report_id)
        
        if not os.path.exists(folder):
            return []
        
        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # from file name parsesectionindex
                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections
    
    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
         group install completereport
        
         from already savesectionfile group install completereport, enter line titlecleanup
        """
        folder = cls._get_report_folder(report_id)
        
        # structure reportheader
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"
        
        # order read fetch allsectionfile
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]
        
        # after process: cleanup whole reporttitle question topic
        md_content = cls._post_process_report(md_content, outline)
        
        # savecompletereport
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(t('report.fullReportAssembled', reportId=report_id))
        return md_content
    
    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
         after processreportcontent
        
        1. removeduplicatetitle
        2. protect report main title(#) and sectiontitle(##), remove its level title(###, ####)
        3. cleanup many remaining empty line and divide line
        
        Args:
            content: original begin reportcontent
            outline: reportoutline
            
        Returns:
            process after content
        """
        import re
        
        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False
        
        # collectoutline in allsectiontitle
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # check is else is title line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # check is else is duplicatetitle( in continue 5 line within exit same contenttitle)
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    # skipduplicatetitle and its after empty line
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue
                
                # title layer level process:
                # - # (level=1) only protect report main title
                # - ## (level=2) protect sectiontitle
                # - ### and to below (level>=3) convert as boldtext
                
                if level == 1:
                    if title == outline.title:
                        # protect report main title
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # sectiontitleerror using #, positive as ##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # its one level title turn as bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # protect sectiontitle
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # non-section two level title turn as bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### and to below level titleconvert as boldtext
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False
                
                i += 1
                continue
            
            elif stripped == '---' and prev_was_heading:
                # skiptitle after tight divide line
                i += 1
                continue
            
            elif stripped == '' and prev_was_heading:
                # title after only protect one empty line
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False
            
            else:
                processed_lines.append(line)
                prev_was_heading = False
            
            i += 1
        
        # cleanup continue many empty line ( protect most many 2 )
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @classmethod
    def save_report(cls, report: Report) -> None:
        """savereportinfo and completereport"""
        cls._ensure_report_folder(report.report_id)
        
        # saveinfoJSON
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        # saveoutline
        if report.outline:
            cls.save_outline(report.report_id, report.outline)
        
        # savecompleteMarkdownreport
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)
        
        logger.info(t('report.reportSaved', reportId=report.report_id))
    
    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """ fetch report"""
        path = cls._get_report_path(report_id)
        
        if not os.path.exists(path):
            # compatible old format: check directly storage in reportsdirectory below file
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reportobject
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )
        
        # ifmarkdown_content as empty , test from full_report.md read fetch
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
        
        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error')
        )
    
    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """ root simulationID fetch report"""
        cls._ensure_reports_dir()
        
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # new format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            # compatible old format: JSONfile
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report
        
        return None
    
    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """ column exit report"""
        cls._ensure_reports_dir()
        
        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # new format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # compatible old format: JSONfile
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
        
        # create time space descending
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """deletereport( whole folder)"""
        import shutil
        
        folder_path = cls._get_report_folder(report_id)
        
        # new format: delete whole folder
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(t('report.reportFolderDeleted', reportId=report_id))
            return True
        
        # compatible old format: delete single file
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")
        
        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True
        
        return deleted
