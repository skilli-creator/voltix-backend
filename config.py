# backend/config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'voltix')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    
    # Email - Resend
    RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
    RESEND_FROM_EMAIL = os.getenv('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'tonnykyalo054@gmail.com')  # ✅ Updated
    
    # Environment
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    
    # ============================================
    # DERIV OAUTH CONFIGURATION
    # ============================================
    DERIV_APP_ID = os.getenv('DERIV_APP_ID', '')
    DERIV_REDIRECT_URI = os.getenv('DERIV_REDIRECT_URI', '')
    FRONTEND_URL = os.getenv('FRONTEND_URL', '')