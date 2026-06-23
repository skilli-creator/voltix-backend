# backend/services/deriv_service.py

import time
from typing import Dict, List, Optional

class DerivService:
    """Service for managing Deriv market data - Real data only"""
    
    def __init__(self):
        self.market_data = {}
        self.volatility_markets = self._get_volatility_markets()
    
    def _get_volatility_markets(self):
        """Define all volatility markets available"""
        return [
            {'symbol': 'R_100_1S', 'name': 'Volatility 100 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_10_1S', 'name': 'Volatility 10 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_25_1S', 'name': 'Volatility 25 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_50_1S', 'name': 'Volatility 50 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_75_1S', 'name': 'Volatility 75 (1s) Index', 'isOneSec': True},
            {'symbol': 'R_10', 'name': 'Volatility 10 Index', 'isOneSec': False},
            {'symbol': 'R_25', 'name': 'Volatility 25 Index', 'isOneSec': False},
            {'symbol': 'R_50', 'name': 'Volatility 50 Index', 'isOneSec': False},
            {'symbol': 'R_75', 'name': 'Volatility 75 Index', 'isOneSec': False},
            {'symbol': 'R_100', 'name': 'Volatility 100 Index', 'isOneSec': False},
        ]
    
    def set_market_data(self, symbol: str, data: Dict) -> bool:
        """Set market data for a symbol"""
        self.market_data[symbol] = data
        return True
    
    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get data for a specific market"""
        return self.market_data.get(symbol)
    
    def get_all_market_data(self) -> Dict:
        """Get all market data"""
        return self.market_data
    
    def get_markets_list(self) -> List[Dict]:
        """Get list of available markets"""
        return self.volatility_markets
    
    def update_market_data(self, symbol: str, new_data: Dict) -> bool:
        """Update market data with real data from Deriv"""
        if symbol in self.market_data:
            self.market_data[symbol] = new_data
            return True
        return False
    
    def clear_all_market_data(self):
        """Clear all market data"""
        self.market_data.clear()
    
    def remove_market_data(self, symbol: str) -> bool:
        """Remove data for a specific market"""
        if symbol in self.market_data:
            del self.market_data[symbol]
            return True
        return False
    
    def get_market_history(self, symbol: str, limit: int = 150) -> Optional[List[Dict]]:
        """Get historical ticks for a market"""
        data = self.market_data.get(symbol)
        if not data:
            return None
        return data.get('ticks', [])[-limit:]

# ✅ MAKE SURE THIS EXISTS AT THE BOTTOM
deriv_service = DerivService()