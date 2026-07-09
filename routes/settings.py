import os
from flask import Blueprint, jsonify, request
from config import load_config, save_config

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@settings_bp.route('', methods=['GET'])
def api_get_settings():
    cfg = load_config()
    result = {}
    for section in cfg.sections():
        for key, value in cfg[section].items():
            result[f"{section}_{key}"] = value
    return jsonify(result)


@settings_bp.route('', methods=['POST'])
def api_save_settings():
    data = request.json or {}
    cfg = load_config()
    for section in cfg.sections():
        for key in cfg[section]:
            full_key = f"{section}_{key}"
            if full_key in data:
                cfg[section][key] = str(data[full_key])
    save_config(cfg)
    return jsonify({'ok': True})