# backend/routes/deriv_oauth_routes.py

from flask import Blueprint, request, jsonify, redirect, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.deriv_oauth_service import deriv_oauth_service
from models.database import db
import secrets
from datetime import datetime

deriv_oauth_bp = Blueprint('deriv_oauth', __name__)

# ============================================
# OAUTH ENDPOINTS
# ============================================

@deriv_oauth_bp.route('/initiate', methods=['POST'])
@jwt_required()
def initiate_oauth():
    """
    Initiate OAuth flow - returns authorization URL
    """
    try:
        # Check if OAuth is configured
        if not deriv_oauth_service.is_configured():
            return jsonify({
                'success': False,
                'error': 'OAuth not configured. Please add DERIV_APP_ID to environment variables.'
            }), 400
        
        user_id = get_jwt_identity()
        
        # Generate PKCE verifier and state
        auth_url, code_verifier, state = deriv_oauth_service.get_authorization_url()
        
        # Store verifier and state in session
        session['deriv_oauth_verifier'] = code_verifier
        session['deriv_oauth_state'] = state
        session['deriv_oauth_user_id'] = user_id
        
        return jsonify({
            'success': True,
            'auth_url': auth_url,
            'state': state
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_oauth_bp.route('/callback', methods=['GET'])
def oauth_callback():
    """
    Handle OAuth callback from Deriv
    """
    try:
        # Get code and state from query params
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            return f"""
            <html>
                <body>
                    <h2>OAuth Error</h2>
                    <p>Error: {error}</p>
                    <p>Please close this window and try again.</p>
                    <script>setTimeout(function(){{ window.close(); }}, 3000);</script>
                </body>
            </html>
            """
        
        if not code:
            return """
            <html>
                <body>
                    <h2>No Authorization Code</h2>
                    <p>No authorization code received. Please try again.</p>
                </body>
            </html>
            """
        
        # Get stored verifier and user_id from session
        stored_verifier = session.get('deriv_oauth_verifier')
        stored_state = session.get('deriv_oauth_state')
        user_id = session.get('deriv_oauth_user_id')
        
        if not stored_verifier or not user_id:
            return """
            <html>
                <body>
                    <h2>Session Expired</h2>
                    <p>OAuth session expired. Please try again.</p>
                    <script>setTimeout(function(){{ window.close(); }}, 3000);</script>
                </body>
            </html>
            """
        
        # Verify state
        if state != stored_state:
            return """
            <html>
                <body>
                    <h2>Invalid State</h2>
                    <p>Invalid state parameter. Please try again.</p>
                </body>
            </html>
            """
        
        # Exchange code for tokens
        token_data = deriv_oauth_service.exchange_code_for_tokens(code, stored_verifier)
        
        # Get account info
        account_info = deriv_oauth_service.get_account_info(token_data['access_token'])
        
        # Save tokens to database
        db.save_deriv_token(
            user_id=user_id,
            access_token=token_data['access_token'],
            account_id=account_info['account_id'],
            email=account_info.get('email'),
            account_type=account_info.get('account_type', 'Demo'),
            currency=account_info['currency'],
            balance=account_info['balance']
        )
        
        # Clear session data
        session.pop('deriv_oauth_verifier', None)
        session.pop('deriv_oauth_state', None)
        session.pop('deriv_oauth_user_id', None)
        
        # Return success page with redirect
        return f"""
        <html>
            <body>
                <h2>✅ Connection Successful!</h2>
                <p>Your Deriv account has been connected.</p>
                <p>Redirecting to dashboard...</p>
                <script>
                    setTimeout(function() {{
                        window.opener.location.href = '/derivdash?connected=true&account_id={account_info["account_id"]}';
                        window.close();
                    }}, 2000);
                </script>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
            <body>
                <h2>❌ Connection Failed</h2>
                <p>Error: {str(e)}</p>
                <p>Please close this window and try again.</p>
                <script>setTimeout(function(){{ window.close(); }}, 3000);</script>
            </body>
        </html>
        """


@deriv_oauth_bp.route('/status', methods=['GET'])
@jwt_required()
def get_connection_status():
    """Check if user has an active Deriv connection"""
    try:
        user_id = get_jwt_identity()
        token_data = db.get_deriv_token(user_id)
        
        if not token_data:
            return jsonify({
                'connected': False,
                'message': 'No Deriv account connected'
            })
        
        return jsonify({
            'connected': True,
            'account_id': token_data['account_id'],
            'account_type': token_data['account_type'],
            'currency': token_data['currency'],
            'balance': float(token_data['balance']) if token_data['balance'] else 0,
            'email': token_data.get('email')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deriv_oauth_bp.route('/disconnect', methods=['POST'])
@jwt_required()
def disconnect():
    """Disconnect Deriv account"""
    try:
        user_id = get_jwt_identity()
        db.deactivate_deriv_token(user_id)
        
        return jsonify({
            'success': True,
            'message': 'Deriv account disconnected successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500