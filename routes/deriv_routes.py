# backend/routes/deriv_routes.py

import time
from flask import Blueprint, jsonify, request
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
def get_all_market_data():
    """Get data for all markets"""
    return jsonify({
        'success': True,
        'data': deriv_service.get_all_market_data()
    })

@deriv_bp.route('/market-data/<symbol>', methods=['GET'])
def get_market_data(symbol):
    """Get data for a specific market"""
    data = deriv_service.get_market_data(symbol)
    if not data:
        return jsonify({
            'success': False,
            'error': f'Market {symbol} not found'
        }), 404
    return jsonify({
        'success': True,
        'data': data
    })

@deriv_bp.route('/market-data/<symbol>/history', methods=['GET'])
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

@deriv_bp.route('/update', methods=['POST'])
def force_update():
    """Force update all markets (for testing)"""
    data = deriv_service.update_all_markets()
    websocket_service.broadcast_to_all('price_update', {'data': data})
    return jsonify({
        'success': True,
        'data': data,
        'message': 'All markets updated'
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
        
        # Send initial data
        initial_data = deriv_service.get_all_market_data()
        socketio.emit('initial_data', {'data': initial_data}, room=client_id)
    
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
            socketio.emit('subscribed', {
                'symbol': symbol,
                'message': f'Subscribed to {symbol}'
            }, room=client_id)
    
    @socketio.on('unsubscribe')
    def handle_unsubscribe(data):
        client_id = request.sid
        symbol = data.get('symbol')
        if symbol:
            websocket_service.unsubscribe(client_id, symbol)
            print(f'📡 Client {client_id} unsubscribed from {symbol}')
            socketio.emit('unsubscribed', {
                'symbol': symbol,
                'message': f'Unsubscribed from {symbol}'
            }, room=client_id)
    
    @socketio.on('ping')
    def handle_ping():
        client_id = request.sid
        socketio.emit('pong', {
            'timestamp': int(time.time() * 1000)
        }, room=client_id)
    
    @socketio.on('get_market_data')
    def handle_get_market_data(data):
        client_id = request.sid
        symbol = data.get('symbol')
        if symbol:
            market_data = deriv_service.get_market_data(symbol)
            socketio.emit('market_update', {
                'symbol': symbol,
                'data': market_data
            }, room=client_id)