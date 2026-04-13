"""
Jarvis Backend start enter port
"""

import os
import sys

# parse Windows console in Chinese code question topic : in allimport before settings UTF-8 encoding
if sys.platform == 'win32':
    # settingsenvironment variable correctly protect Python using UTF-8
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    # new configurationstandardoutput flow as UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# addproject root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config


def main():
    """ main function"""
    # validateconfiguration
    errors = Config.validate()
    if errors:
        print("configurationerror:")
        for err in errors:
            print(f"  - {err}")
        print("\n please check .env file in configuration")
        sys.exit(1)
    
    # create should
    app = create_app()
    
    # fetch runconfiguration
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = Config.DEBUG
    
    # startservice
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()

