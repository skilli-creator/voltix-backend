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

logger = logging.getLogger(__name__)

DERIV_API_URL = "https://api.derivws.com"

# ============================================
# ENCRYPTION
# ============================================
def get_encryption_key():
    from flask import current_app
    key = current_app.config.get('ENCRYPTION_KEY')
    if not key:
        raise ValueError("ENCRYPTION_KEY missing")
    return key.encode() if isinstance(key, str) else key


def encrypt_token(token):
    if not token:
        return None
    return Fernet(get_encryption_key()).encrypt(token.encode()).decode()


def decrypt_token(token):
    if not token:
        return None
    return Fernet(get_encryption_key()).decrypt(token.encode()).decode()


# ============================================
# REST API
# ============================================
def get_deriv_accounts(api_token):
    try:
        res = requests.get(
            f"{DERIV_API_URL}/trading/v1/options/accounts",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=10
        )
        if res.status_code != 200:
            logger.error(f"Accounts fetch failed: {res.status_code}")
            return None
        return res.json().get("data", [])
    except Exception as e:
        logger.error(f"Accounts error: {e}")
        return None


def request_otp(api_token, account_id):
    try:
        res = requests.get(
            f"{DERIV_API_URL}/trading/v1/options/accounts/{account_id}/otp",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=10
        )
        if res.status_code != 200:
            logger.error(f"OTP failed: {res.status_code}")
            return None
        return res.json().get("data", {}).get("ws_url")
    except Exception as e:
        logger.error(f"OTP error: {e}")
        return None


def validate_deriv_token(api_token):
    accounts = get_deriv_accounts(api_token)
    if not accounts:
        return {"success": False, "error": "Invalid token"}

    acc = next((a for a in accounts if a.get("status") == "active"), accounts[0])

    return {
        "success": True,
        "account_id": acc.get("account_id"),
        "currency": acc.get("currency"),
        "balance": float(acc.get("balance", 0)),
        "accounts": accounts
    }


# ============================================
# CONNECTION CLASS
# ============================================
class DerivConnection:
    def __init__(self, user_id, api_token, socketio=None):
        self.user_id = user_id
        self.api_token = api_token
        self.socketio = socketio

        self.ws = None
        self.connected = False
        self.authorized = False
        self.should_run = False

        self.account_id = None
        self.currency = "USD"
        self.balance = 0

        self._lock = threading.Lock()
        self._pending = {}
        self._req_id = 0

    # ========================================
    # CONNECT
    # ========================================
    def connect(self):
        accounts = get_deriv_accounts(self.api_token)
        if not accounts:
            logger.error("No accounts found")
            return

        acc = next((a for a in accounts if a["status"] == "active"), accounts[0])
        self.account_id = acc["account_id"]
        self.currency = acc["currency"]
        self.balance = float(acc["balance"])

        ws_url = request_otp(self.api_token, self.account_id)
        if not ws_url:
            logger.error("OTP failed")
            return

        self.should_run = True

        def on_open(ws):
            logger.info("WS connected")
            self.connected = True

            # SAFE: always send authorize
            self.send({"authorize": self.api_token})

        def on_message(ws, message):
            data = json.loads(message)

            # AUTHORIZE
            if data.get("msg_type") == "authorize":
                if "error" in data:
                    logger.error(f"Authorize failed: {data['error']}")
                else:
                    logger.info("Authorized OK")
                    self.authorized = True

                    self.subscribe_balance()
                    self.subscribe_transactions()

                    if self.socketio:
                        self.socketio.emit("deriv_authorized", {
                            "account_id": self.account_id,
                            "currency": self.currency,
                            "balance": self.balance
                        }, room=f"user_{self.user_id}")

            # CALLBACKS
            req_id = data.get("req_id")
            if req_id and req_id in self._pending:
                self._pending[req_id]["response"] = data
                self._pending[req_id]["event"].set()

            # BALANCE
            if "balance" in data:
                new_balance = data["balance"]["balance"]
                if new_balance != self.balance:
                    self.balance = new_balance
                    logger.info(f"Balance updated: {self.balance}")

                    if self.socketio:
                        self.socketio.emit("deriv_balance_update", {
                            "balance": self.balance,
                            "currency": self.currency
                        }, room=f"user_{self.user_id}")

            # ERRORS
            if "error" in data:
                logger.warning(f"Deriv error: {data['error']}")

        def on_close(ws, *args):
            logger.warning("WS closed")
            self.connected = False
            self.authorized = False

            if self.should_run:
                time.sleep(3)
                self.connect()

        def on_error(ws, error):
            logger.error(f"WS error: {error}")

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error
        )

        threading.Thread(target=self.ws.run_forever, daemon=True).start()

    # ========================================
    # SEND
    # ========================================
    def send(self, payload):
        if not self.ws or not self.connected:
            return False
        try:
            self.ws.send(json.dumps(payload))
            return True
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False

    # ========================================
    # REQUEST
    # ========================================
    def send_request(self, payload, timeout=10):
        with self._lock:
            self._req_id += 1
            req_id = str(self._req_id)
            payload["req_id"] = req_id

            event = threading.Event()
            self._pending[req_id] = {"event": event, "response": None}

        self.send(payload)

        if event.wait(timeout):
            return self._pending[req_id]["response"]

        return None

    # ========================================
    # SUBSCRIPTIONS
    # ========================================
    def subscribe_balance(self):
        self.send({"balance": 1, "subscribe": 1})

    def subscribe_transactions(self):
        self.send({"transaction": 1, "subscribe": 1})

    # ========================================
    # DISCONNECT
    # ========================================
    def disconnect(self):
        self.should_run = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass


