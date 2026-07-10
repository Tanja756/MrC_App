import os
import json
import logging
import threading
from flask import Flask, jsonify, request
from config import ensure_config, load_config
from yadisk_client import YandexDiskClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)


def create_app():
    ensure_config()

    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'actions')
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

    from db import init_db
    init_db()

    from routes.tasks import tasks_bp
    from routes.warehouse import warehouse_bp
    from routes.ppr import ppr_bp
    from routes.fn import fn_bp
    from routes.route import route_bp
    from routes.settings import settings_bp
    from routes.pages import pages_bp
    from routes.misc import misc_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(misc_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(warehouse_bp)
    app.register_blueprint(ppr_bp)
    app.register_blueprint(fn_bp)
    app.register_blueprint(route_bp)
    app.register_blueprint(settings_bp)

    @app.route('/api/sync/from-yandex', methods=['POST'])
    def api_sync_from_yandex():
        print(f"[API] sync_from_yandex: starting...")
        from data_sync import sync_from_yandex
        client = YandexDiskClient()
        result = sync_from_yandex(client)
        print(f"[API] sync_from_yandex: done, result={result}")
        return jsonify(result)

    @app.route('/api/sync/to-yandex', methods=['POST'])
    def api_sync_to_yandex():
        print(f"[API] sync_to_yandex: starting...")
        from action_manager import upload_all_actions
        client = YandexDiskClient()
        count = upload_all_actions(client)
        print(f"[API] sync_to_yandex: done, uploaded={count}")
        return jsonify({'uploaded': count})

    @app.route('/api/sync/status')
    def api_sync_status():
        from db import get_pending_actions, get_tasks_count
        pending = len(get_pending_actions())
        tasks_total = get_tasks_count()
        tasks_open = get_tasks_count('my') + get_tasks_count('free')
        tasks_closed = get_tasks_count('closed')
        return jsonify({
            'pending_actions': pending,
            'tasks_total': tasks_total,
            'tasks_open': tasks_open,
            'tasks_closed': tasks_closed,
        })

    app.jinja_env.globals.update(now=__import__('datetime').datetime.now)

    _start_auto_upload(app)

    return app


def _start_auto_upload(app):
    cfg = load_config()
    interval = int(cfg.get('App', 'sync_interval_minutes', fallback='10'))

    def _run():
        import time
        from action_manager import upload_all_actions
        from data_sync import sync_from_yandex
        while True:
            time.sleep(interval * 60)
            with app.app_context():
                try:
                    client = YandexDiskClient()
                    upload_all_actions(client)
                except Exception as e:
                    logger.error(f"Auto-upload error: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info(f"Auto-upload started (interval={interval} min)")


if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=True)