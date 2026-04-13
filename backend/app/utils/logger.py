"""
logconfiguration model block
 provide unified log, meanwhileoutput to console and file
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler


def _ensure_utf8_stdout():
    """
     correctly protect stdout/stderr using UTF-8 encoding
     parse Windows console in Chinese code question topic
    """
    if sys.platform == 'win32':
        # Windows below new configurationstandardoutput as UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# logdirectory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logger(name: str = 'jarvis', level: int = logging.DEBUG) -> logging.Logger:
    """
    settingslog
    
    Args:
        name: logname
        level: log level
        
    Returns:
        configuration good log
    """
    # correctly protect logdirectory exist in
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # createlog
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # stop log toward upload to root logger, avoid exempt duplicateoutput
    logger.propagate = False
    
    # ifalready has process, not duplicateadd
    if logger.handlers:
        return logger
    
    # logformat
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 1. file processing - detailedlog( day period name , with round turn )
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_filename),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # 2. consoleprocess - simple log(INFO and to on )
    # correctly protect Windows below using UTF-8 encoding, avoid exempt in Chinese code
    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # addprocess
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'jarvis') -> logging.Logger:
    """
     fetch log(if not exist then create)
    
    Args:
        name: logname
        
    Returns:
        loginstance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# createdefaultlog
logger = setup_logger()


# then method
def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)

