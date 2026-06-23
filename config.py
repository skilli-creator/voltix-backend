# backend/config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    
    # Database
    # Priority 1: Use DATABASE_URL (for production - Render/Clever Cloud)
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # Priority 2: Individual variables (for local development)
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
    
    # Helper method to check if running in production
    @staticmethod
    def is_production():
        return os.getenv('ENVIRONMENT') == 'production'