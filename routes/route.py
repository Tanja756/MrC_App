from flask import Blueprint, jsonify, request
from db import get_tasks

route_bp = Blueprint('route', __name__, url_prefix='/api/route')


@route_bp.route('/sheet', methods=['POST'])
def api_route_sheet():
    data = request.json or {}
    month = data.get('month', '')
    if not month:
        return jsonify({'rows': []})
    tasks = get_tasks()
    from datetime import datetime
    try:
        start = datetime.strptime(month, '%Y-%m')
    except ValueError:
        return jsonify({'rows': []})

    filtered = [
        t for t in tasks
        if t.get('closed_at') and t['closed_at'].startswith(month)
    ]
    filtered.sort(key=lambda t: t.get('closed_at', ''))
    return jsonify({'rows': filtered})