# backend/services/deriv_service.py
import json
import websocket
import threading
import time
import base64
import logging
from datetime import datetime
from cryptography.fernet import Fernet
from models.database import db


# ============================================
# LOGGING
# ============================================
logger = logging.getLogger(__name__)


# ============================================
# ENCRYPTION HELPERS
# ============================================
def get_encryption_key():
    """Get encryption key from config"""
    from flask import current_app
    key = current_app.config.get('ENCRYPTION_KEY')
    if not key:
        raise ValueError("❌ ENCRYPTION_KEY not configured")
    return key.encode() if isinstance(key, str) else key


def encrypt_token(token):
    """Encrypt API token for storage"""
    if not token:
        return None
    fernet = Fernet(get_encryption_key())
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token):
    """Decrypt API token for use"""
    if not encrypted_token:
        return None
    fernet = Fernet(get_encryption_key())
    return fernet.decrypt(encrypted_token.encode()).decode()


# ============================================
# DERIV CONNECTION - PERSISTENT
# ============================================
class DerivConnection:
    """
    Persistent WebSocket connection to Deriv
    Each user has their own persistent connection
    """
    
    def __init__(self, user_id, token, config):
        self.user_id = user_id
        self.token = token  # Decrypted token
        self.config = config  # ✅ Flask config passed in
        
        # State
        self.ws = None
        self.connected = False
        self.connecting = False
        self.should_run = False
        
        # ✅ Thread safety lock
        self._state_lock = threading.Lock()
        
        # Subscriptions
        self.subscriptions = {}  # symbol -> callback
        
        # Message handlers
        self.message_handlers = {}  # msg_type -> callback
        
        # Pending requests
        self._pending_requests = {}
        self._request_counter = 0
        self._request_lock = threading.Lock()
        
        # Events
        self.event = threading.Event()
        
        # Thread
        self.thread = None
        
        # Reconnection
        self._reconnect_count = 0
        self._max_reconnects = 10
        
        # Connection metadata
        self.account_id = None
        self.currency = 'USD'
        self.balance = 0
        self.connected_at = None
        self.last_message = None
        self.last_pong = None
        
        # ✅ Heartbeat
        self._heartbeat_thread = None
    
    def get_ws_url(self):
        """Get WebSocket URL with app_id"""
        ws_url = self.config.get('DERIV_WS_URL')
        if not ws_url:
            raise ValueError("❌ DERIV_WS_URL not configured")
        return ws_url
    
    def connect(self):
        """Establish persistent WebSocket connection"""
        with self._state_lock:
            if self.connected or self.connecting:
                return
            
            self.connecting = True
            self.should_run = True
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                self.last_message = datetime.utcnow()
                
                # ✅ Route to appropriate handler
                self._route_message(data)
                
            except Exception as e:
                logger.error(f"WebSocket message error for user {self.user_id}: {e}")
        
        def on_error(ws, error):
            logger.error(f"WebSocket error for user {self.user_id}: {error}")
            with self._state_lock:
                self.connected = False
        
        def on_close(ws, close_status_code, close_msg):
            logger.warning(f"WebSocket closed for user {self.user_id}: {close_msg}")
            with self._state_lock:
                self.connected = False
                self.connecting = False
            
            # ✅ Auto-reconnect with exponential backoff
            if self.should_run and self._reconnect_count < self._max_reconnects:
                self._reconnect_count += 1
                wait_time = min(2 ** self._reconnect_count, 30)
                logger.info(f"🔄 Reconnecting user {self.user_id} in {wait_time}s (attempt {self._reconnect_count})")
                threading.Timer(wait_time, self.connect).start()
        
        def on_open(ws):
            with self._state_lock:
                self.ws = ws
                self.connected = True
                self.connecting = False
                self._reconnect_count = 0
                self.connected_at = datetime.utcnow()
            
            logger.info(f"✅ WebSocket connected for user {self.user_id}")
            
            # Send authorize
            self.send_authorize()
            
            # ✅ Start heartbeat
            self._start_heartbeat()
            
            # ✅ Resubscribe to all symbols
            self._resubscribe_all()
        
        ws_url = self.get_ws_url()
        self.event.clear()
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        self.thread = threading.Thread(target=self._run_forever, daemon=True)
        self.thread.start()
    
    def _run_forever(self):
        """Run WebSocket in background thread"""
        while self.should_run:
            try:
                self.ws.run_forever()
                if self.should_run:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"WebSocket run error for user {self.user_id}: {e}")
                time.sleep(1)
    
    def _route_message(self, data):
        """✅ Route incoming message to appropriate handler"""
        # 1. Check for request/response match
        req_id = data.get('req_id')
        if req_id and req_id in self._pending_requests:
            self._pending_requests[req_id]['response'] = data
            self._pending_requests[req_id]['event'].set()
            return
        
        # 2. Check for authorize response
        if 'authorize' in data:
            self._handle_authorize(data)
            return
        
        # 3. Check for balance response
        if 'balance' in data:
            self._handle_balance(data)
            return
        
        # 4. Check for error
        if 'error' in data:
            self._handle_error(data)
            return
        
        # 5. ✅ Check for tick messages (subscription)
        if data.get('msg_type') == 'tick':
            symbol = data.get('tick', {}).get('symbol')
            if symbol and symbol in self.subscriptions:
                try:
                    self.subscriptions[symbol](data)
                except Exception as e:
                    logger.error(f"Subscription handler error for {symbol}: {e}")
            return
        
        # 6. ✅ Check for generic message handlers
        msg_type = data.get('msg_type')
        if msg_type and msg_type in self.message_handlers:
            try:
                self.message_handlers[msg_type](data)
            except Exception as e:
                logger.error(f"Message handler error for {msg_type}: {e}")
    
    def _handle_authorize(self, data):
        """Handle authorize response"""
        auth_data = data.get('authorize', {})
        self.account_id = auth_data.get('loginid')
        self.currency = auth_data.get('currency', 'USD')
        self.balance = auth_data.get('balance', 0)
        logger.info(f"✅ User {self.user_id} authorized: {self.account_id}")
        self.event.set()
    
    def _handle_balance(self, data):
        """Handle balance response"""
        balance_data = data.get('balance', {})
        self.balance = balance_data.get('balance', 0)
    
    def _handle_error(self, data):
        """Handle error response"""
        error_msg = data.get('error', {}).get('message', 'Unknown error')
        logger.warning(f"Deriv error for user {self.user_id}: {error_msg}")
    
    def send_authorize(self):
        """Send authorization request"""
        if not self._is_ws_ready():
            return
        
        payload = {'authorize': self.token}
        self.send(payload)
    
    def send(self, payload):
        """Send message through WebSocket"""
        if not self._is_ws_ready():
            raise Exception("WebSocket not connected")
        
        try:
            self.ws.send(json.dumps(payload))
            return True
        except Exception as e:
            logger.error(f"Send error for user {self.user_id}: {e}")
            with self._state_lock:
                self.connected = False
            return False
    
    def _is_ws_ready(self):
        """Check if WebSocket is ready"""
        with self._state_lock:
            return self.connected and self.ws is not None
    
    def send_request(self, payload, timeout=10):
        """
        Send request and wait for response
        
        Returns:
            dict: Response data or None on timeout
        """
        with self._request_lock:
            self._request_counter += 1
            req_id = str(self._request_counter)
            payload['req_id'] = req_id
            
            event = threading.Event()
            self._pending_requests[req_id] = {
                'event': event,
                'response': None
            }
        
        try:
            if not self.send(payload):
                return None
            
            if event.wait(timeout):
                response = self._pending_requests[req_id].get('response')
                return response
            
            return None
            
        finally:
            # ✅ Cleanup always happens
            with self._request_lock:
                self._pending_requests.pop(req_id, None)
    
    def get_balance(self):
        """Fetch balance from Deriv"""
        if not self._is_ws_ready():
            raise Exception("WebSocket not connected")
        
        payload = {'balance': 1}
        response = self.send_request(payload, timeout=10)
        
        if response and 'balance' in response:
            self.balance = response['balance'].get('balance', 0)
            return self.balance
        
        return self.balance
    
    def is_connected(self):
        """Check if connection is active"""
        with self._state_lock:
            return self.connected and self.ws is not None
    
    def subscribe(self, symbol, callback):
        """✅ Subscribe to price updates for a symbol"""
        with self._state_lock:
            self.subscriptions[symbol] = callback
        
        if not self._is_ws_ready():
            logger.warning(f"Cannot subscribe {symbol}: not connected")
            return False
        
        payload = {
            'ticks': symbol,
            'subscribe': 1
        }
        return self.send(payload)
    
    def unsubscribe(self, symbol):
        """✅ Unsubscribe from a symbol"""
        with self._state_lock:
            if symbol in self.subscriptions:
                del self.subscriptions[symbol]
        
        if not self._is_ws_ready():
            return True
        
        payload = {
            'forget': symbol
        }
        return self.send(payload)
    
    def _resubscribe_all(self):
        """✅ Resubscribe to all symbols after reconnect"""
        symbols = list(self.subscriptions.keys())
        for symbol in symbols:
            callback = self.subscriptions[symbol]
            logger.info(f"🔄 Resubscribing {symbol} for user {self.user_id}")
            self.subscribe(symbol, callback)
    
    def _start_heartbeat(self):
        """✅ Start heartbeat thread"""
        def ping():
            while self.should_run:
                try:
                    if self.is_connected():
                        self.send({"ping": 1})
                        self.last_pong = datetime.utcnow()
                    time.sleep(20)
                except Exception as e:
                    logger.error(f"Heartbeat error for user {self.user_id}: {e}")
                    time.sleep(5)
        
        self._heartbeat_thread = threading.Thread(target=ping, daemon=True)
        self._heartbeat_thread.start()
    
    def disconnect(self):
        """Close connection gracefully"""
        self.should_run = False
        with self._state_lock:
            self.connected = False
            self.connecting = False
        
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None
        
        # Cleanup subscriptions
        with self._state_lock:
            self.subscriptions.clear()
    
    def reconnect(self):
        """Force reconnection"""
        self.disconnect()
        time.sleep(0.5)
        self.connect()


