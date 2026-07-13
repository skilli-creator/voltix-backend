# backend/services/__init__.py
from services.deriv_service import (
    connection_manager,
    deriv_service,
    init_socketio,
    cleanup_all_connections,
    connect_deriv_account,
    disconnect_deriv_account,
    get_deriv_account_status,
    get_deriv_balance,
    validate_deriv_token,
    is_deriv_connected,
    get_account_info,
    get_connection_status,
    subscribe_to_symbol,
    unsubscribe_from_symbol,
    encrypt_token,
    decrypt_token,
    get_deriv_accounts,
    request_otp
)
from services.email_service import EmailService

__all__ = [
    'connection_manager',
    'deriv_service',
    'init_socketio',
    'cleanup_all_connections',
    'connect_deriv_account',
    'disconnect_deriv_account',
    'get_deriv_account_status',
    'get_deriv_balance',
    'validate_deriv_token',
    'is_deriv_connected',
    'get_account_info',
    'get_connection_status',
    'subscribe_to_symbol',
    'unsubscribe_from_symbol',
    'encrypt_token',
    'decrypt_token',
    'get_deriv_accounts',
    'request_otp',
    'EmailService'
]