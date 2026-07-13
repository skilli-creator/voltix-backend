# backend/services/deriv_service.py
import json
import websocket
import threading
import time
import logging
import requests
from datetime import datetime
from cryptography.fernet import Fernet
from flask_socketio import emit, join_room, leave_room
from models.database import db

# ============================================
# LOGGING
# ============================================
logger = logging.getLogger(__name__)

# ============================================
# ENCRYPTION HELPERS
# ============================================
def get_encryption_key():
    from flask import current_app
    key = current_app.config.get('ENCRYPTION_KEY')
    if not key:
        raise ValueError("❌ ENCRYPTION_KEY not configured")
    return key.encode() if isinstance(key, str) else key

def encrypt_token(token):
    if not token:
        return None
    fernet = Fernet(get_encryption_key())
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token):
    if not encrypted_token:
        return None
    fernet = Fernet(get_encryption_key())
    return fernet.decrypt(encrypted_token.encode()).decode()

# ============================================
# DERIV API - PAT + OTP FLOW
# ============================================

DERIV_API_URL = "https://api.derivws.com"
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3"

def get_deriv_accounts(api_token):
    """Step 3: Get all accounts for a Deriv PAT token"""
    try:
        url = f"{DERIV_API_URL}/trading/v1/options/accounts"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"📡 GET /accounts with PAT token")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"❌ Failed to get accounts: {response.status_code}")
            return None
        
        data = response.json()
        accounts = data.get('data', [])
        logger.info(f"✅ Found {len(accounts)} account(s)")
        
        for acc in accounts:
            logger.info(f"   - {acc.get('account_id')} ({acc.get('currency')}) balance: {acc.get('balance')} [{acc.get('status')}]")
        
        return accounts
        
    except Exception as e:
        logger.error(f"❌ Error getting accounts: {e}")
        return None

def request_otp(api_token, account_id):
    """Step 5: Request OTP for WebSocket session"""
    try:
        url = f"{DERIV_API_URL}/trading/v1/options/accounts/{account_id}/otp"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"🔑 Requesting OTP for {account_id}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"❌ Failed to get OTP: {response.status_code}")
            return None
        
        data = response.json()
        ws_url = data.get('data', {}).get('ws_url')
        
        if not ws_url:
            logger.error(f"❌ No WebSocket URL in OTP response")
            return None
        
        logger.info(f"✅ OTP received, WebSocket URL ready")
        return ws_url
        
    except Exception as e:
        logger.error(f"❌ Error requesting OTP: {e}")
        return None

# ============================================
# VALIDATE DERIV TOKEN
# ============================================