# ============================================
# CONNECTION MANAGER
# ============================================
class DerivConnectionManager:
    """Manages all user connections"""
    
    _instance = None
    _connections = {}
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self, user_id, config=None):
        """Get or create connection for user"""
        with self._lock:
            if user_id not in self._connections:
                # Try to get token from database
                account = DerivAccount.query.filter_by(user_id=user_id, is_connected=True).first()
                if not account:
                    logger.warning(f"No Deriv account found for user {user_id}")
                    return None
                
                # Decrypt token
                token = decrypt_token(account.api_token)
                if not token:
                    logger.error(f"Failed to decrypt token for user {user_id}")
                    return None
                
                # ✅ Pass config to connection
                if config is None:
                    from flask import current_app
                    config = current_app.config
                
                # Create new connection
                conn = DerivConnection(user_id, token, config)
                self._connections[user_id] = conn
                conn.connect()
                return conn
            
            return self._connections[user_id]
    
    def remove_connection(self, user_id):
        """Remove connection for user"""
        with self._lock:
            if user_id in self._connections:
                try:
                    self._connections[user_id].disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting user {user_id}: {e}")
                del self._connections[user_id]
                return True
            return False
    
    def get_all_connections(self):
        """Get all active connections"""
        with self._lock:
            return self._connections.copy()
    
    def get_active_user_ids(self):
        """Get all connected user IDs"""
        with self._lock:
            return [uid for uid, conn in self._connections.items() if conn.is_connected()]
    
    def get_connection_status(self, user_id):
        """Get status of a connection"""
        with self._lock:
            if user_id not in self._connections:
                return {'connected': False}
            
            conn = self._connections[user_id]
            return {
                'connected': conn.is_connected(),
                'account_id': conn.account_id,
                'currency': conn.currency,
                'balance': conn.balance,
                'connected_at': conn.connected_at,
                'subscriptions': list(conn.subscriptions.keys())
            }
    
    def cleanup_all(self):
        """Cleanup all connections on shutdown"""
        logger.info("🧹 Cleaning up all connections...")
        for user_id in list(self._connections.keys()):
            self.remove_connection(user_id)
        logger.info("✅ All connections cleaned up")


