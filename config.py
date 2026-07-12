# backend/config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

class Config:
    # ============================================
    # SECRETS - MUST come from environment
    # ============================================
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    
    if not SECRET_KEY:
        raise ValueError("❌ SECRET_KEY must be set in .env")
    if not JWT_SECRET_KEY:
        raise ValueError("❌ JWT_SECRET_KEY must be set in .env")
    
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
    
    # ============================================
    # DATABASE - MySQL
    # ============================================
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'voltix')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    
    # Build DATABASE_URL for compatibility
    DATABASE_URL = os.getenv('DATABASE_URL', f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    # ============================================
    # DERIV - MANUAL API TOKEN ONLY
    # ============================================
    raw_app_id = os.getenv('DERIV_APP_ID')
    if raw_app_id and raw_app_id.isdigit():
        DERIV_APP_ID = raw_app_id
    else:
        DERIV_APP_ID = '1089'
    
    DERIV_WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    
    # ============================================
    # ENCRYPTION
    # ============================================
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    
    if not ENCRYPTION_KEY:
        raise ValueError("❌ ENCRYPTION_KEY must be set in .env")
    
    # ============================================
    # FRONTEND
    # ============================================
    FRONTEND_URL = os.getenv('FRONTEND_URL')
    
    if not FRONTEND_URL:
        raise ValueError("❌ FRONTEND_URL must be set in .env")
    
    # ============================================
    # CORS
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
    
    @staticmethod
    def validate():
        """Validate all required environment variables"""
        required = [
            "SECRET_KEY",
            "JWT_SECRET_KEY",
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
        
        app_id = os.getenv('DERIV_APP_ID')
        if app_id and not app_id.isdigit():
            print(
                f"\n{'='*60}\n"
                f"⚠️  WARNING: DERIV_APP_ID is not numeric\n"
                f"{'='*60}\n"
                f"  Current value: {app_id}\n"
                f"  Using fallback: 1089\n"
                f"  For WebSocket connections, Deriv requires a numeric app_id.\n"
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