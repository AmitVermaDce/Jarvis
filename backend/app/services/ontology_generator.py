"""
ontologygenerateservice
API1: analyzetextcontent, generate will simulationentity and relation typesdefinition
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction

logger = logging.getLogger(__name__)


def _to_pascal_case(name: str) -> str:
    """ will anyformatnameconvert as PascalCase( if 'works_for' -> 'WorksFor', 'person' -> 'Person')"""
    # non- char number char character divide
    parts = re.split(r'[^a-zA-Z0-9]+', name)
    # again camelCase divide ( if 'camelCase' -> ['camel', 'Case'])
    words = []
    for part in parts:
        words.extend(re.sub(r'([a-z])([A-Z])', r'\1_\2', part).split('_'))
    # each first char large write , filter empty string
    result = ''.join(word.capitalize() for word in words if word)
    return result if result else 'Unknown'


# ontologygenerate system unified hint
ONTOLOGY_SYSTEM_PROMPT = """ is one knowledge graphontology. task is analyze to fixed textcontent and simulation need , **social media opinion simulation**entity types and relation types.

**important: mustoutputvalidJSONformatdata, not need output its content. **

## coretaskbackground

currently structure one **Social Media Opinion Simulation System**. in this system unified in :
- eachentity all is one can to in social media on speak, interaction, propagationinfo" number " or " main body "
- entity space will shadow , repost, comment, respond
- need to simulationpublic opinionevent in each should and infopropagationpath

therefore, **entitymust is actual in actual exist in , can to in on speak and interaction main body **:

** can to is **:
- tool body (, , meaning view , , common through )
- , ( package its number )
- organizationinstitution( large , will , NGO, will )
- part , institution
- body institution(, , self body , network )
- social media
- special fixed group table ( if will , , group)

** not can to is **:
- abstract( if "public opinion", "", "trend")
- theme/ speech topic ( if " technique ", "")
- viewpoint/stance( if "support", "oppose")

## outputformat

 please outputJSONformat, contain to below structure :

```json
{
    "entity_types": [
        {
            "name": "entity typesname( text , PascalCase)",
            "description": " simple short description( text , not exceed past 100character)",
            "attributes": [
                {
                    "name": "attribute name ( text , snake_case)",
                    "type": "text",
                    "description": "attributedescription"
                }
            ],
            "examples": ["exampleentity1", "exampleentity2"]
        }
    ],
    "edge_types": [
        {
            "name": "relation typesname( text , UPPER_SNAKE_CASE)",
            "description": " simple short description( text , not exceed past 100character)",
            "source_targets": [
                {"source": " source entity types", "target": " item mark entity types"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": " for textcontentbriefanalyzedescription"
}
```

## point ( its important! )

### 1. entity types - must follow keep

** number amount need : must positive good 10 entity types**

** layer times structure need (mustmeanwhilecontain tool body type and type)**:

10 entity typesmustcontain to below layer times :

A. **type(mustcontain, place in listfinally2 )**:
   - `Person`: self body type. one not belong at its more tool body type time , enter this class.
   - `Organization`: organizationinstitutiontype. one organization not belong at its more tool body organizationtype time , enter this class.

B. ** tool body type(8 , root textcontent)**:
   - for text in exit mainrole, more tool body type
   - if : iftext and technique event, can to has `Student`, `Professor`, `University`
   - if : iftext and event, can to has `Company`, `CEO`, `Employee`

** as need to type**:
- text in will exit each types , if " in small ", " path ", " certain network "
- ifnotypematch, should was enter `Person`
- same , small type organization, temporary body should enter `Organization`

** tool body type original then **:
- from text in identify exit high frequency exit or keyroletype
- each tool body typeshould has correct , avoid exempt
- description mustdescription this type and type area

### 2. relation types

- number amount : 6-10
- relationshouldinteraction in actual system
- correctly protect relation source_targets cover definitionentity types

### 3. attribute

- eachentity types1-3 keyattribute
- **note**: attribute name not can using `name`, `uuid`, `group_id`, `created_at`, `summary`( this some is system unified protect char )
- recommend using : `full_name`, `title`, `role`, `position`, `location`, `description`

## entity typesreference

** class( tool body )**:
- Student:
- Professor: /
- Journalist:
- Celebrity: / network
- Executive: high
- Official:
- Lawyer:
- Doctor:

** class()**:
- Person: self ( not belong at on tool body type time using )

**organizationclass( tool body )**:
- University: high
- Company:
- GovernmentAgency: institution
- MediaOutlet: body institution
- Hospital:
- School: in small
- NGO: non-organization

**organizationclass()**:
- Organization: organizationinstitution( not belong at on tool body type time using )

## relation typesreference

- WORKS_FOR: at
- STUDIES_AT: then read at
- AFFILIATED_WITH: belong at
- REPRESENTS: table
- REGULATES:
- REPORTS_ON:
- COMMENTS_ON: comment
- RESPONDS_TO: respond
- SUPPORTS: support
- OPPOSES: oppose
- COLLABORATES_WITH:
- COMPETES_WITH:
"""


class OntologyGenerator:
    """
    ontologygenerate
    analyzetextcontent, generateentity and relation typesdefinition
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        generateontologydefinition
        
        Args:
            document_texts: text textlist
            simulation_requirement: simulation need description
            additional_context: outside context
            
        Returns:
            ontologydefinition(entity_types, edge_types)
        """
        # structure usermessage
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        lang_instruction = get_language_instruction()
        system_prompt = f"{ONTOLOGY_SYSTEM_PROMPT}\n\n{lang_instruction}\nIMPORTANT: Entity type names MUST be in English PascalCase (e.g., 'PersonEntity', 'MediaOrganization'). Relationship type names MUST be in English UPPER_SNAKE_CASE (e.g., 'WORKS_FOR'). Attribute names MUST be in English snake_case. Only description fields and analysis_summary should use the specified language above."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # callLLM
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        # validate and after process
        result = self._validate_and_process(result)
        
        return result
    
    # to LLM text maximum long degree (5 ten-thousand char )
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """ structure usermessage"""
        
        # mergetext
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # iftext exceed past 5 ten-thousand char , truncate( only shadow to LLMcontent, not shadow graph buildinging)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...( original text {original_length} char , already truncate before {self.MAX_TEXT_LENGTH_FOR_LLM} char at ontologyanalyze)..."
        
        message = f"""## simulation need