# ============================================
# GLOBAL CONNECTION MANAGER INSTANCE
# ============================================
connection_manager = DerivConnectionManager()


# ============================================
# ACCOUNT MANAGEMENT (Using Persistent Connections)
# ============================================
def connect_deriv_account(user_id, api_token):
    """
    Connect a Deriv account for a user
    
    Returns:
        {
            'success': bool,
            'message': str,
            'data': dict
        }
    """
    try:
        # 1. Validate token (temporary connection)
        validation = validate_deriv_token(api_token)
        
        if not validation.get('success'):
            error_msg = validation.get('error', 'Invalid Deriv token')
            raise Exception(error_msg)
        
        # 2. Encrypt token for storage
        encrypted_token = encrypt_token(api_token)
        
        # 3. Check if user already has a Deriv account
        existing = DerivAccount.query.filter_by(user_id=user_id).first()
        
        if existing:
            existing.api_token = encrypted_token
            existing.account_id = validation.get('account_id')
            existing.currency = validation.get('currency', 'USD')
            existing.balance = validation.get('balance', 0)
            existing.is_connected = True
            existing.last_active_at = datetime.utcnow()
            db.session.commit()
            deriv_account = existing
        else:
            deriv_account = DerivAccount(
                user_id=user_id,
                api_token=encrypted_token,
                account_id=validation.get('account_id'),
                currency=validation.get('currency', 'USD'),
                balance=validation.get('balance', 0),
                is_connected=True,
                connection_date=datetime.utcnow(),
                last_active_at=datetime.utcnow()
            )
            db.session.add(deriv_account)
            db.session.commit()
        
        # 4. Create persistent connection
        from flask import current_app
        connection_manager.remove_connection(user_id)
        conn = connection_manager.get_connection(user_id, current_app.config)
        
        if not conn:
            raise Exception("Failed to establish connection")
        
        # Wait for connection to be ready
        if not conn.event.wait(10):
            raise Exception("Connection timeout")
        
        return {
            'success': True,
            'message': 'Deriv account connected successfully',
            'data': deriv_account.to_dict()
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Connect error for user {user_id}: {e}")
        raise e


def disconnect_deriv_account(user_id):
    """Disconnect a Deriv account"""
    try:
        account = DerivAccount.query.filter_by(user_id=user_id).first()
        
        if not account:
            raise Exception('No Deriv account found')
        
        # Remove persistent connection
        connection_manager.remove_connection(user_id)
        
        # Update account status
        account.is_connected = False
        account.last_active_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'success': True,
            'message': 'Deriv account disconnected successfully'
        }
        
    except Exception as e:
        db.session.rollback()
        raise e


