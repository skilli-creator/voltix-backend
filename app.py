# backend/app.py

import socket
import os
import time
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config

# Routes
from routes.auth_routes import auth_bp
from routes.deriv_routes import deriv_bp
from routes.dbot_routes import bot_bp

# Services
from services.websocket_service import websocket_service
from services.email_service import EmailService


# ============================================
# DNS TEST (ADD THIS)
# ============================================
def test_dns():
    print("\n" + "="*50)
    print("🌐 DNS TEST START")
    print("="*50)
    
    hosts = ["google.com", "api.resend.com", "smtp.gmail.com", "auth.deriv.com"]
    
    for host in hosts:
        try:
            ip = socket.gethostbyname(host)
            print(f"✅ {host} → {ip}")
        except Exception as e:
            print(f"❌ {host} → {e}")
    
    print("="*50)
    print("🌐 DNS TEST END")
    print("="*50 + "\n")


# ============================================
# CREATE APP
# ============================================
app = Flask(__name__)

# Run DNS test on startup
test_dns()


# ============================================
# CONFIGURATION
# ============================================

# Core secrets
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY

# ---- SESSION CONFIG ----
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = True  
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['PERMANENT_SESSION_LIFETIME'] = 600


# ============================================
# CORS CONFIG
# ============================================
CORS(
    app,
    supports_credentials=True,
    origins=[
        "https://voltix-traders.vercel.app"
    ]
)


# ============================================
# EXTENSIONS
# ============================================
jwt = JWTManager(app)


# ============================================
# INITIALIZE RESEND EMAIL
# ============================================
EmailService.init_resend()


# ============================================
# BLUEPRINTS
# ============================================
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(deriv_bp, url_prefix='/api/deriv')
# ❌ REMOVED: deriv_oauth_bp - No longer needed (using manual API token only)
app.register_blueprint(bot_bp, url_prefix='/api/bot')


# ============================================
# SOCKET.IO
# ============================================
socketio = websocket_service.init_app(app)

from routes.deriv_routes import register_socket_handlers
register_socket_handlers()


# ============================================
# HEALTH ROUTES
# ============================================
@app.route('/')
def home():
    return jsonify({
        'message': 'Voltix API Running 🚀',
        'status': 'online',
        'websocket': 'Enabled',
        'environment': os.environ.get('ENVIRONMENT', 'development')
    })


@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time() * 1000),
        'connected_clients': len(websocket_service.connected_clients),
        'active_markets': len(websocket_service.get_all_market_data())
    })


# ============================================
# RUN SERVER
# ============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))

    print("🚀 Starting Voltix Traders Backend...")
    print("🌐 WebSocket enabled on /socket.io/")
    print(f"📍 Server running on http://localhost:{port}")
    print("📡 Waiting for connections...")

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )