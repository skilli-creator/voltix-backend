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
        self.auth_url = "https://auth.deriv.com/oauth2/auth"
        self.token_url = "https://auth.deriv.com/oauth2/token"
        self.api_base = "https://api.deriv.com"
        
        # Check if App ID is configured
        if not self.client_id:
            print("⚠️ WARNING: DERIV_APP_ID not set in environment")
    
    def is_configured(self):
        """Check if OAuth is properly configured"""
        return bool(self.client_id)
    
    def generate_pkce_code_verifier(self):
        """Generate a PKCE code verifier"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('ascii')
    
    def generate_pkce_code_challenge(self, code_verifier):
        """Generate a PKCE code challenge from the verifier"""
        code_challenge = hashlib.sha256(code_verifier.encode('ascii')).digest()
        return base64.urlsafe_b64encode(code_challenge).rstrip(b'=').decode('ascii')
    
    def get_authorization_url(self, state=None):
        """
        Generate the OAuth authorization URL with PKCE
        Returns: (auth_url, code_verifier, state)
        """
        if not self.is_configured():
            raise Exception("DERIV_APP_ID not configured. Please add it to environment variables.")
        
        code_verifier = self.generate_pkce_code_verifier()
        code_challenge = self.generate_pkce_code_challenge(code_verifier)
        
        if not state:
            state = secrets.token_urlsafe(16)
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'trading read',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'state': state
        }
        
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        return auth_url, code_verifier, state
    
    def exchange_code_for_tokens(self, code, code_verifier):
        """
        Exchange authorization code for access and refresh tokens
        """
        if not self.is_configured():
            raise Exception("DERIV_APP_ID not configured")
        
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'code': code,
            'redirect_uri': self.redirect_uri,
            'code_verifier': code_verifier
        }
        
        response = requests.post(self.token_url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            return {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_in': token_data.get('expires_in', 3600)
            }
        else:
            raise Exception(f"Token exchange failed: {response.text}")
    
    def get_account_info(self, access_token):
        """Get Deriv account information"""
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.post(f"{self.api_base}/account_list", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('error'):
                raise Exception(f"API error: {data.get('error')}")
            
            accounts = data.get('account_list', [])
            if accounts:
                account = accounts[0]
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
    
    def verify_token(self, access_token):
        """Verify if the access token is valid"""
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.post(f"{self.api_base}/account_list", headers=headers)
            return response.status_code == 200
        except:
            return False

# Singleton instance
deriv_oauth_service = DerivOAuthService()