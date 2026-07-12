# backend/services/deriv_service.py

import websocket
import json
import threading
import requests
from config import Config

class DerivService:
    
    # ✅ NEWER OTP-BASED WebSocket Method (Handles both Demo & Real)
    DERIV_OTP_URL = "https://api.derivws.com/trading/v1/options/accounts"
    
    @staticmethod
    def _get_otp_ws_url(account_id, api_token=None):
        """
        Get WebSocket URL with OTP (new secure method)
        Handles both demo and real accounts
        """
        try:
            headers = {}
            if api_token:
                headers['Authorization'] = f'Bearer {api_token}'
            
            response = requests.post(
                f"{DerivService.DERIV_OTP_URL}/{account_id}/otp",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                ws_url = data.get('url')
                if ws_url:
                    print(f"🔌 OTP WebSocket URL obtained: {ws_url[:50]}...")
                    return ws_url
                else:
                    print(f"⚠️ No URL in OTP response: {data}")
                    return None
            else:
                print(f"⚠️ OTP request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"⚠️ OTP error: {e}")
            return None
    
    @staticmethod
    def _close_ws_safely(ws):
        """Safely close WebSocket"""
        try:
            ws.close()
        except:
            pass
    
    # ==================== CONNECTION TEST (OTP Method - NEW) ====================
    
    @staticmethod
    def test_connection(api_token, account_id=None):
        """
        Test connection using OTP method (new secure method)
        Handles both demo and real accounts
        
        Args:
            api_token: The Deriv API token
            account_id: Optional - if not provided, will try to get from token
        """
        result = {"success": False, "data": None, "error": None}
        response_received = threading.Event()
        
        # If account_id not provided, we need to get it first
        # For demo accounts, we can use a default or get from token
        if not account_id:
            # Try to get account_id from the token via a quick connection
            account_id = DerivService._get_account_id_from_token(api_token)
            if not account_id:
                return False, "Could not determine account ID. Please provide account_id."
        
        # Get OTP URL
        ws_url = DerivService._get_otp_ws_url(account_id, api_token)
        if not ws_url:
            return False, "Failed to get OTP URL. Please check your account_id and token."
        
        def on_message(ws, message):
            data = json.loads(message)
            print(f"📨 Response: {data}")
            
            # Check for authorization success
            if data.get('authorize'):
                result["success"] = True
                result["data"] = data['authorize']
                response_received.set()
                DerivService._close_ws_safely(ws)
            # Check for success format { "code": 0, "msg": "authorize" }
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                result["success"] = True
                result["data"] = {"msg": "authorize", "code": 0}
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('error'):
                result["error"] = data['error'].get('message', 'Unknown error')
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            print(f"❌ WebSocket error: {error}")
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            print(f"🔌 WebSocket connected via OTP")
            print(f"🔑 Authorizing with token: {api_token[:20]}...")
            ws.send(json.dumps({"authorize": api_token}))
        
        def on_close(ws, close_status_code, close_msg):
            print(f"🔌 WebSocket closed: {close_status_code} - {close_msg}")
        
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=15)
        
        if result["success"]:
            print(f"✅ Authorization successful (OTP method)!")
            return True, result["data"]
        else:
            print(f"❌ Authorization failed (OTP method): {result['error']}")
            return False, result["error"] or "Connection failed"
    
    # ==================== GET ACCOUNT ID FROM TOKEN ====================
    
    @staticmethod
    def _get_account_id_from_token(api_token):
        """
        Get account_id from the token by making a quick connection
        """
        result = {"account_id": None, "error": None}
        response_received = threading.Event()
        ws_url = "wss://ws.derivws.com/websockets/v3?app_id=1089"
        
        def on_message(ws, message):
            data = json.loads(message)
            print(f"📨 Account ID Response: {data}")
            
            if data.get('authorize'):
                result["account_id"] = data['authorize'].get('loginid')
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                # Wait for the next message with account data
                pass
            elif data.get('error'):
                result["error"] = data['error'].get('message', 'Unknown error')
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error
        )
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=10)
        
        if result["account_id"]:
            print(f"✅ Account ID retrieved: {result['account_id']}")
            return result["account_id"]
        else:
            print(f"❌ Failed to get account ID: {result['error']}")
            return None
    
    # ==================== ACCOUNT INFO ====================
    
    @staticmethod
    def get_account_info(api_token, account_id=None):
        """Get account information using OTP WebSocket"""
        result = {"success": False, "info": None, "error": None}
        response_received = threading.Event()
        authorized = False
        
        if not account_id:
            account_id = DerivService._get_account_id_from_token(api_token)
            if not account_id:
                return False, "Could not determine account ID"
        
        ws_url = DerivService._get_otp_ws_url(account_id, api_token)
        if not ws_url:
            return False, "Failed to get OTP URL"
        
        def on_message(ws, message):
            nonlocal authorized
            data = json.loads(message)
            print(f"📨 Account Info Response: {data}")
            
            if data.get('authorize'):
                authorized = True
                authorize_data = data['authorize']
                result["success"] = True
                result["info"] = {
                    'account_id': authorize_data.get('loginid', ''),
                    'currency': authorize_data.get('currency', 'USD'),
                    'account_type': 'Demo' if authorize_data.get('is_virtual') else 'Real',
                    'email': authorize_data.get('email', ''),
                    'balance': authorize_data.get('balance', 0),
                    'fullname': authorize_data.get('fullname', '')
                }
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                authorized = True
            elif data.get('error'):
                result["error"] = data['error'].get('message', 'Unknown error')
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=15)
        
        if result["success"]:
            return True, result["info"]
        else:
            return False, result["error"] or "Failed to get account info"
    
    # ==================== BALANCE ====================
    
    @staticmethod
    def get_balance(api_token, account_id=None):
        """Get account balance using OTP WebSocket"""
        result = {"success": False, "balance": None, "currency": None, "error": None, "loginid": None}
        response_received = threading.Event()
        authorized = False
        
        if not account_id:
            account_id = DerivService._get_account_id_from_token(api_token)
            if not account_id:
                return False, "Could not determine account ID", None, None
        
        ws_url = DerivService._get_otp_ws_url(account_id, api_token)
        if not ws_url:
            return False, "Failed to get OTP URL", None, None
        
        def on_message(ws, message):
            nonlocal authorized
            data = json.loads(message)
            print(f"📨 Balance Response: {data}")
            
            if data.get('authorize'):
                authorized = True
                ws.send(json.dumps({"balance": 1}))
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                authorized = True
                ws.send(json.dumps({"balance": 1}))
            elif data.get('balance'):
                result["success"] = True
                result["balance"] = data['balance']['balance']
                result["currency"] = data['balance']['currency']
                result["loginid"] = data['balance']['loginid']
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('error'):
                result["error"] = data['error'].get('message', 'Unknown error')
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=15)
        
        if result["success"]:
            return True, result["balance"], result["currency"], result["loginid"]
        else:
            return False, result["error"] or "Failed to get balance", None, None


# ============================================
# ✅ SINGLETON INSTANCE
# ============================================

deriv_service = DerivService()