def validate_deriv_token(api_token):
    """Validate Deriv PAT token by getting accounts"""
    try:
        logger.info(f"🔍 Validating PAT token...")
        
        accounts = get_deriv_accounts(api_token)
        
        if not accounts:
            return {
                'success': False,
                'error': 'Invalid API token or no accounts found'
            }
        
        active_account = None
        for acc in accounts:
            if acc.get('status') == 'active':
                active_account = acc
                break
        
        if not active_account:
            active_account = accounts[0]
        
        logger.info(f"✅ Active account: {active_account.get('account_id')}")
        
        return {
            'success': True,
            'account_id': active_account.get('account_id'),
            'currency': active_account.get('currency', 'USD'),
            'balance': float(active_account.get('balance', 0)),
            'accounts': accounts
        }
        
    except Exception as e:
        logger.error(f"❌ Validation error: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# ============================================
# DERIV CONNECTION - WITH AUTHORIZATION STATE
# ============================================
class DerivConnection:
    def __init__(self, user_id, api_token, config, socketio=None):
        self.user_id = user_id
        self.api_token = api_token
        self.config = config
        self.socketio = socketio
        
        # WebSocket state
        self.ws = None
        self.connected = False
        self.connecting = False
        self.should_run = False
        self._state_lock = threading.Lock()
        
        # ✅ CRITICAL: Authorization state
        self._authorized = False
        
        # Account info
        self.account_id = None
        self.currency = 'USD'
        self.balance = 0
        self.accounts = []
        self.connected_at = None
        self.last_message = None
        
        # Callback system
        self._pending_requests = {}
        self._request_counter = 0
        self._request_lock = threading.Lock()
        
        # Event system
        self.event = threading.Event()
        self.thread = None
        
        # Reconnection
        self._reconnect_count = 0
        self._max_reconnects = 10
        
        # Heartbeat
        self._heartbeat_thread = None
        
        # Cleanup timer
        self._cleanup_timer = None
        self._start_request_cleanup()
    
    def _start_request_cleanup(self):
        """Clean up stale pending requests"""
        def cleanup():
            while self.should_run:
                time.sleep(30)
                with self._request_lock:
                    now = time.time()
                    stale = []
                    for req_id, data in self._pending_requests.items():
                        if data.get('created_at', 0) < now - 60:
                            stale.append(req_id)
                    for req_id in stale:
                        logger.warning(f"⚠️ Cleaning up stale request: {req_id}")
                        self._pending_requests.pop(req_id, None)
        
        self._cleanup_timer = threading.Thread(target=cleanup, daemon=True)
        self._cleanup_timer.start()
    
    def connect(self):
        """Step 6: Establish WebSocket connection using PAT + OTP flow"""
        with self._state_lock:
            if self.connected or self.connecting:
                return
            self.connecting = True
            self.should_run = True
            self._authorized = False  # ✅ Reset auth state on connect
        
        # Step 3: Get accounts
        logger.info(f"📡 Getting accounts for user {self.user_id}")
        accounts = get_deriv_accounts(self.api_token)
        
        if not accounts:
            logger.error(f"❌ No accounts found")
            with self._state_lock:
                self.connecting = False
            return
        
        self.accounts = accounts
        
        # Step 4: Select active account
        active_account = None
        for acc in accounts:
            if acc.get('status') == 'active':
                active_account = acc
                break
        
        if not active_account:
            active_account = accounts[0]
        
        self.account_id = active_account.get('account_id')
        self.currency = active_account.get('currency', 'USD')
        self.balance = float(active_account.get('balance', 0))
        
        logger.info(f"✅ Selected account: {self.account_id} ({self.currency}) balance: {self.balance}")
        
        # Step 5: Request OTP
        logger.info(f"🔑 Requesting OTP for {self.account_id}")
        ws_url = request_otp(self.api_token, self.account_id)
        
        if not ws_url:
            logger.error(f"❌ Failed to get OTP")
            with self._state_lock:
                self.connecting = False
            return
        
        logger.info(f"✅ OTP received, connecting WebSocket...")
        
        # Step 6: WebSocket connection
        def on_message(ws, message):
            try:
                data = json.loads(message)
                self.last_message = datetime.utcnow()
                self._route_message(data)
            except Exception as e:
                logger.error(f"WebSocket message error: {e}")
        
        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")
            with self._state_lock:
                self.connected = False
        
        def on_close(ws, close_status_code, close_msg):
            logger.warning(f"WebSocket closed: {close_msg}")
            with self._state_lock:
                self.connected = False
                self.connecting = False
                self._authorized = False  # ✅ Reset auth on close
            
            if self.should_run and self._reconnect_count < self._max_reconnects:
                self._reconnect_count += 1
                wait_time = min(2 ** self._reconnect_count, 30)
                logger.info(f"🔄 Reconnecting in {wait_time}s (attempt {self._reconnect_count})")
                threading.Timer(wait_time, self.connect).start()
        
        def on_open(ws):
            with self._state_lock:
                self.ws = ws
                self.connected = True
                self.connecting = False
                self._reconnect_count = 0
                self.connected_at = datetime.utcnow()
            
            logger.info(f"✅ WebSocket connected")
            logger.info(f"🔐 Sending authorization...")
            
            # Send authorize
            auth_payload = {"authorize": self.api_token}
            self.send(auth_payload)
            
            # Start heartbeat
            self._start_heartbeat()
            
            self.event.set()
        
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
        
        if not self.event.wait(10):
            logger.error(f"❌ Connection timeout")
            with self._state_lock:
                self.connecting = False
    
    def _run_forever(self):
        while self.should_run:
            try:
                self.ws.run_forever()
                if self.should_run:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"WebSocket run error: {e}")
                time.sleep(1)
    
    def _route_message(self, data):
        """Route incoming message to appropriate handler"""
        msg_type = data.get('msg_type')
        
        # ✅ Step 6: Handle authorization response
        if msg_type == 'authorize':
            if 'error' in data:
                error_msg = data['error'].get('message', 'Authorization failed')
                logger.error(f"❌ Authorization failed: {error_msg}")
                with self._state_lock:
                    self._authorized = False
                
                if self.socketio:
                    self.socketio.emit('deriv_error', {
                        'error': error_msg
                    }, room=f'user_{self.user_id}')
            else:
                logger.info(f"✅ Authorization successful")
                with self._state_lock:
                    self._authorized = True
                
                # ✅ Step 7: Subscribe ONLY after authorization
                self._subscribe_balance()
                self._subscribe_transactions()
                
                if self.socketio:
                    self.socketio.emit('deriv_authorized', {
                        'account_id': self.account_id,
                        'currency': self.currency,
                        'balance': self.balance
                    }, room=f'user_{self.user_id}')
            return
        
        # Step 10: Handle request/response callbacks
        req_id = data.get('req_id')
        if req_id:
            if req_id in self._pending_requests:
                logger.info(f"📨 Found callback for req_id: {req_id}")
                self._pending_requests[req_id]['response'] = data
                self._pending_requests[req_id]['event'].set()
            else:
                logger.warning(f"⚠️ No callback found for req_id: {req_id}")
            return
        
        # Step 10: Handle balance updates
        if 'balance' in data:
            self._handle_balance(data)
            return
        
        # Handle errors
        if 'error' in data:
            self._handle_error(data)
            return
    
    def _handle_balance(self, data):
        """Step 10: Handle balance update"""
        balance_data = data.get('balance', {})
        new_balance = balance_data.get('balance', 0)
        
        # ✅ Log even when unchanged (for debugging)
        logger.info(f"💰 Balance: {self.balance} → {new_balance}")
        
        if new_balance != self.balance:
            self.balance = new_balance
            
            if self.socketio:
                self.socketio.emit('deriv_balance_update', {
                    'balance': self.balance,
                    'currency': self.currency,
                    'account_id': self.account_id
                }, room=f'user_{self.user_id}')
    
    def _handle_error(self, data):
        error_msg = data.get('error', {}).get('message', 'Unknown error')
        logger.warning(f"⚠️ Deriv error: {error_msg}")
        
        if self.socketio:
            self.socketio.emit('deriv_error', {
                'error': error_msg
            }, room=f'user_{self.user_id}')
    
    def _subscribe_balance(self):
        """Step 7: Subscribe to balance updates (ONLY if authorized)"""
        if not self._is_ready():
            logger.warning(f"⚠️ Cannot subscribe to balance: not ready (connected={self.connected}, authorized={self._authorized})")
            return
        
        payload = {'balance': 1, 'subscribe': 1}
        self.send(payload)
        logger.info(f"📊 Subscribed to balance updates")
    
    def _subscribe_transactions(self):
        """Step 7: Subscribe to transaction stream (ONLY if authorized)"""
        if not self._is_ready():
            logger.warning(f"⚠️ Cannot subscribe to transactions: not ready")
            return
        
        payload = {
            'transaction': 1,
            'subscribe': 1
        }
        self.send(payload)
        logger.info(f"📊 Subscribed to transaction stream")
    
    # ✅ CRITICAL: Check both connection AND authorization
    def _is_ready(self):
        """Check if WebSocket is connected AND authorized"""
        with self._state_lock:
            return self.connected and self.ws is not None and self._authorized
    
    def _is_ws_ready(self):
        """Legacy: Check if WebSocket is connected (without auth)"""
        with self._state_lock:
            return self.connected and self.ws is not None
    
    def send(self, payload):
        if not self._is_ws_ready():
            logger.error(f"❌ Cannot send: WebSocket not connected")
            return False
        
        if not self._authorized:
            logger.warning(f"⚠️ Sending without authorization - may fail: {payload.get('msg_type', 'unknown')}")
        
        try:
            self.ws.send(json.dumps(payload))
            return True
        except Exception as e:
            logger.error(f"❌ Send error: {e}")
            with self._state_lock:
                self.connected = False
            return False
    
    def send_request(self, payload, timeout=10):
        """Step 10: Send request with callback"""
        if not self._is_ready():
            raise Exception("WebSocket not connected or not authorized")
        
        with self._request_lock:
            self._request_counter += 1
            req_id = str(self._request_counter)
            payload['req_id'] = req_id
            
            event = threading.Event()
            self._pending_requests[req_id] = {
                'event': event,
                'response': None,
                'created_at': time.time()
            }
        
        try:
            if not self.send(payload):
                return None
            
            if event.wait(timeout):
                response = self._pending_requests[req_id].get('response')
                if response:
                    logger.info(f"✅ Request {req_id} completed")
                return response
            
            logger.warning(f"⏰ Request {req_id} timed out")
            return None
            
        finally:
            with self._request_lock:
                self._pending_requests.pop(req_id, None)
    
    def get_balance(self):
        """Step 10: Get balance via request"""
        if not self._is_ready():
            raise Exception("WebSocket not connected or not authorized")
        
        logger.info(f"📊 Requesting balance via req_id")
        payload = {'balance': 1}
        response = self.send_request(payload, timeout=10)
        
        if response and 'balance' in response:
            new_balance = response['balance'].get('balance', 0)
            logger.info(f"💰 Balance request returned: {new_balance}")
            self.balance = new_balance
            return self.balance
        
        return self.balance
    
    def is_connected(self):
        with self._state_lock:
            return self.connected and self.ws is not None
    
    def is_authorized(self):
        with self._state_lock:
            return self._authorized
    
    def is_ready(self):
        """Full readiness check: connected AND authorized"""
        with self._state_lock:
            return self.connected and self.ws is not None and self._authorized
    
    def _start_heartbeat(self):
        def ping():
            while self.should_run:
                try:
                    if self.is_connected():
                        self.send({"ping": 1})
                    time.sleep(20)
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                    time.sleep(5)
        
        self._heartbeat_thread = threading.Thread(target=ping, daemon=True)
        self._heartbeat_thread.start()
    
    def disconnect(self):
        self.should_run = False
        with self._state_lock:
            self.connected = False
            self.connecting = False
            self._authorized = False
        
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None

