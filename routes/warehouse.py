from flask import Blueprint, jsonify, request
from db import get_storages, get_balances, get_storage_name

warehouse_bp = Blueprint('warehouse', __name__, url_prefix='/api/warehouse')


@warehouse_bp.route('/storages')
def api_warehouse_storages():
    rows = get_storages()
    return jsonify({'storages': rows})


@warehouse_bp.route('/balances')
def api_warehouse_balances():
    storage_guid = request.args.get('storage_guid', '')
    rows = get_balances(storage_guid=storage_guid or None)
    return jsonify({'balances': rows})


@warehouse_bp.route('/storage-name')
def api_storage_name():
    guid = request.args.get('guid', '')
    if not guid:
        return jsonify({'name': ''})
    return jsonify({'name': get_storage_name(guid)})