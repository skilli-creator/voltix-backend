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

# Disable SSL warnings (needed for IP workaround)
urllib3.disable_warnings()

logger = logging.getLogger(__name__)

# 🔴 Use direct IP to avoid Render DNS issues
DERIV_API_IP = "https://165.227.79.199"
DERIV_HOST = "api.deriv.com"


# =============================
# ENCRYPTION
# =============================
def get_encryption_key():
    from flask import current_app
    key = current_app.config.get("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY missing")
    return key.encode() if isinstance(key, str) else key


def encrypt_token(token):
    return Fernet(get_encryption_key()).encrypt(token.encode()).decode()


def decrypt_token(token):
    return Fernet(get_encryption_key()).decrypt(token.encode()).decode()


# =============================
# REST (FIXED - uses IP + Host header)
# =============================
def get_deriv_accounts(token):
    try:
        url = f"{DERIV_API_IP}/trading/v1/options/accounts"

        headers = {
            "Authorization": f"Bearer {token}",
            "Host": DERIV_HOST
        }

        r = requests.get(url, headers=headers, timeout=10, verify=False)

        if r.status_code != 200:
            logger.error(f"Accounts fetch failed: {r.status_code} {r.text}")
            return None

        return r.json().get("data", [])

    except Exception as e:
        logger.error(f"get_deriv_accounts error: {e}")
        return None


def request_otp(token, account_id):
    try:
        url = f"{DERIV_API_IP}/trading/v1/options/accounts/{account_id}/otp"

        headers = {
            "Authorization": f"Bearer {token}",
            "Host": DERIV_HOST
        }

        r = requests.get(url, headers=headers, timeout=10, verify=False)

        if r.status_code != 200:
            logger.error(f"OTP request failed: {r.status_code} {r.text}")
            return None

        return r.json().get("data", {}).get("ws_url")

    except Exception as e:
        logger.error(f"request_otp error: {e}")
        return None


def validate_deriv_token(token):
    accs = get_deriv_accounts(token)

    if not accs:
        return {"success": False, "error": "Invalid token or network error"}

    acc = next((a for a in accs if a.get("status") == "active"), accs[0])

    return {
        "success": True,
        "account_id": acc.get("account_id"),
        "currency": acc.get("currency", "USD"),
        "balance": float(acc.get("balance", 0)),
        "accounts": accs
    }


# =============================
# CONNECTION (OTP ONLY - NO AUTHORIZE)
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
        self.currency = "USD"
        self.should_run = False

    def connect(self):
        logger.info("Connecting to Deriv...")

        accounts = get_deriv_accounts(self.token)
        if not accounts:
            logger.error("No accounts found")
            return

        acc = next((a for a in accounts if a.get("status") == "active"), accounts[0])
        self.account_id = acc.get("account_id")
        self.currency = acc.get("currency", "USD")
        self.balance = float(acc.get("balance", 0))

        ws_url = request_otp(self.token, self.account_id)
        if not ws_url:
            logger.error("Failed to get OTP")
            return

        self.should_run = True

        def on_open(ws):
            self.connected = True
            logger.info("WS connected (OTP session)")
            self.subscribe()

        def on_message(ws, message):
            try:
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

                if "error" in data:
                    logger.warning(f"WS error: {data['error']}")

            except Exception as e:
                logger.error(f"WS message error: {e}")

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
        self.send({"transaction": 1, "subscribe": 1})

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
    val = validate_deriv_token(token)

    if not val.get("success"):
        return val

    enc = encrypt_token(token)

    # ⚠️ make sure your DB uses "api_token"
    db.save_deriv_token(
        user_id=user_id,
        api_token=enc,
        account_id=val["account_id"],
        currency=val["currency"],
        balance=val["balance"]
    )

    connection_manager.remove(user_id)
    connection_manager.create(user_id, token)

    return {"success": True, "data": val}


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