def get_deriv_account_status(user_id):
    """Get Deriv account status"""
    try:
        account = DerivAccount.query.filter_by(user_id=user_id).first()
        
        if not account:
            return {
                'success': True,
                'data': {'isConnected': False}
            }
        
        # Check if connection is active
        conn = connection_manager.get_connection(user_id)
        if conn and conn.is_connected():
            account.is_connected = True
        
        return {
            'success': True,
            'data': account.to_dict()
        }
        
    except Exception as e:
        raise e


def get_deriv_balance(user_id):
    """Get Deriv account balance (using persistent connection)"""
    try:
        from flask import current_app
        
        # Get or create connection
        conn = connection_manager.get_connection(user_id, current_app.config)
        
        if not conn or not conn.is_connected():
            account = DerivAccount.query.filter_by(user_id=user_id, is_connected=True).first()
            if not account:
                raise Exception('Deriv account not connected')
            
            conn = connection_manager.get_connection(user_id, current_app.config)
            if not conn or not conn.event.wait(10):
                raise Exception('Failed to establish connection')
        
        # Get balance from persistent connection
        balance = conn.get_balance()
        
        # Update database
        account = DerivAccount.query.filter_by(user_id=user_id).first()
        if account:
            account.balance = balance
            account.last_active_at = datetime.utcnow()
            db.session.commit()
        
        return {
            'success': True,
            'data': {'balance': balance}
        }
        
    except Exception as e:
        raise e


