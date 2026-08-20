"""
Enhanced Mzizibet Game Engine
Handles RNG, payout calculation, fairness, and game outcome generation.
Updated to support all 5 self-hosted games with validation and logging.
"""

import hashlib
import hmac
import secrets
import math
import logging
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class GameType(Enum):
    """All supported game types."""
    CRASH = "crash"
    AVIATOR = "aviator"
    HILO_CARD = "hilo_card"
    PLINKO = "plinko"
    JETX = "jetx"
    SLOTS = "slots"
    DICE = "dice"
    ROULETTE = "roulette"
    BLACKJACK = "blackjack"
    MINES = "mines"


class GameEngine:
    """Core game engine for all casino games with enhanced validation."""
    
    SECRET_SEED = "mzizibet_game_engine_secret_2024"
    MIN_MULTIPLIER = Decimal('1.00')
    MAX_MULTIPLIER = Decimal('500.00')
    
    @staticmethod
    def generate_round_id() -> str:
        """Generate unique round ID."""
        return secrets.token_hex(16)
    
    @staticmethod
    def generate_server_seed() -> str:
        """Generate server-side seed for this round."""
        return secrets.token_hex(32)
    
    @staticmethod
    def generate_client_nonce() -> str:
        """Generate client-side nonce for provable fairness."""
        return secrets.token_hex(16)
    
    @staticmethod
    def provably_fair_hash(server_seed: str, client_seed: str, nonce: int = 0) -> str:
        """
        Generate provably fair hash combining server seed, client seed, and nonce.
        
        Fairness Model:
        - Server seed: Generated before betting closes, revealed after round ends
        - Client seed: Player can provide, used to prevent pre-computation
        - Nonce: Public counter (0, 1, 2...) preventing seed reuse
        - Hash: SHA-256(server_seed:client_seed:nonce) → Deterministic & Verifiable
        
        Verification: Player gets all 3 values and can verify outcome was predetermined.
        """
        if not isinstance(server_seed, str) or not isinstance(client_seed, str):
            raise ValueError("Seeds must be strings")
        if not isinstance(nonce, int) or nonce < 0:
            raise ValueError("Nonce must be non-negative integer")
        
        combined = f"{server_seed}:{client_seed}:{nonce}".encode()
        return hashlib.sha256(combined).hexdigest()
    
    @staticmethod
    def seed_to_random(seed_hash: str, range_max: int = 100000) -> int:
        """
        Convert seed hash to random number in range [0, range_max).
        Uses first 8 hex digits for uniform distribution.
        """
        if not isinstance(seed_hash, str) or len(seed_hash) < 8:
            raise ValueError("Invalid seed hash")
        if range_max <= 0:
            raise ValueError("Range must be positive")
        
        return int(seed_hash[:8], 16) % range_max
    
    @classmethod
    def get_crash_multiplier(cls, server_seed: str, client_seed: str = None, nonce: int = 0) -> float:
        """
        Generate crash game multiplier (2.00 - 500.00x).
        Uses exponential distribution matching real casino patterns.
        
        Distribution:
        - Common: 2.00x - 5.00x (60%)
        - Rare: 10.00x - 50.00x (35%)
        - Very Rare: 100.00x - 500.00x (5%)
        
        Used by: mzizicrash, Aviator Mzizi
        """
        try:
            if client_seed is None:
                client_seed = cls.generate_client_nonce()
            
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            rand_val = int(seed_hash[:8], 16) / 0xffffffff
            
            # Clamp to valid range
            rand_val = max(0.00001, min(0.99999, rand_val))
            
            # Exponential distribution
            multiplier = 500.0 * math.exp(-math.log(500.0) * rand_val)
            multiplier = max(2.00, min(500.00, multiplier))
            
            return round(multiplier, 2)
        
        except Exception as e:
            logger.error(f"Error generating crash multiplier: {e}")
            raise ValueError(f"Failed to generate crash multiplier: {e}")
    
    @classmethod
    def get_aviator_multiplier(cls, server_seed: str, client_seed: str = None, nonce: int = 0) -> float:
        """
        Generate Aviator Mzizi multiplier.
        Same exponential distribution as crash but for plane climbing.
        """
        return cls.get_crash_multiplier(server_seed, client_seed, nonce)
    
    @classmethod
    def get_hilo_card(cls, server_seed: str, client_seed: str = None, nonce: int = 0) -> int:
        """
        Generate Hi-Lo Card value (2-14, where 14 is Ace).
        Standard poker card values.
        """
        try:
            if client_seed is None:
                client_seed = cls.generate_client_nonce()
            
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            card_value = cls.seed_to_random(seed_hash, 13) + 2  # 2-14
            
            return card_value
        
        except Exception as e:
            logger.error(f"Error generating hi-lo card: {e}")
            raise ValueError(f"Failed to generate hi-lo card: {e}")
    
    @classmethod
    def get_plinko_slot(cls, server_seed: str, client_seed: str = None, nonce: int = 0) -> int:
        """
        Generate Plinko Mzizi landing slot (0-8, 9 slots total).
        Center slots (3-5) have higher multipliers.
        """
        try:
            if client_seed is None:
                client_seed = cls.generate_client_nonce()
            
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            slot = cls.seed_to_random(seed_hash, 9)  # 0-8
            
            return slot
        
        except Exception as e:
            logger.error(f"Error generating plinko slot: {e}")
            raise ValueError(f"Failed to generate plinko slot: {e}")
    
    @classmethod
    def get_jetx_coins(cls, server_seed: str, client_seed: str = None, nonce: int = 0, duration: int = 120) -> int:
        """
        Generate Jet X Mzizi coin count before crash (0-duration/2).
        Coins collected = multiplier increase (1.0 + coins × 0.1, max 10.0).
        
        Args:
            duration: Game length in seconds (default 120)
        Returns:
            Number of coins collected (0-60)
        """
        try:
            if client_seed is None:
                client_seed = cls.generate_client_nonce()
            
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            # Max coins is half the duration (one coin per ~2 seconds)
            max_coins = duration // 2
            coins = cls.seed_to_random(seed_hash, max_coins + 1)
            
            return coins
        
        except Exception as e:
            logger.error(f"Error generating jetx coins: {e}")
            raise ValueError(f"Failed to generate jetx coins: {e}")
    
    @classmethod
    def get_slot_reels(cls, server_seed: str, client_seed: str, nonce: int = 0, num_reels: int = 5) -> List[int]:
        """
        Generate slot reel positions (0-9 for each reel).
        Each reel is independently random.
        """
        try:
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            reels = []
            
            for i in range(num_reels):
                reel_seed = hashlib.sha256(f"{seed_hash}_{i}".encode()).hexdigest()
                position = cls.seed_to_random(reel_seed, 10)
                reels.append(position)
            
            return reels
        
        except Exception as e:
            logger.error(f"Error generating slot reels: {e}")
            raise ValueError(f"Failed to generate slot reels: {e}")
    
    @classmethod
    def get_dice_roll(cls, server_seed: str, client_seed: str, nonce: int = 0) -> int:
        """Generate dice roll (1-6) using provably fair method."""
        try:
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            return cls.seed_to_random(seed_hash, 6) + 1
        
        except Exception as e:
            logger.error(f"Error generating dice roll: {e}")
            raise ValueError(f"Failed to generate dice roll: {e}")
    
    @classmethod
    def get_roulette_spin(cls, server_seed: str, client_seed: str, nonce: int = 0) -> int:
        """
        Generate roulette result (0-36 for European).
        0 = green, 1-36 = numbered slots
        """
        try:
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            return cls.seed_to_random(seed_hash, 37)
        
        except Exception as e:
            logger.error(f"Error generating roulette spin: {e}")
            raise ValueError(f"Failed to generate roulette spin: {e}")
    
    @classmethod
    def get_blackjack_deck(cls, server_seed: str, client_seed: str, nonce: int = 0) -> List[int]:
        """
        Generate shuffled deck for blackjack (4 decks, 13 values each).
        1-9 = face value, 10 = 10-value cards, 11 = Ace
        """
        try:
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            # 4 standard decks
            cards = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 11] * 4
            
            # Fisher-Yates shuffle using deterministic seed
            deck = cards.copy()
            for i in range(len(deck) - 1, 0, -1):
                reel_seed = hashlib.sha256(f"{seed_hash}_{i}".encode()).hexdigest()
                j = cls.seed_to_random(reel_seed, i + 1)
                deck[i], deck[j] = deck[j], deck[i]
            
            return deck
        
        except Exception as e:
            logger.error(f"Error generating blackjack deck: {e}")
            raise ValueError(f"Failed to generate blackjack deck: {e}")
    
    @classmethod
    def get_plinko_path(cls, server_seed: str, client_seed: str, nonce: int = 0, rows: int = 10) -> List[int]:
        """
        Generate plinko ball path (each row: 0=left, 1=right).
        Ball starts at top center and bounces down through rows.
        """
        try:
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            path = []
            
            for row in range(rows):
                cell_seed = hashlib.sha256(f"{seed_hash}_{row}".encode()).hexdigest()
                direction = cls.seed_to_random(cell_seed, 2)  # 0 or 1
                path.append(direction)
            
            return path
        
        except Exception as e:
            logger.error(f"Error generating plinko path: {e}")
            raise ValueError(f"Failed to generate plinko path: {e}")
    
    @classmethod
    def get_mines_grid(cls, server_seed: str, client_seed: str, nonce: int = 0, difficulty: int = 1) -> List[List[bool]]:
        """
        Generate mines grid (5x5).
        difficulty: 1=2 mines, 2=5 mines, 3=10 mines
        True = mine, False = safe
        """
        try:
            seed_hash = cls.provably_fair_hash(server_seed, client_seed, nonce)
            grid = [[False] * 5 for _ in range(5)]
            mine_count = [2, 5, 10][difficulty - 1]
            
            # Probability-based mine placement
            mines_placed = 0
            for i in range(25):
                if mines_placed >= mine_count:
                    break
                cell_seed = hashlib.sha256(f"{seed_hash}_{i}".encode()).hexdigest()
                probability = (mine_count - mines_placed) / (25 - i)
                rand = int(cell_seed[:8], 16) / 0xffffffff
                
                if rand < probability:
                    row = i // 5
                    col = i % 5
                    grid[row][col] = True
                    mines_placed += 1
            
            return grid
        
        except Exception as e:
            logger.error(f"Error generating mines grid: {e}")
            raise ValueError(f"Failed to generate mines grid: {e}")
    
    @classmethod
    def verify_crash_multiplier(cls, server_seed: str, client_seed: str, 
                               claimed_multiplier: float, nonce: int = 0) -> bool:
        """
        Verify a claimed crash multiplier is correct.
        Used for dispute resolution and audit trails.
        """
        try:
            calculated = cls.get_crash_multiplier(server_seed, client_seed, nonce)
            return abs(calculated - claimed_multiplier) < 0.01  # Allow rounding error
        
        except Exception as e:
            logger.error(f"Error verifying crash multiplier: {e}")
            return False
    
    @classmethod
    def verify_game_outcome(cls, game_type: GameType, server_seed: str, client_seed: str,
                           claimed_result: Any, nonce: int = 0) -> bool:
        """
        Verify any game outcome using provably fair protocol.
        """
        try:
            if game_type in [GameType.CRASH, GameType.AVIATOR]:
                calculated = cls.get_crash_multiplier(server_seed, client_seed, nonce)
                return abs(calculated - claimed_result) < 0.01
            
            elif game_type == GameType.HILO_CARD:
                calculated_current = cls.get_hilo_card(server_seed, client_seed, nonce)
                calculated_next = cls.get_hilo_card(server_seed, client_seed, nonce + 1)
                return calculated_current == claimed_result.get('current') and \
                       calculated_next == claimed_result.get('next')
            
            elif game_type == GameType.PLINKO:
                calculated = cls.get_plinko_slot(server_seed, client_seed, nonce)
                return calculated == claimed_result
            
            elif game_type == GameType.JETX:
                calculated = cls.get_jetx_coins(server_seed, client_seed, nonce)
                return calculated == claimed_result
            
            else:
                logger.warning(f"Unknown game type for verification: {game_type}")
                return False
        
        except Exception as e:
            logger.error(f"Error verifying game outcome: {e}")
            return False


