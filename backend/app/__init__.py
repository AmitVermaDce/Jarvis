"""
Jarvis Backend - Flask should
"""

import os
import warnings

# control multiprocessing resource_tracker warning( from self # three lib if transformers)
# need to in all its import before settings
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask should function"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # settingsJSONencoding: correctly protect display text directly( not as \uXXXX format)
    # Flask >= 2.3 using app.json.ensure_ascii, old version using JSON_AS_ASCII configuration
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # settingslog
    logger = setup_logger('jarvis')
    
    # only in reloader subprocess in startinfo( avoid exempt debug mode below times )
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("Jarvis Backend start in ...")
        logger.info("=" * 50)
    
    # enableCORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # registersimulationprocesscleanupfunction( correctly protect serviceclose time end stop allsimulationprocess)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info(" already registeredsimulationprocesscleanupfunction")
        
    # boot the live data pipeline worker
    if is_reloader_process or not debug_mode:
        from .services.live_data_pipeline import live_data_pipeline
        live_data_pipeline.init_app(app)
    
    # requestlogcenter item
    @app.before_request
    def log_request():
        logger = get_logger('jarvis.request')
        logger.debug(f"request: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"request body : {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('jarvis.request')
        logger.debug(f"response: {response.status_code}")
        return response
    
    # register chart
    from .api import graph_bp, simulation_bp, report_bp, scenarios_bp, demand_signals_bp
    from .api.demand_sensing import create_demand_sensing_blueprint

    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(scenarios_bp, url_prefix='/api/scenarios')
    app.register_blueprint(demand_signals_bp, url_prefix='/api/demand-signals')

    # Register demand sensing blueprint
    demand_sensing_bp = create_demand_sensing_blueprint()
    app.register_blueprint(demand_sensing_bp)
    
    # health check
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'Jarvis Backend'}
    
    if should_log_startup:
        logger.info("Jarvis Backend startcomplete")
    
    return app

