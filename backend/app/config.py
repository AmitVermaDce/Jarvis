"""
Application configuration.
Loads configuration from project root .env file, with .env.local overrides.
"""

import os
from dotenv import load_dotenv

# Load project root .env file first
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')
if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    load_dotenv(override=True)

# Load .env.local with highest priority (user overrides)
local_env = os.path.join(os.path.dirname(__file__), '../../.env.local')
if os.path.exists(local_env):
    load_dotenv(local_env, override=True)


def _resolve_llm_config():
    """Resolve LLM configuration, supporting Ollama and other providers."""
    model = os.environ.get('MODEL_NAME') or os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    ollama_host = os.environ.get('OLLAMA_HOST', '')
    base_url = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    api_key = os.environ.get('LLM_API_KEY', '')

    if ollama_host:
        base_url = f"{ollama_host.rstrip('/')}/v1"
        if not api_key:
            api_key = 'ollama'
    return api_key, base_url, model


class Config:
    """Flask application configuration class."""
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'jarvis-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON configuration - disable ASCII encoding so text displays directly (not \uXXXX)
    JSON_AS_ASCII = False
    
    # LLM configuration (OpenAI-compatible format)
    _llm_api_key, _llm_base_url, _llm_model = _resolve_llm_config()
    LLM_API_KEY = _llm_api_key
    LLM_BASE_URL = _llm_base_url
    LLM_MODEL_NAME = _llm_model
    
    # File upload configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # Text processing configuration
    DEFAULT_CHUNK_SIZE = 500  # Default chunk size
    DEFAULT_CHUNK_OVERLAP = 50  # Default overlap size
    
    # Live data ingestion configuring
    LIVE_POLL_INTERVAL = int(os.environ.get('LIVE_POLL_INTERVAL', '1'))  # Hours
    LIVE_DATA_SOURCES = os.environ.get('LIVE_DATA_SOURCES', 'all')  # 'duckduckgo', 'yfinance', or 'all'
    
    # OASIS simulation configurationuration
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS available actions configuration
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent configuration
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # Demand Sensing configuration
    DEMAND_SENSING_ENABLED = os.environ.get('DEMAND_SENSING_ENABLED', 'false').lower() == 'true'
    DEMAND_SIGNAL_SOURCES = os.environ.get('DEMAND_SIGNAL_SOURCES', '').split(',') if os.environ.get('DEMAND_SIGNAL_SOURCES') else ['pos', 'weather', 'inventory', 'promotion']
    DEMAND_DEVIATION_THRESHOLD = float(os.environ.get('DEMAND_DEVIATION_THRESHOLD', '15.0'))  # percentage
    DEMAND_FORECAST_DAYS = int(os.environ.get('DEMAND_FORECAST_DAYS', '14'))

    # External API configurations (for demand signals)
    ERP_API_URL = os.environ.get('ERP_API_URL', '')
    ERP_API_KEY = os.environ.get('ERP_API_KEY', '')
    WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY', '')

    @classmethod
    def validate(cls):
        """Validate required configuration values."""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY not configured")
        return errors

