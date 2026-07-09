from flask import Blueprint, jsonify, request
from db import get_ppr_list, get_ppr_departments

ppr_bp = Blueprint('ppr', __name__, url_prefix='/api/ppr')


@ppr_bp.route('/list')
def api_ppr_list():
    department = request.args.get('department', '')
    year = request.args.get('year', type=int)
    quarter = request.args.get('quarter', type=int)
    rows = get_ppr_list(
        department=department or None,
        year=year,
        quarter=quarter
    )
    return jsonify({'rows': rows})


@ppr_bp.route('/departments')
def api_ppr_departments():
    return jsonify({'departments': get_ppr_departments()})