# ============================================
# CONNECTION MANAGER
# ============================================
class DerivConnectionManager:
    _instance = None
    _connections = {}
    _lock = threading.Lock()
    _socketio = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def init_socketio(self, socketio):
        self._socketio = socketio
        
        @socketio.on('connect')
        def handle_connect():
            logger.info('✅ Client connected to Socket.IO')
            emit('connected', {'status': 'ok'})
        
        @socketio.on('disconnect')
        def handle_disconnect():
            logger.info('❌ Client disconnected from Socket.IO')
        
        @socketio.on('join')
        def handle_join(data):
            user_id = data.get('user_id')
            if user_id:
                join_room(f'user_{user_id}')
                emit('joined', {'room': f'user_{user_id}'})
                logger.info(f"User {user_id} joined room")
        
        @socketio.on('leave')
        def handle_leave(data):
            user_id = data.get('user_id')
            if user_id:
                leave_room(f'user_{user_id}')
                emit('left', {'room': f'user_{user_id}'})
    
    def get_connection(self, user_id, config=None):
        with self._lock:
            if user_id not in self._connections:
                account = db.get_deriv_token(user_id)
                if not account:
                    logger.warning(f"No Deriv account found for user {user_id}")
                    return None
                
                api_token = decrypt_token(account.get('api_token'))
                if not api_token:
                    logger.error(f"Failed to decrypt token for user {user_id}")
                    return None
                
                if config is None:
                    from flask import current_app
                    config = current_app.config
                
                conn = DerivConnection(user_id, api_token, config, self._socketio)
                self._connections[user_id] = conn
                conn.connect()
                return conn
            
            return self._connections[user_id]
    
    def remove_connection(self, user_id):
        with self._lock:
            if user_id in self._connections:
                try:
                    self._connections[user_id].disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting user {user_id}: {e}")
                del self._connections[user_id]
                return True
            return False
    
    def get_connection_status(self, user_id):
        with self._lock:
            if user_id not in self._connections:
                return {'connected': False}
            
            conn = self._connections[user_id]
            return {
                'connected': conn.is_connected(),
                'authorized': conn.is_authorized(),
                'ready': conn.is_ready(),
                'account_id': conn.account_id,
                'currency': conn.currency,
                'balance': conn.balance,
                'accounts': conn.accounts,
                'connected_at': conn.connected_at
            }
    
    def emit_to_user(self, user_id, event, data):
        if self._socketio:
            self._socketio.emit(event, data, room=f'user_{user_id}')
    
    def cleanup_all(self):
        logger.info("🧹 Cleaning up all connections...")
        for user_id in list(self._connections.keys()):
            self.remove_connection(user_id)
        logger.info("✅ All connections cleaned up")

