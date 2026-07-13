import json
import websocket
import threading
import time
import logging
import requests
from cryptography.fernet import Fernet
from flask_socketio import join_room
from models.database import db
import urllib3

urllib3.disable_warnings()

logger = logging.getLogger(__name__)

DERIV_API = "https://165.227.79.199"
DERIV_HOST = "api.deriv.com"


# =============================
# ENCRYPTION
# =============================
def get_encryption_key():
    from flask import current_app
    key = current_app.config.get("ENCRYPTION_KEY")
    return key.encode() if isinstance(key, str) else key


def encrypt_token(token):
    return Fernet(get_encryption_key()).encrypt(token.encode()).decode()


def decrypt_token(token):
    return Fernet(get_encryption_key()).decrypt(token.encode()).decode()


# =============================
# REST
# =============================
def get_deriv_accounts(token):
    try:
        url = f"{DERIV_API}/trading/v1/options/accounts"

        headers = {
            "Authorization": f"Bearer {token}",
            "Host": DERIV_HOST
        }

        r = requests.get(url, headers=headers, timeout=10, verify=False)

        if r.status_code != 200:
            logger.error(f"Deriv error: {r.text}")
            return None

        data = r.json()
        return data.get("data", [])

    except Exception as e:
        logger.error(f"get_deriv_accounts error: {e}")
        return None


def request_otp(token, account_id):
    try:
        url = f"{DERIV_API}/trading/v1/options/accounts/{account_id}/otp"

        headers = {
            "Authorization": f"Bearer {token}",
            "Host": DERIV_HOST
        }

        r = requests.get(url, headers=headers, timeout=10, verify=False)

        if r.status_code != 200:
            logger.error(f"OTP error: {r.text}")
            return None

        return r.json().get("data", {}).get("ws_url")

    except Exception as e:
        logger.error(f"request_otp error: {e}")
        return None


def validate_deriv_token(token):
    accounts = get_deriv_accounts(token)

    if not accounts:
        return {"success": False, "error": "Invalid token"}

    active = next((a for a in accounts if a.get("status") == "active"), accounts[0])

    return {
        "success": True,
        "account_id": active["account_id"],
        "currency": active["currency"],
        "balance": float(active["balance"]),
        "accounts": accounts
    }


# =============================
# WEBSOCKET
# =============================
class DerivConnection:
    def __init__(self, user_id, token, socketio=None):
        self.user_id = user_id
        self.token = token
        self.socketio = socketio

        self.ws = None
        self.connected = False
        self.balance = 0
        self.account_id = None
        self.should_run = False

    def connect(self):
        accounts = get_deriv_accounts(self.token)
        if not accounts:
            logger.error("No accounts found")
            return

        acc = next((a for a in accounts if a.get("status") == "active"), accounts[0])

        self.account_id = acc["account_id"]
        self.balance = float(acc["balance"])

        ws_url = request_otp(self.token, self.account_id)
        if not ws_url:
            logger.error("OTP failed")
            return

        self.should_run = True

        def on_open(ws):
            self.connected = True
            logger.info("WS connected")
            self.subscribe()

        def on_message(ws, message):
            data = json.loads(message)

            if "balance" in data:
                new_balance = data["balance"]["balance"]

                if new_balance != self.balance:
                    self.balance = new_balance

                    if self.socketio:
                        self.socketio.emit(
                            "deriv_balance_update",
                            {"balance": self.balance},
                            room=f"user_{self.user_id}"
                        )

        def on_close(ws, *args):
            self.connected = False
            logger.warning("WS closed")

            if self.should_run:
                time.sleep(3)
                self.connect()

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close
        )

        threading.Thread(target=self.ws.run_forever, daemon=True).start()

    def subscribe(self):
        self.send({"balance": 1, "subscribe": 1})

    def send(self, payload):
        if self.ws and self.connected:
            self.ws.send(json.dumps(payload))

    def disconnect(self):
        self.should_run = False
        if self.ws:
            self.ws.close()


# =============================
# MANAGER
# =============================
class DerivConnectionManager:
    def __init__(self):
        self.connections = {}
        self.socketio = None

    def init_socketio(self, socketio):
        self.socketio = socketio

        @socketio.on("join")
        def join(data):
            join_room(f"user_{data['user_id']}")

    def create(self, user_id, token):
        conn = DerivConnection(user_id, token, self.socketio)
        self.connections[user_id] = conn
        conn.connect()
        return conn

    def get(self, user_id):
        return self.connections.get(user_id)

    def remove(self, user_id):
        if user_id in self.connections:
            self.connections[user_id].disconnect()
            del self.connections[user_id]


connection_manager = DerivConnectionManager()


# =============================
# EXPORTS
# =============================
def init_socketio(socketio):
    connection_manager.init_socketio(socketio)
    return socketio


def cleanup_all_connections():
    for uid in list(connection_manager.connections.keys()):
        connection_manager.remove(uid)


# =============================
# API FUNCTIONS
# =============================
def connect_deriv_account(user_id, token):
    validation = validate_deriv_token(token)

    if not validation["success"]:
        return validation

    encrypted = encrypt_token(token)

    db.save_deriv_token(
        user_id=user_id,
        api_token=encrypted,
        account_id=validation["account_id"],
        currency=validation["currency"],
        balance=validation["balance"]
    )

    connection_manager.remove(user_id)
    connection_manager.create(user_id, token)

    return {"success": True, "data": validation}


def disconnect_deriv_account(user_id):
    connection_manager.remove(user_id)
    db.disconnect_deriv(user_id)
    return {"success": True}


def get_deriv_balance(user_id):
    conn = connection_manager.get(user_id)
    return {"success": True, "balance": conn.balance if conn else 0}


def get_connection_status(user_id):
    conn = connection_manager.get(user_id)
    return {"connected": conn.connected if conn else False}