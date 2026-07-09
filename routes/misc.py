from flask import Blueprint, jsonify

misc_bp = Blueprint('misc', __name__)


@misc_bp.route('/api/priorities')
def api_priorities():
    return jsonify([])


@misc_bp.route('/api/salary')
def api_salary():
    return jsonify({"data": [], "totalAmount": 0.0})