def validate_deriv_token(token):
    """
    Validate Deriv API token (using temporary connection)
    Used only for initial validation
    """
    result = {
        'success': False,
        'account_id': None,
        'currency': 'USD',
        'balance': 0,
        'error': None
    }
    
    event = threading.Event()
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            
            if 'error' in data:
                result['error'] = data['error'].get('message', 'Authorization failed')
                event.set()
                ws.close()
                return
            
            if data.get('code') == 0 and data.get('msg') == 'authorize':
                result['success'] = True
                auth_data = data.get('authorize', {})
                result['account_id'] = auth_data.get('loginid')
                result['currency'] = auth_data.get('currency', 'USD')
                result['balance'] = auth_data.get('balance', 0)
                event.set()
                ws.close()
                return
            
            if 'authorize' in data:
                result['success'] = True
                auth_data = data['authorize']
                result['account_id'] = auth_data.get('loginid')
                result['currency'] = auth_data.get('currency', 'USD')
                result['balance'] = auth_data.get('balance', 0)
                event.set()
                ws.close()
                
        except Exception as e:
            result['error'] = str(e)
            event.set()
            ws.close()
    
    def on_error(ws, error):
        result['error'] = str(error)
        event.set()
        ws.close()
    
    def on_open(ws):
        ws.send(json.dumps({'authorize': token}))
    
    from flask import current_app
    ws_url = current_app.config.get('DERIV_WS_URL')
    if not ws_url:
        return {'success': False, 'error': 'DERIV_WS_URL not configured'}
    
    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error
        )
        
        thread = threading.Thread(target=ws.run_forever, daemon=True)
        thread.start()
        
        if not event.wait(30):
            result['error'] = 'Timeout waiting for response'
            ws.close()
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_account_info(user_id):
    """Get full account info from database"""
    try:
        account = DerivAccount.query.filter_by(user_id=user_id).first()
        if not account:
            return {
                'success': False,
                'message': 'No Deriv account found'
            }
        
        # Update connection status
        conn = connection_manager.get_connection(user_id)
        if conn and conn.is_connected():
            account.is_connected = True
        
        return {
            'success': True,
            'data': account.to_dict()
        }
        
    except Exception as e:
        raise e


def is_deriv_connected(user_id):
    """Check if user has an active Deriv connection"""
    try:
        account = DerivAccount.query.filter_by(user_id=user_id, is_connected=True).first()
        if not account:
            return False
        
        conn = connection_manager.get_connection(user_id)
        return conn is not None and conn.is_connected()
        
    except:
        return False


def get_connection_status(user_id):
    """Get detailed connection status"""
    return connection_manager.get_connection_status(user_id)


def subscribe_to_symbol(user_id, symbol, callback):
    """Subscribe to price updates for a symbol"""
    from flask import current_app
    conn = connection_manager.get_connection(user_id, current_app.config)
    
    if not conn or not conn.is_connected():
        raise Exception('Deriv connection not available')
    
    return conn.subscribe(symbol, callback)


def unsubscribe_from_symbol(user_id, symbol):
    """Unsubscribe from a symbol"""
    from flask import current_app
    conn = connection_manager.get_connection(user_id, current_app.config)
    
    if not conn or not conn.is_connected():
        return True
    
    return conn.unsubscribe(symbol)


# ============================================
# CLEANUP ON SHUTDOWN
# ============================================
def cleanup_all_connections():
    """Cleanup all connections on shutdown"""
    connection_manager.cleanup_all()