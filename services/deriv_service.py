# backend/services/deriv_service.py

import websocket
import json
import threading
import time
from typing import Dict, List, Optional

class DerivService:
    """Complete Deriv service with WebSocket connection and market data management"""
    
    # CORRECT Deriv WebSocket URL
    DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3"
    DERIV_APP_ID = "1089"  # Demo App ID
    
    def __init__(self):
        self.market_data = {}
        self.volatility_markets = self._get_volatility_markets()
    
    # ==================== MARKET DATA ====================
    
    def _get_volatility_markets(self):
        """Define all volatility markets available"""
        return [
            {'symbol': 'R_100_1S', 'name': 'Volatility 100 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_10_1S', 'name': 'Volatility 10 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_25_1S', 'name': 'Volatility 25 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_50_1S', 'name': 'Volatility 50 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_75_1S', 'name': 'Volatility 75 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_10', 'name': 'Volatility 10 Index', 'isOneSec': False},
            {'symbol': 'R_25', 'name': 'Volatility 25 Index', 'isOneSec': False},
            {'symbol': 'R_50', 'name': 'Volatility 50 Index', 'isOneSec': False},
            {'symbol': 'R_75', 'name': 'Volatility 75 Index', 'isOneSec': False},
            {'symbol': 'R_100', 'name': 'Volatility 100 Index', 'isOneSec': False},
        ]
    
    def set_market_data(self, symbol: str, data: Dict) -> bool:
        """Set market data for a symbol"""
        self.market_data[symbol] = data
        return True
    
    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get data for a specific market"""
        return self.market_data.get(symbol)
    
    def get_all_market_data(self) -> Dict:
        """Get all market data"""
        return self.market_data
    
    def get_markets_list(self) -> List[Dict]:
        """Get list of available markets"""
        return self.volatility_markets
    
    def update_market_data(self, symbol: str, new_data: Dict) -> bool:
        """Update market data with real data from Deriv"""
        if symbol in self.market_data:
            self.market_data[symbol] = new_data
            return True
        return False
    
    def clear_all_market_data(self):
        """Clear all market data"""
        self.market_data.clear()
    
    def remove_market_data(self, symbol: str) -> bool:
        """Remove data for a specific market"""
        if symbol in self.market_data:
            del self.market_data[symbol]
            return True
        return False
    
    def get_market_history(self, symbol: str, limit: int = 150) -> Optional[List[Dict]]:
        """Get historical ticks for a market"""
        data = self.market_data.get(symbol)
        if not data:
            return None
        return data.get('ticks', [])[-limit:]
    
    # ==================== WEBSOCKET HELPERS ====================
    
    @staticmethod
    def _get_ws_url():
        """Get WebSocket URL with App ID"""
        return f"{DerivService.DERIV_WS_URL}?app_id={DerivService.DERIV_APP_ID}"
    
    @staticmethod
    def _close_ws_safely(ws):
        """Safely close WebSocket"""
        try:
            ws.close()
        except:
            pass
    
    # ==================== CONNECTION TEST ====================
    
    @staticmethod
    def test_connection(api_token):
        """Test if the API token is valid using WebSocket"""
        result = {"success": False, "data": None, "error": None}
        response_received = threading.Event()
        
        def on_message(ws, message):
            data = json.loads(message)
            print(f"📨 Response: {data}")
            
            if data.get('authorize'):
                result["success"] = True
                result["data"] = data['authorize']
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('error'):
                result["error"] = data['error']['message']
                response_received.set()
                DerivService._close_ws_safely(ws)
            # Also handle success response format: { "code": 0, "msg": "authorize" }
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                result["success"] = True
                result["data"] = {"msg": "authorize", "code": 0}
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            print(f"❌ WebSocket error: {error}")
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws_url = DerivService._get_ws_url()
            print(f"🔌 WebSocket connected to {ws_url}")
            print(f"🔑 Authorizing with token: {api_token[:20]}...")
            ws.send(json.dumps({"authorize": api_token}))
        
        def on_close(ws, close_status_code, close_msg):
            print(f"🔌 WebSocket closed: {close_status_code} - {close_msg}")
        
        ws_url = DerivService._get_ws_url()
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
        
        response_received.wait(timeout=10)
        
        if result["success"]:
            print(f"✅ Authorization successful!")
            return True, result["data"]
        else:
            print(f"❌ Authorization failed: {result['error']}")
            return False, result["error"] or "Connection failed"
    
    # ==================== ACCOUNT INFO ====================
    
    @staticmethod
    def get_account_info(api_token):
        """Get account information using WebSocket - returns authorized account info directly"""
        result = {"success": False, "info": None, "error": None}
        response_received = threading.Event()
        
        def on_message(ws, message):
            data = json.loads(message)
            print(f"📨 Account Info Response: {data}")
            
            if data.get('authorize'):
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
            elif data.get('error'):
                result["error"] = data['error']['message']
                response_received.set()
                DerivService._close_ws_safely(ws)
            # Also handle success response format
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                # The authorize data comes in a separate message
                # We'll wait for the next message with the actual data
                pass
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws_url = DerivService._get_ws_url()
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=10)
        
        if result["success"]:
            return True, result["info"]
        else:
            return False, result["error"] or "Failed to get account info"
    
    # ==================== BALANCE ====================
    
    @staticmethod
    def get_balance(api_token):
        """Get account balance using WebSocket - uses authorized account directly (NO switching)"""
        result = {"success": False, "balance": None, "currency": None, "error": None, "loginid": None}
        response_received = threading.Event()
        
        def on_message(ws, message):
            data = json.loads(message)
            print(f"📨 Balance Response: {data}")
            
            if data.get('authorize'):
                # After authorization, directly get balance (NO switch_account)
                ws.send(json.dumps({"balance": 1}))
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                # Authorization successful, request balance
                ws.send(json.dumps({"balance": 1}))
            elif data.get('balance'):
                result["success"] = True
                result["balance"] = data['balance']['balance']
                result["currency"] = data['balance']['currency']
                result["loginid"] = data['balance']['loginid']
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('error'):
                result["error"] = data['error']['message']
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws_url = DerivService._get_ws_url()
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=15)
        
        if result["success"]:
            return True, result["balance"], result["currency"], result["loginid"]
        else:
            return False, result["error"] or "Failed to get balance", None, None
    
    # ==================== PLACE TRADE ====================
    
    @staticmethod
    def place_trade(api_token, symbol, trade_type, amount, duration, duration_unit='t'):
        """Place a binary option trade on Deriv using WebSocket - uses authorized account directly"""
        result = {"success": False, "trade": None, "error": None}
        response_received = threading.Event()
        proposal_id = None
        authorized = False
        
        def on_message(ws, message):
            nonlocal proposal_id, authorized
            data = json.loads(message)
            print(f"📨 Trade Response: {data}")
            
            if data.get('authorize'):
                authorized = True
                # After authorization, directly send proposal (NO switch_account)
                ws.send(json.dumps({
                    "proposal": 1,
                    "amount": amount,
                    "basis": "stake",
                    "contract_type": trade_type,
                    "currency": "USD",
                    "duration": duration,
                    "duration_unit": duration_unit,
                    "symbol": symbol
                }))
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                authorized = True
                ws.send(json.dumps({
                    "proposal": 1,
                    "amount": amount,
                    "basis": "stake",
                    "contract_type": trade_type,
                    "currency": "USD",
                    "duration": duration,
                    "duration_unit": duration_unit,
                    "symbol": symbol
                }))
            elif data.get('proposal'):
                proposal_id = data['proposal']['id']
                print(f"📊 Proposal received! ID: {proposal_id}")
                ws.send(json.dumps({
                    "buy": proposal_id,
                    "price": amount
                }))
            elif data.get('buy'):
                result["success"] = True
                result["trade"] = {
                    'contract_id': data['buy']['contract_id'],
                    'buy_price': data['buy']['buy_price'],
                    'longcode': data['buy'].get('longcode', '')
                }
                print(f"✅ Trade placed! Contract ID: {result['trade']['contract_id']}")
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('error'):
                result["error"] = data['error']['message']
                print(f"❌ Error: {result['error']}")
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws_url = DerivService._get_ws_url()
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=30)
        
        if result["success"]:
            return True, result["trade"]
        else:
            return False, result["error"] or "Failed to place trade"
    
    # ==================== ACTIVE CONTRACTS ====================
    
    @staticmethod
    def get_active_contracts(api_token):
        """Get all active contracts for the account - uses authorized account directly"""
        result = {"success": False, "contracts": [], "error": None}
        response_received = threading.Event()
        authorized = False
        
        def on_message(ws, message):
            nonlocal authorized
            data = json.loads(message)
            print(f"📨 Active Contracts Response: {data}")
            
            if data.get('authorize'):
                authorized = True
                ws.send(json.dumps({"portfolio": 1}))
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                authorized = True
                ws.send(json.dumps({"portfolio": 1}))
            elif data.get('portfolio'):
                contracts = []
                for contract in data['portfolio'].get('contracts', []):
                    contracts.append({
                        'contract_id': contract['contract_id'],
                        'symbol': contract.get('symbol', ''),
                        'buy_price': contract.get('buy_price', 0),
                        'payout': contract.get('payout', 0),
                        'expiry_time': contract.get('expiry_time'),
                        'status': contract.get('status', 'open')
                    })
                result["success"] = True
                result["contracts"] = contracts
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('error'):
                result["error"] = data['error']['message']
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws_url = DerivService._get_ws_url()
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=10)
        
        if result["success"]:
            return True, result["contracts"]
        else:
            return False, result["error"] or "Failed to get active contracts"
    
    # ==================== TRADE HISTORY ====================
    
    @staticmethod
    def get_trade_history(api_token, limit=50):
        """Get trade history from Deriv API - uses authorized account directly"""
        result = {"success": False, "history": [], "error": None}
        response_received = threading.Event()
        authorized = False
        
        def on_message(ws, message):
            nonlocal authorized
            data = json.loads(message)
            print(f"📨 Trade History Response: {data}")
            
            if data.get('authorize'):
                authorized = True
                ws.send(json.dumps({"profit_table": 1, "limit": limit}))
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                authorized = True
                ws.send(json.dumps({"profit_table": 1, "limit": limit}))
            elif data.get('profit_table'):
                transactions = []
                for transaction in data['profit_table'].get('transactions', []):
                    buy_price = transaction.get('buy_price', 0)
                    sell_price = transaction.get('sell_price', 0)
                    profit = sell_price - buy_price if sell_price and buy_price else transaction.get('profit_loss', 0)
                    
                    transactions.append({
                        'contract_id': transaction.get('contract_id'),
                        'transaction_id': transaction.get('transaction_id'),
                        'action': transaction.get('action'),
                        'amount': transaction.get('amount'),
                        'balance_after': transaction.get('balance_after'),
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'profit': profit,
                        'payout': transaction.get('payout'),
                        'transaction_time': transaction.get('transaction_time'),
                        'status': transaction.get('status'),
                        'symbol': transaction.get('symbol'),
                        'contract_type': transaction.get('contract_type'),
                        'start_time': transaction.get('start_time'),
                        'exit_time': transaction.get('exit_time')
                    })
                result["success"] = True
                result["history"] = transactions
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('error'):
                result["error"] = data['error']['message']
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws_url = DerivService._get_ws_url()
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=15)
        
        if result["success"]:
            return True, result["history"]
        else:
            return False, result["error"] or "Failed to get trade history"
    
    # ==================== CONTRACT INFO ====================
    
    @staticmethod
    def get_contract_info(api_token, contract_id):
        """Get information about a specific contract - uses authorized account directly"""
        result = {"success": False, "info": None, "error": None}
        response_received = threading.Event()
        authorized = False
        
        def on_message(ws, message):
            nonlocal authorized
            data = json.loads(message)
            print(f"📨 Contract Info Response: {data}")
            
            if data.get('authorize'):
                authorized = True
                ws.send(json.dumps({"proposal_open_contract": contract_id}))
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                authorized = True
                ws.send(json.dumps({"proposal_open_contract": contract_id}))
            elif data.get('proposal_open_contract'):
                contract = data['proposal_open_contract']
                result["success"] = True
                result["info"] = {
                    'contract_id': contract.get('contract_id'),
                    'status': contract.get('status'),
                    'buy_price': contract.get('buy_price'),
                    'sell_price': contract.get('sell_price'),
                    'profit': contract.get('profit', 0),
                    'payout': contract.get('payout', 0),
                    'expiry_time': contract.get('expiry_time'),
                    'symbol': contract.get('underlying'),
                    'transaction_ids': contract.get('transaction_ids', [])
                }
                response_received.set()
                DerivService._close_ws_safely(ws)
            elif data.get('error'):
                result["error"] = data['error']['message']
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws_url = DerivService._get_ws_url()
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=30)
        
        if result["success"]:
            return True, result["info"]
        else:
            return False, result["error"] or "Failed to get contract info"
    
    # ==================== GET TICKS (REAL-TIME DATA) ====================
    
    @staticmethod
    def get_ticks(api_token, symbol, count=10):
        """Get real-time ticks for a symbol"""
        result = {"success": False, "ticks": [], "error": None}
        response_received = threading.Event()
        authorized = False
        ticks_received = False
        
        def on_message(ws, message):
            nonlocal authorized, ticks_received
            data = json.loads(message)
            print(f"📨 Ticks Response: {data}")
            
            if data.get('authorize'):
                authorized = True
                ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))
            elif data.get('code') == 0 and data.get('msg') == 'authorize':
                authorized = True
                ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))
            elif data.get('tick'):
                # Collect ticks
                tick_data = data['tick']
                result["ticks"].append({
                    'price': tick_data['quote'],
                    'time': tick_data['epoch'],
                    'symbol': tick_data['symbol']
                })
                ticks_received = True
                if len(result["ticks"]) >= count:
                    result["success"] = True
                    response_received.set()
                    DerivService._close_ws_safely(ws)
            elif data.get('error'):
                result["error"] = data['error']['message']
                response_received.set()
                DerivService._close_ws_safely(ws)
        
        def on_error(ws, error):
            result["error"] = str(error)
            response_received.set()
        
        def on_open(ws):
            ws.send(json.dumps({"authorize": api_token}))
        
        ws_url = DerivService._get_ws_url()
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        response_received.wait(timeout=15)
        
        if result["success"]:
            return True, result["ticks"]
        else:
            return False, result["error"] or "Failed to get ticks"


# ============================================
# ✅ SINGLETON INSTANCE
# ============================================

deriv_service = DerivService()