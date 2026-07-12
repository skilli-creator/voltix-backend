# backend/config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

class Config:
    # ============================================
    # SECRETS
    # ============================================
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
    
    # ✅ Early validation for critical secrets
    if not SECRET_KEY:
        raise ValueError("❌ SECRET_KEY must be set in .env")
    if not JWT_SECRET_KEY:
        raise ValueError("❌ JWT_SECRET_KEY must be set in .env")
    
    # ============================================
    # DATABASE
    # ============================================
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # ✅ Early validation
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL must be set in .env")
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SSL for Clever Cloud
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'connect_args': {
            "ssl": {}
        }
    }
    
    # ============================================
    # DERIV
    # ============================================
    # ✅ Smart fallback: if non-numeric, use default
    raw_app_id = os.getenv('DERIV_APP_ID')
    if raw_app_id and raw_app_id.isdigit():
        DERIV_APP_ID = raw_app_id
    else:
        DERIV_APP_ID = '1089'  # Safe fallback
    
    DERIV_WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    DERIV_REDIRECT_URI = os.getenv('DERIV_REDIRECT_URI')
    
    # ✅ Early validation
    if not DERIV_REDIRECT_URI:
        raise ValueError("❌ DERIV_REDIRECT_URI must be set in .env")
    
    # ============================================
    # ENCRYPTION
    # ============================================
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    
    # ✅ Early validation
    if not ENCRYPTION_KEY:
        raise ValueError("❌ ENCRYPTION_KEY must be set in .env")
    
    # ============================================
    # FRONTEND
    # ============================================
    FRONTEND_URL = os.getenv('FRONTEND_URL')
    
    # ✅ Early validation
    if not FRONTEND_URL:
        raise ValueError("❌ FRONTEND_URL must be set in .env")
    
    # ============================================
    # CORS - ✅ Safe parsing
    # ============================================
    CORS_ORIGINS = [
        origin.strip() 
        for origin in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',') 
        if origin.strip()
    ]
    
    # ============================================
    # EMAIL
    # ============================================
    RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
    RESEND_FROM_EMAIL = os.getenv('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')
    
    # ============================================
    # ENVIRONMENT & LOGGING
    # ============================================
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    DEBUG = ENVIRONMENT == 'development'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # ============================================
    # VALIDATION - ✅ Runtime check with clear messages
    # ============================================
    @staticmethod
    def validate():
        """Validate all required environment variables"""
        required = [
            "SECRET_KEY",
            "JWT_SECRET_KEY",
            "DATABASE_URL",
            "DERIV_REDIRECT_URI",
            "ENCRYPTION_KEY",
            "FRONTEND_URL"
        ]
        
        missing = []
        for key in required:
            if not os.getenv(key):
                missing.append(key)
        
        if missing:
            raise ValueError(
                f"\n{'='*60}\n"
                f"❌ MISSING REQUIRED ENVIRONMENT VARIABLES\n"
                f"{'='*60}\n"
                f"Please add these to your .env file:\n\n"
                f"  {', '.join(missing)}\n"
                f"{'='*60}\n"
            )
        
        # ✅ Check DERIV_APP_ID warning (clean)
        app_id = os.getenv('DERIV_APP_ID')
        if app_id and not app_id.isdigit():
            print(
                f"\n{'='*60}\n"
                f"⚠️  WARNING: DERIV_APP_ID is not numeric\n"
                f"{'='*60}\n"
                f"  Current value: {app_id}\n"
                f"  Using fallback: 1089\n"
                f"  For WebSocket connections, Deriv requires a numeric app_id.\n"
                f"  If you have a numeric app_id, update your .env file.\n"
                f"{'='*60}\n"
            )
        
        # ✅ Check encryption key format
        encryption_key = os.getenv('ENCRYPTION_KEY')
        if encryption_key:
            try:
                import base64
                base64.urlsafe_b64decode(encryption_key)
            except:
                print(
                    f"\n{'='*60}\n"
                    f"⚠️  WARNING: ENCRYPTION_KEY format may be invalid\n"
                    f"{'='*60}\n"
                    f"  Your ENCRYPTION_KEY should be a valid base64 string.\n"
                    f"  Generate one using:\n"
                    f"  python -c \"import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\"\n"
                    f"{'='*60}\n"
                )
        
        print("✅ All required environment variables are set")

class DevelopmentConfig(Config):
    pass

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}