# ============================================
# CONNECTION MANAGER
# ============================================
class DerivConnectionManager:
    def __init__(self):
        self.connections = {}
        self.socketio = None

    def init_socketio(self, socketio):
        self.socketio = socketio

        @socketio.on('connect')
        def handle_connect():
            logger.info("Client connected")

        @socketio.on('disconnect')
        def handle_disconnect():
            logger.info("Client disconnected")

        @socketio.on('join')
        def handle_join(data):
            user_id = data.get('user_id')
            if user_id:
                join_room(f"user_{user_id}")

    def get(self, user_id):
        return self.connections.get(user_id)

    def create(self, user_id, token):
        conn = DerivConnection(user_id, token, self.socketio)
        self.connections[user_id] = conn
        conn.connect()
        return conn

    def remove(self, user_id):
        if user_id in self.connections:
            self.connections[user_id].disconnect()
            del self.connections[user_id]


connection_manager = DerivConnectionManager()

# ============================================
# SOCKET.IO EXPORTS (FIXED)
# ============================================
def init_socketio(socketio):
    connection_manager.init_socketio(socketio)
    return socketio


def cleanup_all_connections():
    for user_id in list(connection_manager.connections.keys()):
        connection_manager.remove(user_id)


# ============================================
# PUBLIC FUNCTIONS
# ============================================
def connect_deriv_account(user_id, token):
    val = validate_deriv_token(token)
    if not val["success"]:
        raise Exception(val["error"])

    enc = encrypt_token(token)

    db.save_deriv_token(
        user_id=user_id,
        encrypted_token=enc,
        account_id=val["account_id"],
        currency=val["currency"],
        balance=val["balance"]
    )

    connection_manager.remove(user_id)
    conn = connection_manager.create(user_id, token)

    return {"success": True, "data": val}


def disconnect_deriv_account(user_id):
    connection_manager.remove(user_id)
    db.disconnect_deriv(user_id)
    return {"success": True}


def get_deriv_balance(user_id):
    conn = connection_manager.get(user_id)
    if not conn:
        raise Exception("Not connected")
    return {"success": True, "balance": conn.balance}


def get_connection_status(user_id):
    conn = connection_manager.get(user_id)
    return {"connected": conn.connected if conn else False}