# ============================================
# GLOBAL INSTANCE
# ============================================
connection_manager = DerivConnectionManager()

# ============================================
# EXPORTED FUNCTIONS
# ============================================

def connect_deriv_account(user_id, api_token):
    try:
        validation = validate_deriv_token(api_token)
        
        if not validation.get('success'):
            raise Exception(validation.get('error', 'Invalid API token'))
        
        encrypted_token = encrypt_token(api_token)
        
        success = db.save_deriv_token(
            user_id=user_id,
            encrypted_token=encrypted_token,
            account_id=validation.get('account_id'),
            currency=validation.get('currency', 'USD'),
            balance=validation.get('balance', 0)
        )
        
        if not success:
            raise Exception("Failed to save token")
        
        from flask import current_app
        connection_manager.remove_connection(user_id)
        conn = connection_manager.get_connection(user_id, current_app.config)
        
        if not conn:
            raise Exception("Failed to establish connection")
        
        if not conn.event.wait(10):
            raise Exception("Connection timeout")
        
        # Wait a moment for authorization
        time.sleep(2)
        
        connection_manager.emit_to_user(user_id, 'deriv_connected', {
            'success': True,
            'account_id': conn.account_id,
            'currency': conn.currency,
            'balance': conn.balance,
            'accounts': conn.accounts,
            'authorized': conn.is_authorized()
        })
        
        return {
            'success': True,
            'message': 'Deriv account connected successfully',
            'data': {
                'account_id': conn.account_id,
                'currency': conn.currency,
                'balance': conn.balance,
                'accounts': conn.accounts,
                'authorized': conn.is_authorized()
            }
        }
        
    except Exception as e:
        logger.error(f"Connect error: {e}")
        raise e

