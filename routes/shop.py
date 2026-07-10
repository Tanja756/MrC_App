from flask import Blueprint, jsonify, request
from db import find_shop_by_sap, find_shops_by_sap_list

shop_bp = Blueprint('shop', __name__, url_prefix='/api/shop')


@shop_bp.route('/by-sap')
def api_shop_by_sap():
    sap = request.args.get('sap', '')
    if not sap:
        return jsonify({'addr': None})
    row = find_shop_by_sap(sap)
    if row:
        return jsonify({'shop': row['shop_number'], 'sap': row['sap_code'], 'addr': row['address']})
    return jsonify({'addr': None})


@shop_bp.route('/by-sap-list', methods=['POST'])
def api_shop_by_sap_list():
    data = request.json or {}
    saps = data.get('saps', [])
    if not saps:
        return jsonify({})
    rows = find_shops_by_sap_list(saps)
    result = {r['sap_code']: {'shop': r['shop_number'], 'sap': r['sap_code'], 'addr': r['address']} for r in rows}
    return jsonify(result)
