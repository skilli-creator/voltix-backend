# backend/app.py
import socket
import os
import time
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config, config

# Routes
from routes.auth_routes import auth_bp
from routes.deriv_routes import deriv_bp

# Services
from services.deriv_service import init_socketio, cleanup_all_connections
from services.email_service import EmailService

# ============================================
# LOAD CONFIG
# ============================================
env = os.getenv('ENVIRONMENT', 'development')
app_config = config.get(env, config['default'])

Config.validate()

# ============================================
# LOGGING
# ============================================
log_level = getattr(logging, app_config.LOG_LEVEL.upper(), logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# DNS TEST
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

if app_config.DEBUG:
    test_dns()

# ============================================
# CONFIGURATION
# ============================================
app.config['SECRET_KEY'] = app_config.SECRET_KEY
app.config['JWT_SECRET_KEY'] = app_config.JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = app_config.JWT_ACCESS_TOKEN_EXPIRES

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = not app_config.DEBUG
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = "None" if not app_config.DEBUG else "Lax"
app.config['PERMANENT_SESSION_LIFETIME'] = 600

# ============================================
# CORS CONFIG
# ============================================
CORS(
    app,
    supports_credentials=True,
    origins=app_config.CORS_ORIGINS
)

# ============================================
# EXTENSIONS
# ============================================
jwt = JWTManager(app)

# ============================================
# JWT ERROR HANDLERS
# ============================================
@jwt.unauthorized_loader
def unauthorized_response(callback):
    return jsonify({
        'success': False,
        'message': 'Missing or invalid authorization token'
    }), 401

@jwt.invalid_token_loader
def invalid_token_response(callback):
    return jsonify({
        'success': False,
        'message': 'Invalid token'
    }), 401

@jwt.expired_token_loader
def expired_token_response(callback):
    return jsonify({
        'success': False,
        'message': 'Token has expired'
    }), 401

# ============================================
# SECURITY HEADERS
# ============================================
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# ============================================
# REQUEST LOGGING
# ============================================
@app.before_request
def log_request():
    logger.info(f"{request.method} {request.path}")

# ============================================
# INITIALIZE RESEND EMAIL
# ============================================
try:
    EmailService.init_resend()
    logger.info("✅ Email service initialized")
except Exception as e:
    logger.warning(f"⚠️ Email init failed: {e}")

# ============================================
# BLUEPRINTS
# ============================================
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(deriv_bp, url_prefix='/api/deriv')

try:
    from routes.bot_routes import bot_bp
    app.register_blueprint(bot_bp, url_prefix='/api/bot')
except ImportError:
    logger.warning("⚠️ bot_routes not found, skipping registration")

# ============================================
# SOCKET.IO
# ============================================
from flask_socketio import SocketIO

socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')
init_socketio(socketio)

# ============================================
# HEALTH ROUTES
# ============================================
@app.route('/')
def home():
    return jsonify({
        'message': 'Voltix API Running',
        'status': 'online',
        'websocket': 'Enabled',
        'environment': app_config.ENVIRONMENT,
        'deriv_app_id': app_config.DERIV_APP_ID
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time() * 1000),
        'environment': app_config.ENVIRONMENT,
        'deriv_app_id': app_config.DERIV_APP_ID
    })

# ============================================
# ERROR HANDLERS
# ============================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Route not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal server error: {error}')
    return jsonify({
        'success': False,
        'message': 'Internal server error'
    }), 500

# ============================================
# SHUTDOWN HANDLER
# ============================================
import atexit

@atexit.register
def shutdown():
    logger.info("🧹 Cleaning up connections on shutdown...")
    cleanup_all_connections()

# ============================================
# RUN SERVER
# ============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    print("🚀 Starting Voltix Traders Backend...")
    print("🌐 WebSocket enabled on /socket.io/")
    print(f"📍 Server running on http://localhost:{port}")
    print(f"📡 Environment: {app_config.ENVIRONMENT}")
    print(f"🔑 Deriv App ID: {app_config.DERIV_APP_ID}")
    print(f"🐛 Debug mode: {app_config.DEBUG}")
    print(f"📊 Log level: {app_config.LOG_LEVEL}")
    print("📡 Waiting for connections...")

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=app_config.DEBUG,
        allow_unsafe_werkzeug=app_config.DEBUG
    )