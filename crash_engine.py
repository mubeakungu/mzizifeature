"""
crash_engine.py - Unified crash game engine (shared by ALL games)
This file is IDENTICAL for every game type - no modifications needed!
"""

import hashlib
import secrets
from decimal import Decimal
from enum import Enum

class GameType(Enum):
    AVIATOR = "aviator"
    JETX = "jetx"
    CARDS = "cards"
    ROLLER = "roller"
    RACE = "race"
    MINER = "miner"
    FISHY = "fishy"

class CrashGameEngine:
    """
    Universal crash game engine.
    Used by ALL games - only visual representation changes.
    """
    
    # Override these in subclass
    GAME_TYPE = GameType.AVIATOR
    MIN_MULTIPLIER = Decimal("1.01")
    MAX_MULTIPLIER = Decimal("100.00")
    BETTING_WINDOW = 5  # seconds
    GAME_DURATION = 45  # seconds
    MIN_BET = Decimal("10")
    MAX_BET = Decimal("100000")
    DEFAULT_RTP = Decimal("0.96")  # 96% return to player
    
    @staticmethod
    def generate_server_seed():
        """Generate random server seed for fairness"""
        return secrets.token_hex(32)
    
    @staticmethod
    def generate_crash_point(server_seed: str, client_nonce: str = "") -> tuple:
        """
        Provably fair crash point generation.
        
        Math:
        1. Hash(server_seed + client_nonce) → 256-bit number
        2. Normalize to 0-1 range
        3. Apply non-linear distribution
        4. Map to multiplier range
        5. Apply house edge
        
        Returns: (crash_multiplier, client_nonce)
        """
        if not client_nonce:
            client_nonce = secrets.token_hex(16)
        
        # Cryptographic hash
        combined = f"{server_seed}:{client_nonce}"
        hash_object = hashlib.sha256(combined.encode())
        hash_int = int(hash_object.hexdigest(), 16)
        
        # Normalize 0-1
        normalized = (hash_int % 10000) / 10000.0
        
        # Non-linear distribution (sqrt for more crashes at low multipliers)
        range_size = float(CrashGameEngine.MAX_MULTIPLIER - CrashGameEngine.MIN_MULTIPLIER)
        crash_point = CrashGameEngine.MIN_MULTIPLIER + (
            Decimal(str(range_size * (normalized ** 0.5)))
        )
        
        # Apply RTP adjustment
        crash_point = CrashGameEngine._apply_rtp(crash_point)
        
        return (float(crash_point), client_nonce)
    
    @staticmethod
    def _apply_rtp(crash_point: Decimal) -> Decimal:
        """Maintain 96% RTP by adjusting crash distribution"""
        rtp = CrashGameEngine.DEFAULT_RTP
        house_edge_factor = 1 / float(rtp)  # 1.04x
        adjusted = crash_point / Decimal(str(house_edge_factor))
        return min(adjusted, CrashGameEngine.MAX_MULTIPLIER)
    
    @staticmethod
    def calculate_payout(bet_amount: Decimal, multiplier: float) -> Decimal:
        """Simple: bet × multiplier"""
        return bet_amount * Decimal(str(multiplier))
    
    @staticmethod
    def calculate_profit(bet_amount: Decimal, multiplier: float) -> Decimal:
        """Profit = payout - bet"""
        payout = CrashGameEngine.calculate_payout(bet_amount, multiplier)
        return payout - bet_amount
    
    @classmethod
    def get_game_config(cls) -> dict:
        """Return config dict for frontend"""
        return {
            "game_type": cls.GAME_TYPE.value,
            "min_multiplier": float(cls.MIN_MULTIPLIER),
            "max_multiplier": float(cls.MAX_MULTIPLIER),
            "min_bet": float(cls.MIN_BET),
            "max_bet": float(cls.MAX_BET),
            "betting_window": cls.BETTING_WINDOW,
            "game_duration": cls.GAME_DURATION,
            "rtp": float(cls.DEFAULT_RTP),
        }
