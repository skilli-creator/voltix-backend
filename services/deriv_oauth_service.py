# backend/services/deriv_oauth_service.py

import hashlib
import base64
import secrets
import requests
from urllib.parse import urlencode
from config import Config

class DerivOAuthService:
    """Service for handling Deriv OAuth 2.0 with PKCE"""
    
    def __init__(self):
        self.client_id = Config.DERIV_APP_ID
        self.redirect_uri = Config.DERIV_REDIRECT_URI
        self.auth_url = "https://oauth.deriv.com/oauth2/authorize"
        self.token_url = "https://oauth.deriv.com/oauth2/token"
        self.api_base = "https://api.deriv.com"
        
        print(f"🔑 Client ID: {self.client_id}")
        print(f"🔗 Auth URL: {self.auth_url}")
        print(f"🔗 Token URL: {self.token_url}")
    
    def is_configured(self):
        return bool(self.client_id)
    
    def generate_pkce_code_verifier(self):
        """Generate a PKCE code verifier"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('ascii')
    
    def generate_pkce_code_challenge(self, code_verifier):
        """Generate a PKCE code challenge from the verifier"""
        code_challenge = hashlib.sha256(code_verifier.encode('ascii')).digest()
        return base64.urlsafe_b64encode(code_challenge).rstrip(b'=').decode('ascii')
    
    def get_authorization_url(self, state=None):
        if not self.is_configured():
            raise Exception("DERIV_APP_ID not configured")
        
        code_verifier = self.generate_pkce_code_verifier()
        code_challenge = self.generate_pkce_code_challenge(code_verifier)
        
        if not state:
            state = secrets.token_urlsafe(16)
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'read write',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'state': state
        }
        
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        print(f"🔍 Generated Auth URL: {auth_url}")
        return auth_url, code_verifier, state
    
    def exchange_code_for_tokens(self, code, code_verifier):
        """Exchange code for tokens with PKCE code_verifier"""
        if not self.is_configured():
            raise Exception("DERIV_APP_ID not configured")
        
        print(f"🔄 Exchanging code for tokens...")
        print(f"📡 Token URL: {self.token_url}")
        print(f"📝 Code: {code[:20]}...")
        print(f"🔑 Code Verifier: {code_verifier[:20]}...")
        
        try:
            response = requests.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "code_verifier": code_verifier,  # ✅ REQUIRED for PKCE
                },
                timeout=30
            )
            
            print(f"📡 Status: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                print(f"✅ Token exchange successful")
                return {
                    'access_token': token_data.get('access_token'),
                    'refresh_token': token_data.get('refresh_token'),
                    'token_type': token_data.get('token_type', 'Bearer'),
                    'expires_in': token_data.get('expires_in', 3600)
                }
            else:
                print(f"❌ Token exchange failed: {response.text}")
                raise Exception(f"Token exchange failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            raise
    
    def get_account_info(self, access_token):
        headers = {'Authorization': f'Bearer {access_token}'}
        print(f"🔄 Getting account info...")
        
        try:
            response = requests.post(
                f"{self.api_base}/account_list",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('error'):
                    raise Exception(f"API error: {data.get('error')}")
                
                accounts = data.get('account_list', [])
                if accounts:
                    account = accounts[0]
                    print(f"✅ Account info retrieved: {account.get('account_id')}")
                    return {
                        'account_id': account.get('account_id'),
                        'account_type': account.get('account_type', 'Demo'),
                        'email': account.get('email'),
                        'currency': account.get('currency', 'USD'),
                        'balance': account.get('balance', 0)
                    }
                raise Exception("No accounts found")
            else:
                raise Exception(f"Failed to get account info: {response.text}")
                
        except Exception as e:
            print(f"❌ Error getting account info: {e}")
            raise

deriv_oauth_service = DerivOAuthService()