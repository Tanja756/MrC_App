import json
import logging
import hashlib
from config import load_config
from yadisk_client import YandexDiskClient
from db import (
    upsert_tasks, upsert_products, upsert_storages, upsert_clients,
    upsert_balances, upsert_fn_schedule, upsert_ppr_tasks,
    get_sync_state, set_sync_state
)

logger = logging.getLogger(__name__)

SYNC_FILES = {
    'tasks_user': 'tasks_user.json',
    'tasks_free': 'tasks_free.json',
    'tasks_closed': 'tasks_closed.json',
    'references': 'references.json',
    'warehouse': 'warehouse.json',
    'fn_schedule': 'fn_schedule.json',
    'ppr_list': 'ppr_list.json',
}


def compute_hash(data):
    raw = json.dumps(data, ensure_ascii=False, default=str, sort_keys=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def sync_from_yandex(client=None, username=None):
    cfg = load_config()
    if not username:
        username = cfg.get('OneC', 'login', fallback='')
    if not username:
        logger.error("1C login not configured")
        return {'error': '1C login not configured'}

    if not client:
        client = YandexDiskClient()

    results = {}
    for key, filename in SYNC_FILES.items():
        remote_path = f"{username}/{filename}"
        data = client.download_json(remote_path)
        if data is None:
            results[key] = {'status': 'not_found'}
            continue

        file_hash = compute_hash(data)
        prev_hash = get_sync_state(f"hash_{key}")
        if prev_hash == file_hash:
            results[key] = {'status': 'unchanged'}
            continue

        try:
            _import_data(key, data)
            set_sync_state(f"hash_{key}", file_hash)
            results[key] = {'status': 'imported'}
            logger.info(f"Imported {key} ({len(str(data))} bytes)")
        except Exception as e:
            results[key] = {'status': 'error', 'error': str(e)}
            logger.error(f"Failed to import {key}: {e}")

    return results


def _import_data(key, data, username='local'):
    if key == 'tasks_user':
        _import_tasks(data, 'my', username)
    elif key == 'tasks_free':
        _import_tasks(data, 'free', username)
    elif key == 'tasks_closed':
        _import_tasks(data, 'closed', username)
    elif key == 'references':
        _import_references(data)
    elif key == 'warehouse':
        _import_warehouse(data)
    elif key == 'fn_schedule':
        _import_fn_schedule(data)
    elif key == 'ppr_list':
        _import_ppr(data)


def _import_tasks(data, category, username):
    tasks = data if isinstance(data, list) else data.get('tasks', data.get('rows', []))
    for t in tasks:
        if not t.get('guid'):
            continue
        t['category'] = category
        if category == 'closed' and not t.get('closed_at'):
            t['closed_at'] = t.get('date')
    upsert_tasks(tasks)


def _import_references(data):
    products = data.get('products', [])
    if products:
        upsert_products(products)
    storages = data.get('storages', [])
    if storages:
        upsert_storages(storages)
    clients = data.get('clients', [])
    if clients:
        upsert_clients(clients)


def _import_warehouse(data):
    items = []
    rows = data if isinstance(data, list) else data.get('balances', data.get('rows', []))
    if rows:
        items = rows
    elif isinstance(data, dict):
        for storage_guid, balance_list in data.items():
            for b in balance_list:
                b['storage_guid'] = storage_guid
                b['quantity'] = b.pop('balance', b.get('quantity', 0))
            items.extend(balance_list)
    if items:
        from db import clear_warehouse_balances
        guids = set(b.get('storage_guid') for b in items if b.get('storage_guid'))
        for g in guids:
            clear_warehouse_balances(g)
        upsert_balances(items)


def _import_fn_schedule(data):
    items = data if isinstance(data, list) else data.get('rows', data.get('items', []))
    if items:
        upsert_fn_schedule(items)


def _import_ppr(data):
    items = data if isinstance(data, list) else data.get('rows', data.get('items', []))
    if items:
        upsert_ppr_tasks(items)