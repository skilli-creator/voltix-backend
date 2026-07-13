# backend/routes/deriv_routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.deriv_service import (
    connect_deriv_account,
    disconnect_deriv_account,
    get_deriv_balance,
    validate_deriv_token,
    get_connection_status
)

deriv_bp = Blueprint("deriv", __name__)

@deriv_bp.route("/connect", methods=["POST"])
@jwt_required()
def connect():
    try:
        user_id = get_jwt_identity()
        token = request.json.get("api_token", "").strip()

        if not token:
            return jsonify({"success": False, "error": "Token required"}), 400

        return jsonify(connect_deriv_account(user_id, token))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@deriv_bp.route("/disconnect", methods=["POST"])
@jwt_required()
def disconnect():
    user_id = get_jwt_identity()
    return jsonify(disconnect_deriv_account(user_id))


@deriv_bp.route("/balance")
@jwt_required()
def balance():
    user_id = get_jwt_identity()
    return jsonify(get_deriv_balance(user_id))


@deriv_bp.route("/status")
@jwt_required()
def status():
    user_id = get_jwt_identity()
    return jsonify(get_connection_status(user_id))


@deriv_bp.route("/test-token", methods=["POST"])
def test():
    token = request.json.get("api_token", "").strip()
    return jsonify(validate_deriv_token(token))