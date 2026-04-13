"""
Scenario Preset API
Provides seed files and configuration for preset scenarios.
"""

import os
import json
import logging
from flask import Blueprint, send_file, jsonify

logger = logging.getLogger(__name__)

scenarios_bp = Blueprint('scenarios', __name__)

# Directory path
SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), '../../../scenarios')


def get_scenario_config():
    """Get all available scenario configurations."""
    scenarios = []

    if not os.path.exists(SCENARIOS_DIR):
        return scenarios

    for scenario_dir in sorted(os.listdir(SCENARIOS_DIR)):
        scenario_path = os.path.join(SCENARIOS_DIR, scenario_dir)
        if not os.path.isdir(scenario_path):
            continue

        # Find configuration file
        config_path = os.path.join(scenario_path, 'scenario.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config['id'] = scenario_dir
            scenarios.append(config)
        else:
            # Auto-discover: list all seed_*.md files
            seed_files = [f for f in os.listdir(scenario_path)
                          if f.startswith('seed_') and f.endswith('.md')]
            if seed_files:
                scenarios.append({
                    'id': scenario_dir,
                    'name': scenario_dir.replace('_', ' ').title(),
                    'description': f'Scenario with {len(seed_files)} seed files',
                    'seed_files': seed_files,
                    'simulation_requirement': ''
                })

    return scenarios


@scenarios_bp.route('/list', methods=['GET'])
def list_scenarios():
    """List all available scenario presets."""
    try:
        scenarios = get_scenario_config()
        return jsonify({
            'success': True,
            'data': {
                'scenarios': scenarios,
                'count': len(scenarios)
            }
        })
    except Exception as e:
        logger.error(f"Failed to list scenarios: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scenarios_bp.route('/<scenario_id>', methods=['GET'])
def get_scenario(scenario_id):
    """Get a single scenario's detailed configuration."""
    try:
        scenario_path = os.path.join(SCENARIOS_DIR, scenario_id)
        if not os.path.exists(scenario_path):
            return jsonify({
                'success': False,
                'error': f'Scenario not found: {scenario_id}'
            }), 404

        config_path = os.path.join(scenario_path, 'scenario.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config['id'] = scenario_id
        else:
            seed_files = [f for f in os.listdir(scenario_path)
                          if f.startswith('seed_') and f.endswith('.md')]
            config = {
                'id': scenario_id,
                'name': scenario_id.replace('_', ' ').title(),
                'seed_files': seed_files,
                'simulation_requirement': ''
            }

        return jsonify({
            'success': True,
            'data': config
        })
    except Exception as e:
        logger.error(f"Failed to get scenario {scenario_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scenarios_bp.route('/<scenario_id>/file/<filename>', methods=['GET'])
def get_scenario_file(scenario_id, filename):
    """Download a scenario seed file."""
    try:
        file_path = os.path.join(SCENARIOS_DIR, scenario_id, filename)
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': f'File not found: {filename}'
            }), 404

        # Safety check: ensure path doesn't escape
        real_path = os.path.realpath(file_path)
        real_scenarios = os.path.realpath(SCENARIOS_DIR)
        if not real_path.startswith(real_scenarios):
            return jsonify({
                'success': False,
                'error': 'Invalid file path'
            }), 403

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Failed to serve file {filename}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
