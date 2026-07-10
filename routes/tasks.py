from flask import Blueprint, jsonify, request
from db import get_tasks, get_task, get_tasks_count, get_distinct_task_statuses

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')


@tasks_bp.route('/my')
def api_tasks_my():
    return _tasks_by_category('my')


@tasks_bp.route('/free')
def api_tasks_free():
    return _tasks_by_category('free')


@tasks_bp.route('/closed')
def api_tasks_closed():
    return _tasks_by_category('closed')


def _tasks_by_category(category):
    search = request.args.get('search', '')
    rows = get_tasks(category=category, search=search or None, limit=500)
    return jsonify({'tasks': rows})


@tasks_bp.route('/list')
def api_tasks_list():
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    search = request.args.get('search', '')
    limit = request.args.get('limit', 200, type=int)
    offset = request.args.get('offset', 0, type=int)
    cat = category if category in ('my', 'free', 'closed') else status if status and status != 'all' else None
    rows = get_tasks(category=cat, search=search or None, limit=limit, offset=offset)
    total = get_tasks_count(category=cat)
    return jsonify({'rows': rows, 'total': total})


@tasks_bp.route('/statuses')
def api_task_statuses():
    return jsonify({'statuses': get_distinct_task_statuses()})


@tasks_bp.route('/count')
def api_task_count():
    return jsonify({
        'my': get_tasks_count('my'),
        'free': get_tasks_count('free'),
        'closed': get_tasks_count('closed'),
        'total': get_tasks_count(),
    })


@tasks_bp.route('/take', methods=['POST'])
def api_task_take():
    data = request.json or {}
    guid = data.get('guid')
    username = data.get('username', 'local')
    if not guid:
        return jsonify({'error': 'guid required'}), 400
    from db import set_task_taken, add_action
    from action_manager import create_action_file
    task = get_task(guid)
    set_task_taken(guid, username)
    add_action('take_task', guid)
    create_action_file('take_task', guid, task)
    return jsonify({'ok': True})


@tasks_bp.route('/take-bulk', methods=['POST'])
def api_task_take_bulk():
    data = request.json or {}
    guids = data.get('guids', [])
    username = data.get('username', 'local')
    if not guids:
        return jsonify({'error': 'guids required'}), 400
    from db import set_task_taken, add_action
    from action_manager import create_action_file
    tasks = {t['guid']: t for t in get_tasks_by_guids(guids)}
    for guid in guids:
        set_task_taken(guid, username)
        add_action('take_task', guid)
        create_action_file('take_task', guid, tasks.get(guid))
    return jsonify({'ok': True})


@tasks_bp.route('/close', methods=['POST'])
def api_task_close():
    data = request.json or {}
    guid = data.get('guid')
    username = data.get('username', 'local')
    if not guid:
        return jsonify({'error': 'guid required'}), 400
    from db import set_task_closed, add_action
    from action_manager import create_action_file
    task = get_task(guid)
    set_task_closed(guid, username)
    add_action('close_task', guid)
    create_action_file('close_task', guid, task)
    return jsonify({'ok': True})


@tasks_bp.route('/reject', methods=['POST'])
def api_task_reject():
    data = request.json or {}
    guid = data.get('guid')
    username = data.get('username', 'local')
    if not guid:
        return jsonify({'error': 'guid required'}), 400
    from action_manager import create_action_file
    task = get_task(guid)
    create_action_file('reject_task', guid, task)
    return jsonify({'ok': True})


@tasks_bp.route('/redirect', methods=['POST'])
def api_task_redirect():
    data = request.json or {}
    guid = data.get('guid')
    username = data.get('username', 'local')
    if not guid:
        return jsonify({'error': 'guid required'}), 400
    from action_manager import create_action_file
    task = get_task(guid)
    create_action_file('redirect_task', guid, task)
    return jsonify({'ok': True})


@tasks_bp.route('/<guid>')
def api_task_detail(guid):
    task = get_task(guid)
    if not task:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(task)


@tasks_bp.route('/<guid>/attachments')
def api_task_attachments(guid):
    return jsonify([])


@tasks_bp.route('/<guid>/update-closed-at', methods=['POST'])
def api_task_update_closed_at(guid):
    data = request.json or {}
    closed_at = data.get('closed_at', '')
    from db import get_db_connection
    conn = get_db_connection()
    conn.execute("UPDATE task_tracking SET closed_at = ? WHERE guid = ?", (closed_at, guid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@tasks_bp.route('/<guid>/m15-items')
def api_task_m15_items(guid):
    return jsonify({'items': [], 'text': ''})


@tasks_bp.route('/<guid>/m15-text', methods=['GET', 'POST'])
def api_task_m15_text(guid):
    if request.method == 'POST':
        data = request.json or {}
        equipment_text = data.get('text', '')
        if equipment_text:
            from db import save_task_equipment
            save_task_equipment(guid, equipment_text)
            return jsonify({'ok': True})
        return jsonify({'error': 'text required'}), 400
    from db import get_task_equipment
    text = get_task_equipment(guid)
    hk = request.args.get('hk', '')
    return jsonify({'text': text or '', 'request_code': '', 'hk_code': hk})


@tasks_bp.route('/documents')
def api_tasks_documents():
    from db import get_clients
    return jsonify(get_clients())


@tasks_bp.route('/documents', methods=['POST'])
def api_generate_documents():
    from docgen import generate_documents
    data = request.json or {}
    result = generate_documents(data)
    return jsonify(result)


@tasks_bp.route('/documents/act', methods=['POST'])
def api_generate_act():
    from docgen import generate_act
    data = request.json or {}
    result = generate_act(data)
    return _send_file(result)


@tasks_bp.route('/documents/fn', methods=['POST'])
def api_generate_fn():
    from docgen import generate_fn
    data = request.json or {}
    result = generate_fn(data)
    return _send_file(result)


@tasks_bp.route('/documents/m15-in', methods=['POST'])
def api_generate_m15_in():
    from docgen import generate_m15_in
    data = request.json or {}
    result = generate_m15_in(data)
    return _send_file(result)


@tasks_bp.route('/documents/m15-out', methods=['POST'])
def api_generate_m15_out():
    from docgen import generate_m15_out
    data = request.json or {}
    result = generate_m15_out(data)
    return _send_file(result)


def _send_file(result):
    from flask import send_file, after_this_request
    import os
    path = result.get('path')
    if path and os.path.exists(path):
        @after_this_request
        def cleanup(response):
            try:
                os.unlink(path)
            except Exception:
                pass
            return response
        return send_file(path, as_attachment=True, download_name=result.get('filename', 'doc.ods'))
    return jsonify({'error': 'Failed to generate document'}), 500
