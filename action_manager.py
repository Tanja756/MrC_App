import os
import json
import logging
import threading
import time
from datetime import datetime
from config import load_config
from yadisk_client import YandexDiskClient
from db import get_pending_actions, mark_action_uploaded, get_task

logger = logging.getLogger(__name__)

ACTIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'actions')


def ensure_actions_dir():
    os.makedirs(ACTIONS_DIR, exist_ok=True)


def create_action_file(action_type, guid, task_data=None):
    ensure_actions_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{action_type}_{guid}_{timestamp}.json"
    filepath = os.path.join(ACTIONS_DIR, filename)
    action = {
        'type': action_type,
        'guid': guid,
        'timestamp': datetime.now().isoformat(),
    }
    if task_data:
        action['task'] = task_data
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(action, f, ensure_ascii=False, indent=2)
    logger.info(f"Created action file: {filename}")
    return filepath


def upload_pending_actions(client=None):
    if not client:
        client = YandexDiskClient()
    if not client.token:
        logger.warning("No Yandex token, cannot upload actions")
        return 0

    cfg = load_config()
    username = cfg.get('OneC', 'login', fallback='')
    if not username:
        logger.warning("1C login not configured")
        return 0

    pending = get_pending_actions()
    if not pending:
        return 0

    uploaded = 0
    for action in pending:
        task = get_task(action['guid'])
        action_data = {
            'action_type': action['type'],
            'guid': action['guid'],
            'created_at': action['created_at'],
            'task': task,
        }
        remote_path = f"{username}/actions/{action['type']}_{action['guid']}_{action['id']}.json"
        ok = client.upload_json(remote_path, action_data)
        if ok:
            mark_action_uploaded(action['id'])
            uploaded += 1

    return uploaded


def upload_all_actions(client=None):
    if not client:
        client = YandexDiskClient()
    if not client.token:
        logger.warning("No Yandex token configured")
        return 0

    ensure_actions_dir()
    cfg = load_config()
    username = cfg.get('OneC', 'login', fallback='')
    if not username:
        logger.error("1C login not configured")
        return 0

    uploaded = 0
    for fname in os.listdir(ACTIONS_DIR):
        if not fname.endswith('.json'):
            continue
        filepath = os.path.join(ACTIONS_DIR, fname)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            remote_path = f"{username}/actions/{fname}"
            ok = client.upload_json(remote_path, data)
            if ok:
                os.remove(filepath)
                uploaded += 1
        except Exception as e:
            logger.error(f"Failed to upload {fname}: {e}")

    return uploaded


_upload_thread = None
_upload_stop = threading.Event()


def start_auto_upload(interval_minutes=2):
    global _upload_thread, _upload_stop
    _upload_stop.clear()

    def _loop():
        while not _upload_stop.is_set():
            try:
                count = upload_all_actions()
                if count:
                    logger.info(f"Auto-uploaded {count} action files")
            except Exception as e:
                logger.error(f"Auto-upload error: {e}")
            _upload_stop.wait(interval_minutes * 60)

    _upload_thread = threading.Thread(target=_loop, daemon=True)
    _upload_thread.start()
    logger.info(f"Auto-upload started (interval={interval_minutes} min)")


def stop_auto_upload():
    global _upload_thread, _upload_stop
    _upload_stop.set()
    if _upload_thread:
        _upload_thread.join(timeout=5)
        _upload_thread = None