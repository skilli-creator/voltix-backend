# backend/routes/deriv_routes.py

import time
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.deriv_service import deriv_service
from services.websocket_service import websocket_service, socketio

deriv_bp = Blueprint('deriv', __name__)

# ============================================
# REST API ENDPOINTS
# ============================================

@deriv_bp.route('/markets', methods=['GET'])
def get_markets():
    """Get list of all volatility markets"""
    return jsonify({
        'success': True,
        'data': deriv_service.get_markets_list()
    })

@deriv_bp.route('/market-data', methods=['GET'])
@jwt_required()
def get_all_market_data():
    """Get data for all markets (requires authentication)"""
    user_id = get_jwt_identity()
    data = deriv_service.get_all_market_data()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No market data available. Please connect your Deriv account.'
        }), 404
    
    return jsonify({
        'success': True,
        'data': data
    })

@deriv_bp.route('/market-data/<symbol>', methods=['GET'])
@jwt_required()
def get_market_data(symbol):
    """Get data for a specific market (requires authentication)"""
    user_id = get_jwt_identity()
    data = deriv_service.get_market_data(symbol)
    
    if not data:
        return jsonify({
            'success': False,
            'error': f'Market {symbol} not found or not connected'
        }), 404
    
    return jsonify({
        'success': True,
        'data': data
    })

@deriv_bp.route('/market-data/<symbol>/history', methods=['GET'])
@jwt_required()
def get_market_history(symbol):
    """Get historical ticks for a market"""
    limit = request.args.get('limit', 150, type=int)
    ticks = deriv_service.get_market_history(symbol, limit)
    
    if ticks is None:
        return jsonify({
            'success': False,
            'error': f'Market {symbol} not found'
        }), 404
    
    return jsonify({
        'success': True,
        'data': ticks
    })

# ============================================
# SOCKET.IO EVENT HANDLERS
# ============================================

def register_socket_handlers():
    """Register SocketIO event handlers"""
    global socketio
    
    if not socketio:
        print("⚠️ SocketIO not initialized")
        return
    
    @socketio.on('connect')
    def handle_connect():
        client_id = request.sid
        websocket_service.register_client(client_id)
        print(f'✅ Client connected: {client_id}')
        
        # Send available markets list
        socketio.emit('markets_list', {
            'data': deriv_service.get_markets_list()
        }, room=client_id)
        
        # Send any existing market data
        all_data = deriv_service.get_all_market_data()
        if all_data:
            socketio.emit('initial_data', {
                'data': all_data
            }, room=client_id)
    
    @socketio.on('disconnect')
    def handle_disconnect():
        client_id = request.sid
        websocket_service.unregister_client(client_id)
        print(f'❌ Client disconnected: {client_id}')
    
    @socketio.on('subscribe')
    def handle_subscribe(data):
        client_id = request.sid
        symbol = data.get('symbol')
        if symbol:
            websocket_service.subscribe(client_id, symbol)
            print(f'📡 Client {client_id} subscribed to {symbol}')
            
            # Send current data immediately if available
            market_data = deriv_service.get_market_data(symbol)
            if market_data:
                socketio.emit('market_update', {
                    'symbol': symbol,
                    'data': market_data
                }, room=client_id)
    
    @socketio.on('unsubscribe')
    def handle_unsubscribe(data):
        client_id = request.sid
        symbol = data.get('symbol')
        if symbol:
            websocket_service.unsubscribe(client_id, symbol)
            print(f'📡 Client {client_id} unsubscribed from {symbol}')
    
    @socketio.on('ping')
    def handle_ping():
        client_id = request.sid
        socketio.emit('pong', {
            'timestamp': int(time.time() * 1000)
        }, room=client_id)
    
    @socketio.on('get_market_data')
    def handle_get_market_data(data):
        """Client requests market data"""
        client_id = request.sid
        symbol = data.get('symbol')
        if symbol:
            market_data = deriv_service.get_market_data(symbol)
            if market_data:
                socketio.emit('market_update', {
                    'symbol': symbol,
                    'data': market_data
                }, room=client_id)
            else:
                socketio.emit('market_error', {
                    'symbol': symbol,
                    'message': f'No data available for {symbol}'
                }, room=client_id)