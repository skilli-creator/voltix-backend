# backend/models/database.py
import os
import re
import mysql.connector
from mysql.connector import Error
import bcrypt
from datetime import datetime, timedelta
import random
from config import Config

class Database:
    def __init__(self):
        self.connection = None
    
    def get_connection(self):
        try:
            # First try DATABASE_URL (production)
            database_url = os.getenv('DATABASE_URL')
            
            if database_url:
                # Parse mysql://user:password@host:port/database
                pattern = r'mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
                match = re.match(pattern, database_url)
                
                if match:
                    print(f"🔗 Connecting to production database...")
                    self.connection = mysql.connector.connect(
                        host=match.group(3),
                        user=match.group(1),
                        password=match.group(2),
                        database=match.group(5),
                        port=int(match.group(4)),
                        consume_results=True,
                        autocommit=False,
                        ssl_disabled=False
                    )
                    return self.connection
            
            # Fallback to individual variables
            print(f"🔗 Connecting to local database...")
            self.connection = mysql.connector.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                port=Config.DB_PORT,
                consume_results=True,
                autocommit=False
            )
            return self.connection
        except Error as e:
            print(f"Database error: {e}")
            return None
    
    def test_connection(self):
        conn = self.get_connection()
        if conn:
            print("✅ Database connected successfully!")
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchall()
                cursor.close()
            except:
                pass
            conn.close()
            return True
        else:
            print("❌ Database connection failed!")
            return False
    
    def ensure_tables(self):
        """Create required tables if they don't exist"""
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    phone VARCHAR(20) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    email_verified BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    verification_code VARCHAR(10),
                    code_expires_at DATETIME,
                    reset_code VARCHAR(10),
                    reset_code_expires_at DATETIME,
                    last_login DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_email (email),
                    INDEX idx_phone (phone)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Create deriv_accounts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deriv_accounts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    api_token TEXT NOT NULL,
                    account_id VARCHAR(100),
                    currency VARCHAR(10) DEFAULT 'USD',
                    balance DECIMAL(20, 8) DEFAULT 0,
                    is_connected BOOLEAN DEFAULT FALSE,
                    connection_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    UNIQUE KEY unique_user (user_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            conn.commit()
            print("✅ Tables ensured")
            return True
            
        except Error as e:
            print(f"Table creation error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    # ==================== USER FUNCTIONS ====================
    
    def create_user(self, first_name, last_name, phone, email, password):
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        try:
            cursor.execute("""
                INSERT INTO users (first_name, last_name, phone, email, password_hash)
                VALUES (%s, %s, %s, %s, %s)
            """, (first_name, last_name, phone, email, password_hash.decode('utf-8')))
            conn.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"Create user error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_user_by_email(self, email):
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.fetchall()
            return user
        except Error as e:
            print(f"Get user by email error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_user_by_phone(self, phone):
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE phone = %s", (phone,))
            user = cursor.fetchone()
            cursor.fetchall()
            return user
        except Error as e:
            print(f"Get user by phone error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_user_by_id(self, user_id):
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT id, email, first_name, last_name, phone, email_verified, is_active 
                FROM users WHERE id = %s
            """, (user_id,))
            user = cursor.fetchone()
            cursor.fetchall()
            return user
        except Error as e:
            print(f"Get user by ID error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def update_last_login(self, user_id):
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user_id,))
            conn.commit()
            return True
        except Error as e:
            print(f"Update last login error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    def update_email_verified(self, user_id):
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET email_verified = 1 WHERE id = %s", (user_id,))
            conn.commit()
            return True
        except Error as e:
            print(f"Update email verified error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    # ==================== VERIFICATION CODE FUNCTIONS ====================
    
    def generate_code(self):
        return f"{random.randint(100000, 999999)}"
    
    def save_verification_code(self, user_id, email_code):
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        expires_at = datetime.now() + timedelta(minutes=10)
        
        try:
            cursor.execute("""
                UPDATE users SET verification_code = %s, code_expires_at = %s WHERE id = %s
            """, (email_code, expires_at, user_id))
            conn.commit()
            return True
        except Error as e:
            print(f"Save code error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    def verify_code(self, user_id, code):
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT verification_code, code_expires_at FROM users WHERE id = %s
            """, (user_id,))
            user = cursor.fetchone()
            cursor.fetchall()
            
            if not user:
                return False
            
            if user['verification_code'] == code and datetime.now() < user['code_expires_at']:
                return True
            return False
        except Error as e:
            print(f"Verify code error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    # ============================================
    # DERIV ACCOUNT FUNCTIONS
    # ============================================
    
    def save_deriv_token(self, user_id, encrypted_token, account_id=None, 
                         currency='USD', balance=0):
        """Save or update Deriv API token for a user"""
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM deriv_accounts WHERE user_id = %s", (user_id,))
            existing = cursor.fetchone()
            cursor.fetchall()
            
            if existing:
                cursor.execute("""
                    UPDATE deriv_accounts 
                    SET api_token = %s, 
                        account_id = %s,
                        balance = %s, 
                        currency = %s,
                        is_connected = 1,
                        last_active_at = NOW()
                    WHERE user_id = %s
                """, (encrypted_token, account_id, balance, currency, user_id))
            else:
                cursor.execute("""
                    INSERT INTO deriv_accounts 
                    (user_id, api_token, account_id, balance, currency, is_connected, connection_date, last_active_at)
                    VALUES (%s, %s, %s, %s, %s, 1, NOW(), NOW())
                """, (user_id, encrypted_token, account_id, balance, currency))
            
            conn.commit()
            return True
            
        except Error as e:
            print(f"Save deriv token error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def get_deriv_token(self, user_id):
        """Get Deriv token for a user"""
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT * FROM deriv_accounts 
                WHERE user_id = %s AND is_connected = 1
            """, (user_id,))
            
            result = cursor.fetchone()
            cursor.fetchall()
            return result
            
        except Error as e:
            print(f"Get deriv token error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def update_deriv_balance(self, user_id, balance):
        """Update user's Deriv account balance"""
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE deriv_accounts 
                SET balance = %s, last_active_at = NOW()
                WHERE user_id = %s
            """, (balance, user_id))
            conn.commit()
            return True
            
        except Error as e:
            print(f"Update deriv balance error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def disconnect_deriv(self, user_id):
        """Disconnect Deriv account"""
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE deriv_accounts 
                SET is_connected = 0, last_active_at = NOW()
                WHERE user_id = %s
            """, (user_id,))
            conn.commit()
            return True
            
        except Error as e:
            print(f"Disconnect deriv error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def get_deriv_account_status(self, user_id):
        """Get Deriv account status"""
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT id, account_id, currency, balance, is_connected, 
                       connection_date, last_active_at
                FROM deriv_accounts 
                WHERE user_id = %s
            """, (user_id,))
            
            result = cursor.fetchone()
            cursor.fetchall()
            
            if not result:
                return {'isConnected': False}
            
            return result
            
        except Error as e:
            print(f"Get deriv status error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def deactivate_deriv_token(self, user_id):
        """Deactivate Deriv token (legacy)"""
        return self.disconnect_deriv(user_id)

# Create single instance
db = Database()

# Ensure tables exist on import
db.ensure_tables()