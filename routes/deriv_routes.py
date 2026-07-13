from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.deriv_service import (
    connect_deriv_account,
    disconnect_deriv_account,
    get_deriv_balance,
    get_connection_status,
    validate_deriv_token
)

deriv_bp = Blueprint("deriv", __name__)


@deriv_bp.route("/connect", methods=["POST"])
@jwt_required()
def connect():
    user_id = get_jwt_identity()
    token = request.json.get("api_token")

    if not token:
        return jsonify({"success": False, "error": "Token required"}), 400

    result = connect_deriv_account(user_id, token)

    if not result["success"]:
        return jsonify(result), 400

    return jsonify(result)


@deriv_bp.route("/disconnect", methods=["POST"])
@jwt_required()
def disconnect():
    user_id = get_jwt_identity()
    return jsonify(disconnect_deriv_account(user_id))


@deriv_bp.route("/balance", methods=["GET"])
@jwt_required()
def balance():
    user_id = get_jwt_identity()
    return jsonify(get_deriv_balance(user_id))


@deriv_bp.route("/status", methods=["GET"])
@jwt_required()
def status():
    user_id = get_jwt_identity()
    return jsonify({
        "success": True,
        "data": get_connection_status(user_id)
    })


@deriv_bp.route("/test-token", methods=["POST"])
def test_token():
    token = request.json.get("api_token")
    return jsonify(validate_deriv_token(token))