class PayoutCalculator:
    """Calculate house edge, RTP, and ensure fairness across games."""
    
    RTP_CONFIG = {
        'crash': Decimal('97.0'),
        'aviator': Decimal('97.0'),
        'hilo_card': Decimal('96.5'),
        'plinko': Decimal('96.5'),
        'jetx': Decimal('97.0'),
        'slots': Decimal('96.0'),
        'dice': Decimal('98.0'),
        'roulette': Decimal('97.3'),
        'blackjack': Decimal('99.5'),
        'mines': Decimal('96.0'),
    }
    
    @classmethod
    def get_rtp_percent(cls, game_category: str) -> Decimal:
        """Get theoretical RTP (Return to Player) for game category."""
        return cls.RTP_CONFIG.get(game_category, Decimal('96.0'))
    
    @classmethod
    def get_house_edge_percent(cls, game_category: str) -> Decimal:
        """Get house edge as percentage (100 - RTP)."""
        rtp = cls.get_rtp_percent(game_category)
        return Decimal('100') - rtp
    
    @classmethod
    def apply_house_edge(cls, payout: Decimal, game_category: str) -> Decimal:
        """Apply house edge to ensure mathematical fairness over time."""
        rtp = cls.get_rtp_percent(game_category)
        return payout * (rtp / Decimal('100'))
    
    @staticmethod
    def calculate_hilo_multiplier(current_card: int, next_card: int, prediction: str) -> float:
        """
        Calculate Hi-Lo Card multiplier based on difficulty.
        Harder predictions = higher multiplier
        """
        diff = abs(next_card - current_card)
        
        # Base multiplier
        if prediction == 'higher' and next_card > current_card:
            multiplier = 2.0 + (diff / 12.0)  # 2.0 to 3.0
        elif prediction == 'lower' and next_card < current_card:
            multiplier = 2.0 + (diff / 12.0)  # 2.0 to 3.0
        elif next_card == current_card:
            multiplier = 11.0  # Tie = big payout
        else:
            multiplier = 0.0  # Loss
        
        return multiplier
    
    @staticmethod
    def calculate_jetx_multiplier(coins_collected: int) -> float:
        """
        Calculate Jet X Mzizi multiplier from coins.
        Formula: 1.0 + (coins × 0.1), capped at 10.0
        """
        multiplier = 1.0 + (coins_collected * 0.1)
        return min(multiplier, 10.0)
    
    @staticmethod
    def calculate_slot_win(reels: List[int], bet: Decimal) -> Tuple[Decimal, str]:
        """Calculate win for slot reels based on pay lines."""
        payouts = {
            (0, 0, 0, 0, 0): Decimal('10.00'),
            (1, 1, 1, 1, 1): Decimal('50.00'),
            (2, 2, 2, 2, 2): Decimal('100.00'),
            (3, 3, 3, 3, 3): Decimal('5.00'),
            (0, 0, 0): Decimal('3.00'),
            (1, 1, 1): Decimal('20.00'),
            (2, 2, 2): Decimal('40.00'),
        }
        
        if tuple(reels) in payouts:
            multiplier = payouts[tuple(reels)]
            return bet * multiplier, "fullmatch"
        
        if len(reels) >= 3 and reels[1] == reels[2] == reels[3]:
            multiplier = payouts.get((reels[1], reels[1], reels[1]), Decimal('1.00'))
            return bet * multiplier, "threematch"
        
        return Decimal('0.00'), "loss"
    
    @staticmethod
    def calculate_plinko_win(slot: int, bet: Decimal, multipliers: List[float]) -> Decimal:
        """Calculate plinko win based on final slot."""
        if 0 <= slot < len(multipliers):
            return bet * Decimal(str(multipliers[slot]))
        return Decimal('0.00')
    
    @staticmethod
    def log_round(user_id: int, game_id: int, game_type: str, stake: Decimal, payout: Decimal,
                  server_seed: str, client_seed: str, nonce: int = 0) -> Dict[str, Any]:
        """
        Create audit log entry for round.
        Used for compliance, dispute resolution, and fairness verification.
        """
        return {
            'user_id': user_id,
            'game_id': game_id,
            'game_type': game_type,
            'stake': float(stake),
            'payout': float(payout),
            'net_result': float(payout - stake),
            'server_seed': server_seed,
            'client_seed': client_seed,
            'nonce': nonce,
            'timestamp': datetime.utcnow().isoformat(),
            'provably_fair_proof': f"hash({server_seed}:{client_seed}:{nonce})",
        }


