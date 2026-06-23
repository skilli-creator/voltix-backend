# backend/services/__init__.py

from .deriv_service import deriv_service
from .websocket_service import websocket_service

__all__ = ['deriv_service', 'websocket_service']