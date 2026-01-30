"""
Configuration Manager Module
Handles loading and saving configuration from app.config file.
"""

import configparser
import os
from typing import Dict, Any, Optional

# Path to config file
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.config')


def load_config() -> configparser.ConfigParser:
    """Load configuration from app.config file."""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    return config


def save_config(config: configparser.ConfigParser):
    """Save configuration to app.config file."""
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)


def get_nopcommerce_config() -> Dict[str, str]:
    """Get nopCommerce configuration settings."""
    config = load_config()
    return {
        'api_url': config.get('NOPCOMMERCE', 'NOP_API_URL', fallback='https://localhost:59543/api'),
        'secret_key': config.get('NOPCOMMERCE', 'NOP_SECRET_KEY', fallback=''),
        'admin_username': config.get('NOPCOMMERCE', 'NOP_ADMIN_USERNAME', fallback=''),
        'admin_password': config.get('NOPCOMMERCE', 'NOP_ADMIN_PASSWORD', fallback=''),
        'verify_ssl': config.get('NOPCOMMERCE', 'NOP_VERIFY_SSL', fallback='false'),
    }


def get_db_config() -> Dict[str, Any]:
    """Get database configuration settings."""
    config = load_config()
    return {
        'host': config.get('DATABASE', 'DB_HOST', fallback='localhost'),
        'port': config.getint('DATABASE', 'DB_PORT', fallback=5432),
        'database': config.get('DATABASE', 'DB_NAME', fallback='ChatBot'),
        'user': config.get('DATABASE', 'DB_USER', fallback='postgres'),
        'password': config.get('DATABASE', 'DB_PASSWORD', fallback='12345'),
        'driver': config.get('DATABASE', 'DB_DRIVER', fallback='ODBC Driver 17 for SQL Server'),
    }


def get_widget_config() -> Dict[str, str]:
    """Get widget configuration settings."""
    config = load_config()
    return {
        'title': config.get('WIDGET', 'WIDGET_TITLE', fallback='IT Support'),
        'subtitle': config.get('WIDGET', 'WIDGET_SUBTITLE', fallback='How can I help you today?'),
    }


def get_all_config() -> Dict[str, str]:
    """Get all configuration as flat dictionary for admin API."""
    config = load_config()
    result = {}
    
    # Database settings
    result['DB_HOST'] = config.get('DATABASE', 'DB_HOST', fallback='localhost')
    result['DB_PORT'] = config.get('DATABASE', 'DB_PORT', fallback='5432')
    result['DB_NAME'] = config.get('DATABASE', 'DB_NAME', fallback='ChatBot')
    result['DB_USER'] = config.get('DATABASE', 'DB_USER', fallback='postgres')
    result['DB_PASSWORD'] = config.get('DATABASE', 'DB_PASSWORD', fallback='')
    result['DB_DRIVER'] = config.get('DATABASE', 'DB_DRIVER', fallback='ODBC Driver 17 for SQL Server')
    
    # Rasa settings
    result['RASA_API_URL'] = config.get('RASA', 'RASA_API_URL', fallback='http://localhost:5005')
    
    # Widget settings
    result['WIDGET_TITLE'] = config.get('WIDGET', 'WIDGET_TITLE', fallback='')
    result['WIDGET_SUBTITLE'] = config.get('WIDGET', 'WIDGET_SUBTITLE', fallback='')
    
    # nopCommerce settings
    result['NOP_API_URL'] = config.get('NOPCOMMERCE', 'NOP_API_URL', fallback='')
    result['NOP_SECRET_KEY'] = config.get('NOPCOMMERCE', 'NOP_SECRET_KEY', fallback='')
    result['NOP_ADMIN_USERNAME'] = config.get('NOPCOMMERCE', 'NOP_ADMIN_USERNAME', fallback='')
    result['NOP_ADMIN_PASSWORD'] = config.get('NOPCOMMERCE', 'NOP_ADMIN_PASSWORD', fallback='')
    result['NOP_VERIFY_SSL'] = config.get('NOPCOMMERCE', 'NOP_VERIFY_SSL', fallback='false')
    
    return result


def set_all_config(settings: Dict[str, str]):
    """Save all configuration from flat dictionary."""
    config = load_config()
    
    # Ensure sections exist
    for section in ['DATABASE', 'RASA', 'WIDGET', 'NOPCOMMERCE']:
        if not config.has_section(section):
            config.add_section(section)
    
    # Map flat keys to sections
    key_map = {
        'DB_HOST': ('DATABASE', 'DB_HOST'),
        'DB_PORT': ('DATABASE', 'DB_PORT'),
        'DB_NAME': ('DATABASE', 'DB_NAME'),
        'DB_USER': ('DATABASE', 'DB_USER'),
        'DB_PASSWORD': ('DATABASE', 'DB_PASSWORD'),
        'DB_DRIVER': ('DATABASE', 'DB_DRIVER'),
        'RASA_API_URL': ('RASA', 'RASA_API_URL'),
        'WIDGET_TITLE': ('WIDGET', 'WIDGET_TITLE'),
        'WIDGET_SUBTITLE': ('WIDGET', 'WIDGET_SUBTITLE'),
        'NOP_API_URL': ('NOPCOMMERCE', 'NOP_API_URL'),
        'NOP_SECRET_KEY': ('NOPCOMMERCE', 'NOP_SECRET_KEY'),
        'NOP_ADMIN_USERNAME': ('NOPCOMMERCE', 'NOP_ADMIN_USERNAME'),
        'NOP_ADMIN_PASSWORD': ('NOPCOMMERCE', 'NOP_ADMIN_PASSWORD'),
        'NOP_VERIFY_SSL': ('NOPCOMMERCE', 'NOP_VERIFY_SSL'),
    }
    
    for key, value in settings.items():
        if key in key_map:
            section, option = key_map[key]
            config.set(section, option, str(value) if value else '')
    
    save_config(config)


def set_config_value(key: str, value: str):
    """Set a single configuration value."""
    set_all_config({key: value})
