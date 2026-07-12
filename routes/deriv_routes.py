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
    try:
        markets = deriv_service.get_markets_list()
        return jsonify({
            'success': True,
            'data': markets
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_bp.route('/market-data', methods=['GET'])
@jwt_required()
def get_all_market_data():
    """Get data for all markets (requires authentication)"""
    try:
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
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_bp.route('/market-data/<symbol>', methods=['GET'])
@jwt_required()
def get_market_data(symbol):
    """Get data for a specific market (requires authentication)"""
    try:
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
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_bp.route('/market-data/<symbol>/history', methods=['GET'])
@jwt_required()
def get_market_history(symbol):
    """Get historical ticks for a market"""
    try:
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
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# DERIV CONNECTION ENDPOINTS (TOKEN BASED)
# ============================================

@deriv_bp.route('/test-connection', methods=['POST'])
@jwt_required()
def test_connection():
    """Test Deriv API token connection"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        api_token = data.get('api_token')
        
        if not api_token:
            return jsonify({
                'success': False,
                'error': 'API token required'
            }), 400
        
        success, result = deriv_service.test_connection(api_token)
        
        if success:
            return jsonify({
                'success': True,
                'data': result,
                'message': 'Connection successful'
            })
        else:
            return jsonify({
                'success': False,
                'error': result
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_bp.route('/connect', methods=['POST'])
@jwt_required()
def connect_with_token():
    """Connect to Deriv using API token"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        api_token = data.get('api_token')
        
        if not api_token:
            return jsonify({
                'success': False,
                'error': 'API token required'
            }), 400
        
        # Test the connection
        success, result = deriv_service.test_connection(api_token)
        if not success:
            return jsonify({
                'success': False,
                'error': result
            }), 400
        
        # Get account info
        account_success, account_info = deriv_service.get_account_info(api_token)
        
        return jsonify({
            'success': True,
            'message': 'Connected successfully',
            'account': account_info if account_success else None,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_bp.route('/balance', methods=['POST'])
@jwt_required()
def get_balance():
    """Get account balance"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        api_token = data.get('api_token')
        
        if not api_token:
            return jsonify({
                'success': False,
                'error': 'API token required'
            }), 400
        
        success, balance, currency, loginid = deriv_service.get_balance(api_token)
        
        if success:
            return jsonify({
                'success': True,
                'balance': balance,
                'currency': currency,
                'loginid': loginid
            })
        else:
            return jsonify({
                'success': False,
                'error': balance
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_bp.route('/account-info', methods=['POST'])
@jwt_required()
def get_account_info():
    """Get account information"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        api_token = data.get('api_token')
        
        if not api_token:
            return jsonify({
                'success': False,
                'error': 'API token required'
            }), 400
        
        success, info = deriv_service.get_account_info(api_token)
        
        if success:
            return jsonify({
                'success': True,
                'account': info
            })
        else:
            return jsonify({
                'success': False,
                'error': info
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# TRADING ENDPOINTS
# ============================================

@deriv_bp.route('/place-trade', methods=['POST'])
@jwt_required()
def place_trade():
    """Place a trade on Deriv"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        api_token = data.get('api_token')
        symbol = data.get('symbol')
        trade_type = data.get('trade_type')
        amount = data.get('amount')
        duration = data.get('duration')
        duration_unit = data.get('duration_unit', 't')
        
        if not api_token:
            return jsonify({'success': False, 'error': 'API token required'}), 400
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        if not trade_type:
            return jsonify({'success': False, 'error': 'Trade type required'}), 400
        if not amount or amount <= 0:
            return jsonify({'success': False, 'error': 'Valid amount required'}), 400
        if not duration or duration <= 0:
            return jsonify({'success': False, 'error': 'Valid duration required'}), 400
        
        success, trade = deriv_service.place_trade(
            api_token=api_token,
            symbol=symbol,
            trade_type=trade_type,
            amount=amount,
            duration=duration,
            duration_unit=duration_unit
        )
        
        if success:
            # Broadcast trade update to all connected clients
            websocket_service.broadcast_to_all('trade_placed', {
                'user_id': user_id,
                'trade': trade,
                'symbol': symbol,
                'timestamp': int(time.time() * 1000)
            })
            
            return jsonify({
                'success': True,
                'trade': trade
            })
        else:
            return jsonify({
                'success': False,
                'error': trade
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_bp.route('/active-contracts', methods=['POST'])
@jwt_required()
def get_active_contracts():
    """Get active contracts"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        api_token = data.get('api_token')
        
        if not api_token:
            return jsonify({'success': False, 'error': 'API token required'}), 400
        
        success, contracts = deriv_service.get_active_contracts(api_token)
        
        if success:
            return jsonify({
                'success': True,
                'contracts': contracts
            })
        else:
            return jsonify({
                'success': False,
                'error': contracts
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_bp.route('/trade-history', methods=['POST'])
@jwt_required()
def get_trade_history():
    """Get trade history"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        api_token = data.get('api_token')
        limit = data.get('limit', 50)
        
        if not api_token:
            return jsonify({'success': False, 'error': 'API token required'}), 400
        
        success, history = deriv_service.get_trade_history(api_token, limit)
        
        if success:
            return jsonify({
                'success': True,
                'history': history
            })
        else:
            return jsonify({
                'success': False,
                'error': history
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_bp.route('/contract-info', methods=['POST'])
@jwt_required()
def get_contract_info():
    """Get information about a specific contract"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        api_token = data.get('api_token')
        contract_id = data.get('contract_id')
        
        if not api_token:
            return jsonify({'success': False, 'error': 'API token required'}), 400
        if not contract_id:
            return jsonify({'success': False, 'error': 'Contract ID required'}), 400
        
        success, info = deriv_service.get_contract_info(api_token, contract_id)
        
        if success:
            return jsonify({
                'success': True,
                'contract': info
            })
        else:
            return jsonify({
                'success': False,
                'error': info
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
    
    @socketio.on('connect_deriv')
    def handle_connect_deriv(data):
        """Connect to Deriv using API token via WebSocket"""
        client_id = request.sid
        api_token = data.get('api_token')
        
        if not api_token:
            socketio.emit('deriv_connection_error', {
                'error': 'API token required'
            }, room=client_id)
            return
        
        success, result = deriv_service.test_connection(api_token)
        
        if success:
            # Get account info
            account_success, account_info = deriv_service.get_account_info(api_token)
            socketio.emit('deriv_connected', {
                'success': True,
                'account': account_info if account_success else None,
                'message': 'Connected successfully'
            }, room=client_id)
        else:
            socketio.emit('deriv_connection_error', {
                'error': result
            }, room=client_id)