from flask import Blueprint, jsonify, request
from db import get_fn_schedule_list, get_fn_schedule_by_shop, get_fn_engineers, get_fn_months, find_shops_by_sap_list

fn_bp = Blueprint('fn', __name__, url_prefix='/api/fn')


@fn_bp.route('/list')
def api_fn_list():
    engineer = request.args.get('engineer', '')
    month = request.args.get('month', '')
    rows = get_fn_schedule_list(engineer=engineer or None, month=month or None)
    return jsonify({'rows': rows})


@fn_bp.route('/engineers')
def api_fn_engineers():
    return jsonify({'engineers': get_fn_engineers()})


@fn_bp.route('/months')
def api_fn_months():
    return jsonify({'months': get_fn_months()})


@fn_bp.route('/shop/<shop_number>')
def api_fn_shop(shop_number):
    rows = get_fn_schedule_by_shop(shop_number)
    return jsonify({'rows': rows})


@fn_bp.route('/by-sap-list', methods=['POST'])
def api_fn_by_sap_list():
    data = request.json or {}
    saps = data.get('saps', [])
    if not saps:
        return jsonify({})
    rows = find_shops_by_sap_list(saps)
    result = {r['sap_code']: {'shop': r['shop_number'], 'sap': r['sap_code'], 'addr': r['address']} for r in rows}
    return jsonify(result)