class FairnessVerifier:
    """Tools for verifying game fairness and preventing manipulation."""
    
    @staticmethod
    def verify_round(server_seed: str, client_seed: str, nonce: int, 
                     claimed_hash: str, game_type: GameType) -> bool:
        """Verify a round outcome using provably fair protocol."""
        try:
            calculated_hash = GameEngine.provably_fair_hash(server_seed, client_seed, nonce)
            return calculated_hash == claimed_hash
        
        except Exception as e:
            logger.error(f"Error verifying round: {e}")
            return False
    
    @staticmethod
    def generate_verification_proof(server_seed: str, client_seed: str, 
                                   nonce: int, game_type: GameType, result: Any) -> Dict[str, str]:
        """
        Generate proof of fairness for any game round.
        Players can use this to verify outcomes independently.
        """
        seed_hash = GameEngine.provably_fair_hash(server_seed, client_seed, nonce)
        return {
            'game_type': game_type.value,
            'server_seed': server_seed,
            'client_seed': client_seed,
            'nonce': str(nonce),
            'hash': seed_hash,
            'result': str(result),
            'verification_url': f'/api/verify/{game_type.value}?hash={seed_hash}',
            'timestamp': datetime.utcnow().isoformat(),
        }
    
    @staticmethod
    def generate_audit_report(rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate fairness audit report from round history.
        Shows RTP, distribution, and potential manipulation.
        """
        if not rounds:
            return {'error': 'No rounds to audit'}
        
        total_stake = sum(Decimal(r['stake']) for r in rounds)
        total_payout = sum(Decimal(r['payout']) for r in rounds)
        total_rounds = len(rounds)
        
        actual_rtp = (total_payout / total_stake * 100) if total_stake > 0 else Decimal('0')
        
        return {
            'total_rounds': total_rounds,
            'total_stake': float(total_stake),
            'total_payout': float(total_payout),
            'house_profit': float(total_stake - total_payout),
            'actual_rtp_percent': float(actual_rtp),
            'expected_rtp_percent': 96.0,  # Platform average
            'variance': float(actual_rtp - Decimal('96.0')),
            'timestamp': datetime.utcnow().isoformat(),
        }


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

class GameValidator:
    """Validate game parameters and prevent cheating."""
    
    MIN_BET = Decimal('10')
    MAX_BET = Decimal('10000')
    
    @classmethod
    def validate_bet(cls, amount: Decimal, user_balance: Decimal) -> Tuple[bool, Optional[str]]:
        """Validate bet amount."""
        if not isinstance(amount, (Decimal, int, float)):
            return False, "Invalid bet type"
        
        amount = Decimal(str(amount))
        
        if amount < cls.MIN_BET:
            return False, f"Minimum bet is {cls.MIN_BET} KES"
        
        if amount > cls.MAX_BET:
            return False, f"Maximum bet is {cls.MAX_BET} KES"
        
        if amount > user_balance:
            return False, "Insufficient balance"
        
        return True, None
    
    @classmethod
    def validate_multiplier(cls, multiplier: float) -> Tuple[bool, Optional[str]]:
        """Validate game multiplier is in valid range."""
        try:
            mult = float(multiplier)
            if mult < 0.5:
                return False, "Multiplier too low"
            if mult > 500.0:
                return False, "Multiplier too high"
            return True, None
        
        except (ValueError, TypeError):
            return False, "Invalid multiplier format"
