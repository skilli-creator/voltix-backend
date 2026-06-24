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
    
    # Email
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    
    # Environment
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    
    # ============================================
    # DERIV OAUTH CONFIGURATION
    # ============================================
    DERIV_APP_ID = os.getenv('DERIV_APP_ID', '')
    DERIV_REDIRECT_URI = os.getenv('DERIV_REDIRECT_URI', 'https://voltix-traders.vercel.app/api/deriv/oauth/callback')
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://voltix-traders.vercel.app/derivhome')
    
    @staticmethod
    def is_production():
        return os.getenv('ENVIRONMENT') == 'production'