{simulation_requirement}

## text content

{combined_text}
"""
        
        if additional_context:
            message += f"""
## outside description

{additional_context}
"""
        
        message += """
 please root to on content, will public opinionsimulationentity types and relation types.

**must follow keep rule**:
1. must positive good output10 entity types
2. finally2 must is type: Person( ) and Organization(organization)
3. before 8 is root textcontent tool body type
4. allentity typesmust is actual in can to speak main body , not can is abstract
5. attribute name not can using name, uuid, group_id protect char , full_name, org_name replace
"""
        
        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """validate and after process"""
        
        # correctly protect need char segment exist in
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""
        
        # validateentity types
        # record original begin name to PascalCase mapping, at after continue positive edge source_targets quote
        entity_name_map = {}
        for entity in result["entity_types"]:
            # strong control will entity name turn as PascalCase(Zep API need )
            if "name" in entity:
                original_name = entity["name"]
                entity["name"] = _to_pascal_case(original_name)
                if entity["name"] != original_name:
                    logger.warning(f"Entity type name '{original_name}' auto-converted to '{entity['name']}'")
                entity_name_map[original_name] = entity["name"]
            if "attributes" not in entity:
                entity["attributes"] = []
            # Sanitize attributes: ensure each is a dict with 'name'
            sanitized_attrs = []
            for attr in entity["attributes"]:
                if isinstance(attr, str):
                    sanitized_attrs.append({"name": attr, "type": "text", "description": attr})
                elif isinstance(attr, dict) and "name" in attr:
                    sanitized_attrs.append(attr)
                elif isinstance(attr, dict):
                    # Try alternate keys
                    attr_name = attr.get("attribute") or attr.get("field") or attr.get("key")
                    if attr_name:
                        attr["name"] = attr_name
                        sanitized_attrs.append(attr)
                    else:
                        logger.warning(f"Dropping malformed attribute in entity '{entity.get('name', '?')}': {attr}")
                else:
                    logger.warning(f"Dropping invalid attribute type in entity '{entity.get('name', '?')}': {attr}")
            entity["attributes"] = sanitized_attrs
            if "examples" not in entity:
                entity["examples"] = []
            # correctly protect description not exceed past 100character
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # validaterelation types
        for edge in result["edge_types"]:
            # strong control will edge name turn as SCREAMING_SNAKE_CASE(Zep API need )
            if "name" in edge:
                original_name = edge["name"]
                edge["name"] = original_name.upper()
                if edge["name"] != original_name:
                    logger.warning(f"Edge type name '{original_name}' auto-converted to '{edge['name']}'")
            # positive source_targets in entitynamequote, and convert after PascalCase protect hold one
            for st in edge.get("source_targets", []):
                if st.get("source") in entity_name_map:
                    st["source"] = entity_name_map[st["source"]]
                if st.get("target") in entity_name_map:
                    st["target"] = entity_name_map[st["target"]]
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            # Sanitize edge attributes
            sanitized_attrs = []
            for attr in edge["attributes"]:
                if isinstance(attr, str):
                    sanitized_attrs.append({"name": attr, "type": "text", "description": attr})
                elif isinstance(attr, dict) and "name" in attr:
                    sanitized_attrs.append(attr)
                elif isinstance(attr, dict):
                    attr_name = attr.get("attribute") or attr.get("field") or attr.get("key")
                    if attr_name:
                        attr["name"] = attr_name
                        sanitized_attrs.append(attr)
                    else:
                        logger.warning(f"Dropping malformed attribute in edge '{edge.get('name', '?')}': {attr}")
                else:
                    logger.warning(f"Dropping invalid attribute type in edge '{edge.get('name', '?')}': {attr}")
            edge["attributes"] = sanitized_attrs
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        # Zep API limit: most many 10 customentity types, most many 10 customtype
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # deduplicate: name deduplicate, protect first times exit
        seen_names = set()
        deduped = []
        for entity in result["entity_types"]:
            name = entity.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                deduped.append(entity)
            elif name in seen_names:
                logger.warning(f"Duplicate entity type '{name}' removed during validation")
        result["entity_types"] = deduped

        # typedefinition
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        # check is else already has type
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # need to addtype
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # ifadd after will exceed past 10 , need to be removed one some has type
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # calculate need to be removed many few
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # from end tail remove( protect before surface more important tool body type)
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # addtype
            result["entity_types"].extend(fallbacks_to_add)
        
        # most end correctly protect not exceed past limit( prevent process )
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
         will ontologydefinitionconvert as Python code (classontology.py)
        
        Args:
            ontology: ontologydefinition
            
        Returns:
            Python code string
        """
        code_lines = [
            '"""',
            'customentity typesdefinition',
            'Jarvisautogenerate, at will public opinionsimulation',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== entity typesdefinition ==============',
            '',
        ]
        
        # generateentity types
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== relation typesdefinition ==============')
        code_lines.append('')
        
        # generaterelation types
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # convert as PascalCaseclass name
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # generatetypedictionary
        code_lines.append('# ============== typeconfiguration ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # generatesource_targetsmapping
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)

