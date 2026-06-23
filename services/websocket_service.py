# backend/services/websocket_service.py

from typing import Dict, Set
from flask_socketio import SocketIO, emit
from services.deriv_service import deriv_service

# Global SocketIO instance
socketio = None

class WebSocketService:
    """Service for managing WebSocket connections and broadcasts - Real connections only"""
    
    def __init__(self):
        self.connected_clients = set()
        self.client_subscriptions = {}  # client_id -> set of symbols
    
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
        
        # Send current data for this symbol if available
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
            for client_id, symbols in self.client_subscriptions.items():
                if symbol in symbols:
                    socketio.emit(event, data, room=client_id)
    
    def broadcast_to_all(self, event, data):
        """Broadcast to all connected clients"""
        if socketio:
            socketio.emit(event, data)
    
    def get_all_market_data(self):
        """Get all market data from deriv_service"""
        return deriv_service.get_all_market_data()
    
    def broadcast_price_update(self, symbol: str, data: Dict):
        """Broadcast a price update for a specific symbol"""
        if socketio:
            self.broadcast_to_symbol(symbol, 'price_update', {
                'symbol': symbol,
                'data': data
            })
    
    def broadcast_initial_data(self, client_id: str, data: Dict):
        """Send initial market data to a new client"""
        if socketio and client_id in self.connected_clients:
            socketio.emit('initial_data', {
                'data': data
            }, room=client_id)

# Singleton instance
websocket_service = WebSocketService()