# backend/app.py

import time
import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from routes.auth_routes import auth_bp
from routes.deriv_routes import deriv_bp
from routes.dbot_routes import bot_bp
from services.websocket_service import websocket_service

# Create Flask app
app = Flask(__name__)

# Load configuration
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY

# Initialize extensions
CORS(app)
jwt = JWTManager(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(deriv_bp, url_prefix='/api/deriv')
app.register_blueprint(bot_bp, url_prefix='/api/bot')

# Initialize SocketIO
socketio = websocket_service.init_app(app)

# Register SocketIO event handlers
from routes.deriv_routes import register_socket_handlers
register_socket_handlers()

# Health check routes
@app.route('/')
def home():
    return jsonify({
        'message': 'Voltix API Running 🚀',
        'status': 'online',
        'websocket': 'Enabled',
        'environment': os.environ.get('ENVIRONMENT', 'production')
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time() * 1000),
        'connected_clients': len(websocket_service.connected_clients),
        'active_markets': len(websocket_service.get_all_market_data())
    })

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print("Starting Voltix Traders Backend...")
    print(" WebSocket enabled on /socket.io/")
    print(f" Server running on http://localhost:{port}")
    print(" Waiting for connections...")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )