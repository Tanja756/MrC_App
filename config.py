import configparser
import os
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        cfg.write(f)


def get_default_config():
    cfg = configparser.ConfigParser()
    cfg['Yandex'] = {
        'token': '',
        'refresh_token': '',
        'username': '',
    }
    cfg['OneC'] = {
        'login': '',
        'password': '',
        'server': '',
        'port': '',
        'database': '',
    }
    cfg['App'] = {
        'sync_interval_minutes': '10',
        'fias_normalize': 'false',
        'theme': 'light',
        'default_warehouse': '',
        'profile_name': '',
        'export_xls': 'false',
    }
    return cfg


def ensure_config():
    if not os.path.exists(CONFIG_FILE):
        cfg = get_default_config()
        save_config(cfg)
        logger.info(f"Created default config at {CONFIG_FILE}")
    return load_config()


YANDEX_CLIENT_ID = "92d443d2192447ffbc22e9846a3d117f"
YANDEX_CLIENT_SECRET = "3a75b47178934afa8d140f5b7b361c65"