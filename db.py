import sqlite3
import logging
import json
import os
import hashlib

logger = logging.getLogger(__name__)

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(DB_DIR, 'mrc_data.db')


def lower_ru(text):
    return text.lower() if text else None


def upper_ru(text):
    return text.upper() if text else None


def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.create_function("LOWER_RU", 1, lower_ru)
    conn.create_function("UPPER_RU", 1, upper_ru)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS shops (
            shop_number TEXT NOT NULL,
            sap_code TEXT NOT NULL,
            address TEXT NOT NULL,
            UNIQUE(shop_number, sap_code)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS fias_cache (
            raw TEXT PRIMARY KEY,
            normalized TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            guid TEXT PRIMARY KEY,
            number TEXT,
            name TEXT,
            description TEXT,
            status TEXT,
            name_department TEXT,
            user TEXT,
            guid_client TEXT,
            hasAttachments INTEGER DEFAULT 0,
            date TEXT,
            period TEXT,
            priority INTEGER DEFAULT 0,
            closed_at TEXT,
            category TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    try:
        c.execute("ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT ''")
    except Exception:
        pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS task_tracking (
            guid TEXT NOT NULL,
            username TEXT NOT NULL,
            taken_at TEXT,
            closed_at TEXT,
            task_name TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (guid, username)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            guid TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            article TEXT NOT NULL DEFAULT '',
            unit TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS storages (
            guid TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            guid TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            inn TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS warehouse_balances (
            storage_guid TEXT NOT NULL,
            product_guid TEXT NOT NULL,
            product_name TEXT NOT NULL,
            series_name TEXT NOT NULL DEFAULT '',
            inventory_number TEXT NOT NULL DEFAULT '',
            quantity REAL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (storage_guid, product_guid, inventory_number)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS balance_item_meta (
            storage_guid TEXT NOT NULL,
            product_name TEXT NOT NULL,
            series_name TEXT NOT NULL DEFAULT '',
            inventory_number TEXT NOT NULL DEFAULT '',
            broken INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (storage_guid, product_name, series_name, inventory_number)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS fn_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_number TEXT,
            sap_code TEXT,
            address TEXT,
            cashreg_number TEXT,
            engineer TEXT,
            month TEXT,
            fn_expiry TEXT,
            kkt_serial TEXT,
            be_name TEXT DEFAULT '',
            cluster_name TEXT DEFAULT '',
            gp_name TEXT DEFAULT '',
            factory_name TEXT DEFAULT '',
            ssi_ts5 TEXT DEFAULT '',
            replace_from TEXT DEFAULT '',
            replace_to TEXT DEFAULT '',
            replace_date TEXT DEFAULT '',
            status TEXT DEFAULT '',
            fn_id TEXT DEFAULT '',
            fn_prev_id TEXT DEFAULT '',
            kkt_model TEXT DEFAULT '',
            fn_model TEXT DEFAULT '',
            rnm_after_activation TEXT DEFAULT '',
            kkt_reg_status TEXT DEFAULT '',
            fp_received_date TEXT DEFAULT '',
            fn_activation_plus410 TEXT DEFAULT '',
            registry TEXT DEFAULT '',
            invoice TEXT DEFAULT '',
            payment TEXT DEFAULT '',
            comment TEXT DEFAULT '',
            card_sent TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(kkt_serial)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ppr_tasks (
            guid TEXT PRIMARY KEY,
            number TEXT,
            name TEXT,
            department TEXT,
            year INTEGER,
            quarter INTEGER,
            status TEXT,
            description TEXT,
            closed_at TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS task_equipment (
            guid TEXT PRIMARY KEY,
            equipment_text TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS action_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            guid TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            uploaded INTEGER NOT NULL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# === TASK EQUIPMENT ===

def save_task_equipment(guid, equipment_text):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO task_equipment (guid, equipment_text)
        VALUES (?, ?)
        ON CONFLICT(guid) DO UPDATE SET
            equipment_text=excluded.equipment_text,
            updated_at=datetime('now','localtime')
    """, (guid, equipment_text))
    conn.commit()
    conn.close()


def get_task_equipment(guid):
    conn = get_db_connection()
    row = conn.execute("SELECT equipment_text FROM task_equipment WHERE guid = ?", (guid,)).fetchone()
    conn.close()
    return row['equipment_text'] if row else None


# === SHOPS ===

def add_shop(shop_number, sap_code, address):
    if not all([shop_number, sap_code, address]):
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO shops (shop_number, sap_code, address) VALUES (?, ?, ?)",
              (shop_number, sap_code, address))
    conn.commit()
    conn.close()


def update_shop_address(sap_code, address):
    if not sap_code or not address:
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE shops SET address = ? WHERE sap_code = ?", (address, sap_code))
    conn.commit()
    conn.close()


def find_shop_by_sap(sap):
    if not sap:
        return None
    conn = get_db_connection()
    row = conn.execute("SELECT shop_number, sap_code, address FROM shops WHERE sap_code = ?", (sap,)).fetchone()
    conn.close()
    return row


def find_shops_by_sap_list(saps):
    if not saps:
        return []
    conn = get_db_connection()
    placeholders = ','.join('?' * len(saps))
    rows = conn.execute(
        f"SELECT shop_number, sap_code, address FROM shops WHERE sap_code IN ({placeholders})", saps
    ).fetchall()
    conn.close()
    return rows


def search_shops(query):
    if not query:
        return []
    conn = get_db_connection()
    like = f"%{query}%"
    rows = conn.execute("""
        SELECT shop_number, sap_code, address FROM shops
        WHERE LOWER_RU(shop_number) LIKE LOWER_RU(?)
           OR LOWER_RU(sap_code) LIKE LOWER_RU(?)
           OR LOWER_RU(address) LIKE LOWER_RU(?)
    """, (like, like, like)).fetchall()
    conn.close()
    return rows


# === TASKS ===

def upsert_tasks(tasks_list):
    if not tasks_list:
        return 0
    conn = get_db_connection()
    c = conn.cursor()
    count = 0
    for t in tasks_list:
        c.execute("""
            INSERT INTO tasks (guid, number, name, description, status, name_department, user,
                               guid_client, hasAttachments, date, period, priority, closed_at, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guid) DO UPDATE SET
                number=excluded.number, name=excluded.name, description=excluded.description,
                status=excluded.status, name_department=excluded.name_department,
                user=excluded.user, guid_client=excluded.guid_client,
                hasAttachments=excluded.hasAttachments, date=excluded.date,
                period=excluded.period, priority=excluded.priority,
                closed_at=excluded.closed_at, category=excluded.category,
                updated_at=datetime('now','localtime')
        """, (
            t.get('guid'), t.get('number'), t.get('name'), t.get('description'),
            t.get('status'), t.get('name_department'), t.get('user'), t.get('guid_client'),
            1 if t.get('hasAttachments') else 0, t.get('date'), t.get('period'),
            t.get('priority'), t.get('closed_at'), t.get('category', '')
        ))
        count += c.rowcount
    conn.commit()
    conn.close()
    return count


def get_tasks(category=None, search=None, limit=500, offset=0):
    conn = get_db_connection()
    where = []
    params = []
    if category:
        where.append("category = ?")
        params.append(category)
    if search:
        where.append("(name LIKE ? OR number LIKE ? OR description LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s])
    w = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT * FROM tasks {w} ORDER BY date DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tasks_count(category=None):
    conn = get_db_connection()
    if category:
        row = conn.execute("SELECT COUNT(*) as cnt FROM tasks WHERE category = ?", (category,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()
    conn.close()
    return row['cnt'] if row else 0


def get_task(guid):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM tasks WHERE guid = ?", (guid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_tasks_by_guids(guids):
    if not guids:
        return []
    conn = get_db_connection()
    placeholders = ','.join('?' * len(guids))
    rows = conn.execute(
        f"SELECT * FROM tasks WHERE guid IN ({placeholders})", guids
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_distinct_task_statuses():
    conn = get_db_connection()
    rows = conn.execute("SELECT DISTINCT status FROM tasks ORDER BY status").fetchall()
    conn.close()
    return [r['status'] for r in rows if r['status']]


# === TASK TRACKING ===

def set_task_taken(guid, username):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO task_tracking (guid, username, taken_at, task_name)
        VALUES (?, ?, datetime('now','localtime'), '')
        ON CONFLICT(guid, username) DO UPDATE SET taken_at=datetime('now','localtime')
    """, (guid, username))
    conn.commit()
    conn.close()


def set_task_closed(guid, username):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO task_tracking (guid, username, closed_at, task_name)
        VALUES (?, ?, datetime('now','localtime'), '')
        ON CONFLICT(guid, username) DO UPDATE SET closed_at=datetime('now','localtime')
    """, (guid, username))
    conn.commit()
    conn.close()


def get_task_tracking(guid, username):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM task_tracking WHERE guid = ? AND username = ?", (guid, username)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# === PRODUCTS ===

def upsert_products(products_list):
    if not products_list:
        return
    conn = get_db_connection()
    c = conn.cursor()
    for p in products_list:
        c.execute("""
            INSERT INTO products (guid, name, article, unit)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guid) DO UPDATE SET
                name=excluded.name, article=excluded.article, unit=excluded.unit,
                updated_at=datetime('now','localtime')
        """, (p.get('guid'), p.get('name'), p.get('article', ''), p.get('unit', '')))
    conn.commit()
    conn.close()


def get_products(search=None):
    conn = get_db_connection()
    if search:
        rows = conn.execute(
            "SELECT * FROM products WHERE name LIKE ? ORDER BY name LIMIT 500",
            (f"%{search}%",)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM products ORDER BY name LIMIT 500").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# === STORAGES ===

def upsert_storages(storages_list):
    if not storages_list:
        return
    conn = get_db_connection()
    c = conn.cursor()
    for s in storages_list:
        c.execute("""
            INSERT INTO storages (guid, name)
            VALUES (?, ?)
            ON CONFLICT(guid) DO UPDATE SET
                name=excluded.name, updated_at=datetime('now','localtime')
        """, (s.get('guid'), s.get('name')))
    conn.commit()
    conn.close()


def get_storages():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM storages ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# === CLIENTS ===

def upsert_clients(clients_list):
    if not clients_list:
        return
    conn = get_db_connection()
    c = conn.cursor()
    for cl in clients_list:
        c.execute("""
            INSERT INTO clients (guid, name, inn)
            VALUES (?, ?, ?)
            ON CONFLICT(guid) DO UPDATE SET
                name=excluded.name, inn=excluded.inn, updated_at=datetime('now','localtime')
        """, (cl.get('guid'), cl.get('name'), cl.get('inn', '')))
    conn.commit()
    conn.close()


def get_clients():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# === WAREHOUSE BALANCES ===

def upsert_balances(balances_list):
    if not balances_list:
        return
    conn = get_db_connection()
    c = conn.cursor()
    for b in balances_list:
        guid = b.get('product_guid') or hashlib.md5(
            (b.get('product_name', '') + '|' + b.get('series_name', '')).encode('utf-8')
        ).hexdigest()
        c.execute("""
            INSERT INTO warehouse_balances (storage_guid, product_guid, product_name, series_name, inventory_number, quantity)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(storage_guid, product_guid, inventory_number) DO UPDATE SET
                product_name=excluded.product_name, series_name=excluded.series_name,
                quantity=excluded.quantity, updated_at=datetime('now','localtime')
        """, (
            b.get('storage_guid'), guid, b.get('product_name'),
            b.get('series_name', ''), b.get('inventory_number', ''), b.get('quantity', 0)
        ))
    conn.commit()
    conn.close()


def get_balances(storage_guid=None):
    conn = get_db_connection()
    q = """
        SELECT w.*, COALESCE(m.broken, 0) as broken
        FROM warehouse_balances w
        LEFT JOIN balance_item_meta m ON w.storage_guid = m.storage_guid
            AND w.product_name = m.product_name
            AND w.series_name = m.series_name
            AND w.inventory_number = m.inventory_number
    """
    if storage_guid:
        rows = conn.execute(q + " WHERE w.storage_guid = ? ORDER BY w.product_name", (storage_guid,)).fetchall()
    else:
        rows = conn.execute(q + " ORDER BY w.product_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_warehouse_balances(storage_guid):
    conn = get_db_connection()
    conn.execute("DELETE FROM warehouse_balances WHERE storage_guid = ?", (storage_guid,))
    conn.commit()
    conn.close()


def get_storage_name(guid):
    conn = get_db_connection()
    row = conn.execute("SELECT name FROM storages WHERE guid = ?", (guid,)).fetchone()
    conn.close()
    return row['name'] if row else guid


# === FN SCHEDULE ===

def upsert_fn_schedule(items):
    conn = get_db_connection()
    c = conn.cursor()
    count = 0
    c.execute("DELETE FROM fn_schedule WHERE kkt_serial LIKE ? AND substr(kkt_serial,2) IN (SELECT kkt_serial FROM fn_schedule WHERE kkt_serial NOT LIKE ?)", ("'%", "'%"))
    c.execute("UPDATE fn_schedule SET kkt_serial = substr(kkt_serial,2) WHERE kkt_serial LIKE ?", ("'%",))
    c.execute("UPDATE fn_schedule SET fn_id = substr(fn_id,2) WHERE fn_id LIKE ?", ("'%",))
    c.execute("UPDATE fn_schedule SET fn_prev_id = substr(fn_prev_id,2) WHERE fn_prev_id LIKE ?", ("'%",))
    c.execute("UPDATE fn_schedule SET rnm_after_activation = substr(rnm_after_activation,2) WHERE rnm_after_activation LIKE ?", ("'%",))
    conn.commit()
    saps = list({item.get('sap_code', '') for item in items if item.get('sap_code')})
    addr_cache = {}
    if saps:
        placeholders = ','.join('?' * len(saps))
        for row in conn.execute(
            f"SELECT sap_code, address FROM shops WHERE sap_code IN ({placeholders})", saps
        ).fetchall():
            addr_cache[row['sap_code']] = row['address']
    for item in items:
        sap = item.get('sap_code', '')
        if sap and sap in addr_cache and not item.get('address'):
            item['address'] = addr_cache[sap]
        c.execute("""
            INSERT INTO fn_schedule (
                shop_number, sap_code, address, cashreg_number, engineer, month, fn_expiry,
                kkt_serial, be_name, cluster_name, gp_name, factory_name, ssi_ts5,
                replace_from, replace_to, replace_date, status, fn_id, fn_prev_id,
                kkt_model, fn_model, rnm_after_activation, kkt_reg_status,
                fp_received_date, fn_activation_plus410, registry, invoice,
                payment, comment, card_sent
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?
            )
            ON CONFLICT(kkt_serial) DO UPDATE SET
                shop_number=excluded.shop_number, sap_code=excluded.sap_code,
                address=excluded.address, cashreg_number=excluded.cashreg_number,
                engineer=excluded.engineer, month=excluded.month,
                fn_expiry=excluded.fn_expiry, be_name=excluded.be_name,
                cluster_name=excluded.cluster_name, gp_name=excluded.gp_name,
                factory_name=excluded.factory_name, ssi_ts5=excluded.ssi_ts5,
                replace_from=excluded.replace_from, replace_to=excluded.replace_to,
                replace_date=excluded.replace_date, status=excluded.status,
                fn_id=excluded.fn_id, fn_prev_id=excluded.fn_prev_id,
                kkt_model=excluded.kkt_model, fn_model=excluded.fn_model,
                rnm_after_activation=excluded.rnm_after_activation,
                kkt_reg_status=excluded.kkt_reg_status,
                fp_received_date=excluded.fp_received_date,
                fn_activation_plus410=excluded.fn_activation_plus410,
                registry=excluded.registry, invoice=excluded.invoice,
                payment=excluded.payment, comment=excluded.comment,
                card_sent=excluded.card_sent, updated_at=datetime('now','localtime')
        """, (
            item.get('shop_number'), item.get('sap_code'), item.get('address', ''),
            item.get('cashreg_number'), item.get('engineer'), item.get('month'),
            item.get('fn_expiry'), item.get('kkt_serial'), item.get('be_name', ''),
            item.get('cluster_name', ''), item.get('gp_name', ''),
            item.get('factory_name', ''), item.get('ssi_ts5', ''),
            item.get('replace_from', ''), item.get('replace_to', ''),
            item.get('replace_date', ''), item.get('status', ''),
            item.get('fn_id', ''), item.get('fn_prev_id', ''),
            item.get('kkt_model', ''), item.get('fn_model', ''),
            item.get('rnm_after_activation', ''), item.get('kkt_reg_status', ''),
            item.get('fp_received_date', ''), item.get('fn_activation_plus410', ''),
            item.get('registry', ''), item.get('invoice', ''),
            item.get('payment', ''), item.get('comment', ''),
            item.get('card_sent', '')
        ))
        count += 1
    conn.commit()
    conn.close()
    return count


def get_fn_schedule_list(engineer=None, month=None, limit=500, offset=0):
    conn = get_db_connection()
    where = []
    params = []
    if engineer:
        where.append("engineer = ?")
        params.append(engineer)
    if month:
        where.append("month = ?")
        params.append(month)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT * FROM fn_schedule {w} ORDER BY fn_expiry ASC NULLS LAST LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fn_schedule_by_shop(shop_number):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM fn_schedule WHERE shop_number = ? AND status NOT IN ('Выполнена','Снят с учета') ORDER BY id",
        (shop_number,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fn_engineers():
    conn = get_db_connection()
    rows = conn.execute("SELECT DISTINCT engineer FROM fn_schedule WHERE engineer != '' ORDER BY engineer").fetchall()
    conn.close()
    return [r['engineer'] for r in rows]


def get_fn_months():
    conn = get_db_connection()
    rows = conn.execute("SELECT DISTINCT month FROM fn_schedule WHERE month != '' ORDER BY month").fetchall()
    conn.close()
    return [r['month'] for r in rows]


# === PPR ===

def upsert_ppr_tasks(ppr_list):
    if not ppr_list:
        return
    conn = get_db_connection()
    c = conn.cursor()
    for p in ppr_list:
        c.execute("""
            INSERT INTO ppr_tasks (guid, number, name, department, year, quarter, status, description, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guid) DO UPDATE SET
                number=excluded.number, name=excluded.name, department=excluded.department,
                year=excluded.year, quarter=excluded.quarter, status=excluded.status,
                description=excluded.description, closed_at=excluded.closed_at,
                updated_at=datetime('now','localtime')
        """, (
            p.get('guid'), p.get('number'), p.get('name'), p.get('department'),
            p.get('year'), p.get('quarter'), p.get('status'),
            p.get('description'), p.get('closed_at')
        ))
    conn.commit()
    conn.close()


def get_ppr_list(department=None, year=None, quarter=None):
    conn = get_db_connection()
    where = []
    params = []
    if department:
        where.append("department = ?")
        params.append(department)
    if year:
        where.append("year = ?")
        params.append(year)
    if quarter:
        where.append("quarter = ?")
        params.append(quarter)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(f"SELECT * FROM ppr_tasks {w} ORDER BY name", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ppr_departments():
    conn = get_db_connection()
    rows = conn.execute("SELECT DISTINCT department FROM ppr_tasks WHERE department != '' ORDER BY department").fetchall()
    conn.close()
    return [r['department'] for r in rows]


# === SYNC STATE ===

def get_sync_state(key):
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else None


def set_sync_state(key, value):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO sync_state (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now','localtime')
    """, (key, value))
    conn.commit()
    conn.close()


# === ACTION QUEUE ===

def add_action(action_type, guid):
    conn = get_db_connection()
    conn.execute("INSERT INTO action_queue (type, guid) VALUES (?, ?)", (action_type, guid))
    conn.commit()
    conn.close()


def get_pending_actions():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM action_queue WHERE uploaded = 0 ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_action_uploaded(action_id):
    conn = get_db_connection()
    conn.execute("UPDATE action_queue SET uploaded = 1 WHERE id = ?", (action_id,))
    conn.commit()
    conn.close()


def cleanup_actions(days=7):
    conn = get_db_connection()
    conn.execute("DELETE FROM action_queue WHERE uploaded = 1 AND created_at < datetime('now', ?)", (f'-{days} days',))
    conn.commit()
    conn.close()


# === FIAS CACHE ===

def get_fias_cache(raw):
    conn = get_db_connection()
    row = conn.execute("SELECT normalized FROM fias_cache WHERE raw = ?", (raw,)).fetchone()
    conn.close()
    return row['normalized'] if row else None


def set_fias_cache(raw, normalized):
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO fias_cache (raw, normalized) VALUES (?, ?)", (raw, normalized))
    conn.commit()
    conn.close()