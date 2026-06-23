# backend/services/websocket_service.py

import threading
import time
from typing import Dict, Set
from flask_socketio import SocketIO, emit, join_room, leave_room
from services.deriv_service import deriv_service

# Global SocketIO instance
socketio = None

class WebSocketService:
    """Service for managing WebSocket connections and broadcasts"""
    
    def __init__(self):
        self.connected_clients = set()
        self.client_subscriptions = {}  # client_id -> set of symbols
        self.update_thread = None
        self.running = False
    
    def init_app(self, app):
        """Initialize SocketIO with Flask app"""
        global socketio
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
        return socketio
    
    def register_client(self, client_id):
        """Register a new client connection"""
        self.connected_clients.add(client_id)
        if client_id not in self.client_subscriptions:
            self.client_subscriptions[client_id] = set()
        return True
    
    def unregister_client(self, client_id):
        """Unregister a client connection"""
        if client_id in self.connected_clients:
            self.connected_clients.remove(client_id)
        if client_id in self.client_subscriptions:
            del self.client_subscriptions[client_id]
        return True
    
    def subscribe(self, client_id, symbol):
        """Subscribe a client to a symbol"""
        if client_id not in self.client_subscriptions:
            self.client_subscriptions[client_id] = set()
        self.client_subscriptions[client_id].add(symbol)
        
        # Send initial data for this symbol
        data = deriv_service.get_market_data(symbol)
        if data and socketio:
            socketio.emit('market_update', {
                'symbol': symbol,
                'data': data
            }, room=client_id)
        
        return True
    
    def unsubscribe(self, client_id, symbol):
        """Unsubscribe a client from a symbol"""
        if client_id in self.client_subscriptions:
            self.client_subscriptions[client_id].discard(symbol)
        return True
    
    def broadcast_to_client(self, client_id, event, data):
        """Send event to a specific client"""
        if socketio and client_id in self.connected_clients:
            socketio.emit(event, data, room=client_id)
    
    def broadcast_to_symbol(self, symbol, event, data):
        """Broadcast to all clients subscribed to a symbol"""
        if socketio:
            # Find clients subscribed to this symbol
            for client_id, symbols in self.client_subscriptions.items():
                if symbol in symbols:
                    socketio.emit(event, data, room=client_id)
    
    def broadcast_to_all(self, event, data):
        """Broadcast to all connected clients"""
        if socketio:
            socketio.emit(event, data)
    
    def start_price_updates(self):
        """Start background thread for price updates"""
        if self.running:
            return
        
        self.running = True
        self.update_thread = threading.Thread(target=self._price_update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def _price_update_loop(self):
        """Background loop for price updates"""
        last_update_1s = time.time()
        last_update_10s = time.time()
        
        while self.running:
            current_time = time.time()
            
            # Update 1-second markets every second
            if current_time - last_update_1s >= 1:
                # Update 1-second markets
                for market in deriv_service.volatility_markets:
                    if market['isOneSec']:
                        deriv_service.update_market(market['symbol'])
                
                # Broadcast all updates
                updated_data = deriv_service.get_all_market_data()
                self.broadcast_to_all('price_update', {
                    'data': updated_data
                })
                
                last_update_1s = current_time
            
            # Update 10-second markets every 2 seconds
            if current_time - last_update_10s >= 2:
                # Update non-1s markets
                for market in deriv_service.volatility_markets:
                    if not market['isOneSec']:
                        deriv_service.update_market(market['symbol'])
                
                # Broadcast all updates
                updated_data = deriv_service.get_all_market_data()
                self.broadcast_to_all('price_update', {
                    'data': updated_data
                })
                
                last_update_10s = current_time
            
            time.sleep(0.1)  # Prevent CPU overload
    
    def stop_price_updates(self):
        """Stop the price update thread"""
        self.running = False

# Singleton instance
websocket_service = WebSocketService()