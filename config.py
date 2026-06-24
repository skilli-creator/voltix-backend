# backend/config.py

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    # ============================================
    # FLASK / SECURITY
    # ============================================
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')

    # ============================================
    # DATABASE
    # ============================================
    DATABASE_URL = os.getenv('DATABASE_URL')  # optional (if using full URL)

    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'voltix')
    DB_PORT = int(os.getenv('DB_PORT', 3306))

    # ============================================
    # EMAIL CONFIG
    # ============================================
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')

    # ============================================
    # ENVIRONMENT
    # ============================================
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

    # ============================================
    # DERIV OAUTH CONFIGURATION
    # ============================================
    DERIV_APP_ID = os.getenv('DERIV_APP_ID', '')
    DERIV_REDIRECT_URI = os.getenv('DERIV_REDIRECT_URI', 'https://voltix-backend-vh8c.onrender.com/api/deriv/oauth/callback')
    FRONTEND_URL = os.getenv('FRONTEND_URL', '')

    # ============================================
    # HELPERS
    # ============================================
    @staticmethod
    def is_production():
        return os.getenv('ENVIRONMENT') == 'production'