def disconnect_deriv_account(user_id):
    try:
        connection_manager.remove_connection(user_id)
        db.disconnect_deriv(user_id)
        
        connection_manager.emit_to_user(user_id, 'deriv_disconnected', {
            'success': True,
            'message': 'Deriv account disconnected'
        })
        
        return {
            'success': True,
            'message': 'Deriv account disconnected successfully'
        }
        
    except Exception as e:
        logger.error(f"Disconnect error: {e}")
        raise e

def get_deriv_account_status(user_id):
    try:
        status = db.get_deriv_account_status(user_id)
        
        if not status:
            return {'success': True, 'data': {'isConnected': False}}
        
        conn = connection_manager.get_connection(user_id)
        if conn and conn.is_connected():
            status['isConnected'] = True
            status['isAuthorized'] = conn.is_authorized()
            status['isReady'] = conn.is_ready()
        
        return {'success': True, 'data': status}
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise e

def get_deriv_balance(user_id):
    try:
        from flask import current_app
        
        conn = connection_manager.get_connection(user_id, current_app.config)
        
        if not conn or not conn.is_connected():
            raise Exception('Deriv account not connected')
        
        if not conn.is_authorized():
            raise Exception('Deriv account not authorized')
        
        balance = conn.get_balance()
        db.update_deriv_balance(user_id, balance)
        
        return {
            'success': True,
            'data': {'balance': balance}
        }
        
    except Exception as e:
        logger.error(f"Balance error: {e}")
        raise e

def get_account_info(user_id):
    try:
        account = db.get_deriv_token(user_id)
        if not account:
            return {'success': False, 'message': 'No Deriv account found'}
        
        conn = connection_manager.get_connection(user_id)
        if conn and conn.is_connected():
            account['isConnected'] = True
            account['isAuthorized'] = conn.is_authorized()
            account['isReady'] = conn.is_ready()
        
        return {'success': True, 'data': account}
        
    except Exception as e:
        logger.error(f"Account info error: {e}")
        raise e

def is_deriv_connected(user_id):
    try:
        account = db.get_deriv_token(user_id)
        if not account:
            return False
        
        conn = connection_manager.get_connection(user_id)
        return conn is not None and conn.is_connected()
        
    except:
        return False

def get_connection_status(user_id):
    return connection_manager.get_connection_status(user_id)

def init_socketio(socketio):
    connection_manager.init_socketio(socketio)
    return socketio

def cleanup_all_connections():
    connection_manager.cleanup_all()

# ============================================
# ✅ Export the service
# ============================================
deriv_service = connection_manager