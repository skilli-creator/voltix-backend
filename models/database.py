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
                        autocommit=False
                    )
                    return self.connection
            
            # Fallback to individual variables (local development)
            print(f"🔗 Connecting to local database...")
            self.connection = mysql.connector.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
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
            # Consume any pending results before closing
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchall()  # Consume all results
                cursor.close()
            except:
                pass
            conn.close()
            return True
        else:
            print("❌ Database connection failed!")
            return False
    
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
            # Consume any remaining results
            cursor.fetchall()
            return user
        except Error as e:
            print(f"Get user by email error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_user_by_phone(self, phone):
        """Get user by phone number"""
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE phone = %s", (phone,))
            user = cursor.fetchone()
            # Consume any remaining results
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
            cursor.execute("SELECT id, email, first_name, last_name, phone, email_verified, is_active FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            # Consume any remaining results
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
            cursor.execute("SELECT verification_code, code_expires_at FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            # Consume any remaining results
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
    
    # ==================== DERIV OAUTH FUNCTIONS ====================
    
    def save_deriv_token(self, user_id, access_token, account_id=None, email=None, 
                         account_type='Demo', currency='USD', balance=0):
        """
        Save or update Deriv OAuth token for a user
        Uses your existing deriv_accounts table
        """
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            # Check if account exists for user
            cursor.execute("SELECT id FROM deriv_accounts WHERE user_id = %s AND account_id = %s", 
                          (user_id, account_id))
            existing = cursor.fetchone()
            # Consume any remaining results
            cursor.fetchall()
            
            # Access token might be long - store as binary
            token_binary = access_token.encode('utf-8')
            
            if existing:
                # Update existing account
                cursor.execute("""
                    UPDATE deriv_accounts 
                    SET token = %s, 
                        balance = %s, 
                        currency = %s,
                        account_type = %s,
                        email = %s,
                        is_active = 1,
                        last_sync_at = CURRENT_TIMESTAMP,
                        last_error = NULL
                    WHERE user_id = %s AND account_id = %s
                """, (token_binary, balance, currency, account_type, email, user_id, account_id))
            else:
                # Insert new account
                cursor.execute("""
                    INSERT INTO deriv_accounts 
                    (user_id, account_id, email, token, balance, currency, account_type, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                """, (user_id, account_id, email, token_binary, balance, currency, account_type))
            
            conn.commit()
            return True
            
        except Error as e:
            print(f"Save deriv token error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def get_deriv_token(self, user_id, account_id=None):
        """
        Get Deriv token for a user
        If account_id is None, returns the first active account
        """
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        
        try:
            if account_id:
                cursor.execute("""
                    SELECT * FROM deriv_accounts 
                    WHERE user_id = %s AND account_id = %s AND is_active = 1
                """, (user_id, account_id))
            else:
                cursor.execute("""
                    SELECT * FROM deriv_accounts 
                    WHERE user_id = %s AND is_active = 1
                    ORDER BY created_at DESC LIMIT 1
                """, (user_id,))
            
            result = cursor.fetchone()
            # Consume any remaining results
            cursor.fetchall()
            
            # Decode token from binary to string
            if result and result.get('token'):
                result['access_token'] = result['token'].decode('utf-8')
            
            return result
            
        except Error as e:
            print(f"Get deriv token error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_all_deriv_accounts(self, user_id):
        """Get all Deriv accounts for a user"""
        conn = self.get_connection()
        if not conn:
            return []
        
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT * FROM deriv_accounts 
                WHERE user_id = %s AND is_active = 1
                ORDER BY created_at DESC
            """, (user_id,))
            
            results = cursor.fetchall()
            # Consume any remaining results
            cursor.fetchall()
            
            # Decode tokens
            for result in results:
                if result.get('token'):
                    result['access_token'] = result['token'].decode('utf-8')
            
            return results
            
        except Error as e:
            print(f"Get all deriv accounts error: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
    
    def update_deriv_balance(self, user_id, account_id, balance, currency='USD'):
        """Update user's Deriv account balance"""
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE deriv_accounts 
                SET balance = %s, currency = %s, last_sync_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND account_id = %s
            """, (balance, currency, user_id, account_id))
            conn.commit()
            return True
            
        except Error as e:
            print(f"Update deriv balance error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def update_deriv_profit_loss(self, user_id, account_id, profits=0, losses=0):
        """Update profit/loss for a Deriv account"""
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE deriv_accounts 
                SET profits_made = profits_made + %s, 
                    losses_made = losses_made + %s,
                    last_sync_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND account_id = %s
            """, (profits, losses, user_id, account_id))
            conn.commit()
            return True
            
        except Error as e:
            print(f"Update deriv profit/loss error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def deactivate_deriv_token(self, user_id, account_id=None):
        """Deactivate (disconnect) Deriv token(s)"""
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            if account_id:
                cursor.execute("""
                    UPDATE deriv_accounts 
                    SET is_active = 0, last_sync_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND account_id = %s
                """, (user_id, account_id))
            else:
                cursor.execute("""
                    UPDATE deriv_accounts 
                    SET is_active = 0, last_sync_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (user_id,))
            
            conn.commit()
            return True
            
        except Error as e:
            print(f"Deactivate deriv token error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def update_deriv_error(self, user_id, account_id, error_message):
        """Log error for a Deriv account"""
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE deriv_accounts 
                SET last_error = %s, last_sync_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND account_id = %s
            """, (error_message, user_id, account_id))
            conn.commit()
            return True
            
        except Error as e:
            print(f"Update deriv error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    
    def refresh_deriv_token(self, user_id, account_id, new_access_token, balance=None, currency=None):
        """Refresh Deriv token"""
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        token_binary = new_access_token.encode('utf-8')
        
        try:
            query = """
                UPDATE deriv_accounts 
                SET token = %s, last_sync_at = CURRENT_TIMESTAMP
            """
            params = [token_binary]
            
            if balance is not None:
                query += ", balance = %s"
                params.append(balance)
            
            if currency:
                query += ", currency = %s"
                params.append(currency)
            
            query += " WHERE user_id = %s AND account_id = %s"
            params.extend([user_id, account_id])
            
            cursor.execute(query, tuple(params))
            conn.commit()
            return True
            
        except Error as e:
            print(f"Refresh deriv token error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    # ==================== OAUTH STATE FUNCTIONS ====================

    def save_oauth_state(self, user_id, state, code_verifier):
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO oauth_states (user_id, state, code_verifier)
                VALUES (%s, %s, %s)
            """, (user_id, state, code_verifier))
            
            conn.commit()
            return True
            
        except Error as e:
            print(f"Save oauth state error: {e}")
            conn.rollback()
            return False
            
        finally:
            cursor.close()
            conn.close()


    def get_oauth_state(self, state):
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT * FROM oauth_states WHERE state = %s", (state,))
            result = cursor.fetchone()
            cursor.fetchall()
            return result
            
        except Error as e:
            print(f"Get oauth state error: {e}")
            return None
            
        finally:
            cursor.close()
            conn.close()


    def delete_oauth_state(self, state):
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM oauth_states WHERE state = %s", (state,))
            conn.commit()
            return True
            
        except Error as e:
            print(f"Delete oauth state error: {e}")
            conn.rollback()
            return False
            
        finally:
            cursor.close()
            conn.close()        
                

# Create single instance
db = Database()