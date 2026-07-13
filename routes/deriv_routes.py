# backend/routes/deriv_routes.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.deriv_service import (
    connect_deriv_account,
    disconnect_deriv_account,
    get_deriv_account_status,
    get_deriv_balance,
    validate_deriv_token,
    get_account_info,
    get_connection_status
)

deriv_bp = Blueprint('deriv', __name__)

# ============================================
# DERIV CONNECTION ENDPOINTS
# ============================================

@deriv_bp.route('/connect', methods=['POST'])
@jwt_required()
def connect():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        api_token = data.get('api_token')
        
        if not api_token:
            return jsonify({
                'success': False,
                'error': 'API token required'
            }), 400
        
        result = connect_deriv_account(user_id, api_token)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@deriv_bp.route('/disconnect', methods=['POST'])
@jwt_required()
def disconnect():
    try:
        user_id = get_jwt_identity()
        result = disconnect_deriv_account(user_id)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@deriv_bp.route('/status', methods=['GET'])
@jwt_required()
def status():
    try:
        user_id = get_jwt_identity()
        result = get_deriv_account_status(user_id)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@deriv_bp.route('/balance', methods=['GET'])
@jwt_required()
def balance():
    try:
        user_id = get_jwt_identity()
        result = get_deriv_balance(user_id)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@deriv_bp.route('/account', methods=['GET'])
@jwt_required()
def account():
    try:
        user_id = get_jwt_identity()
        result = get_account_info(user_id)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@deriv_bp.route('/test-token', methods=['POST'])
def test_token():
    try:
        data = request.get_json()
        api_token = data.get('api_token')
        
        if not api_token:
            return jsonify({
                'success': False,
                'error': 'API token required'
            }), 400
        
        result = validate_deriv_token(api_token)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@deriv_bp.route('/connection-status', methods=['GET'])
@jwt_required()
def connection_status():
    try:
        user_id = get_jwt_identity()
        result = get_connection_status(user_id)
        return jsonify({
            'success': True,
            'data': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500