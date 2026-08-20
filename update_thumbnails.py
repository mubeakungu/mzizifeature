"""
Updates existing games with thumbnail URLs.
Run with: python update_thumbnails.py
"""
from app.extensions import db
from app.models.casino import Game

GAME_IMAGES = {
    # Crash Games
    "aviator": "https://placehold.co/400x500?text=Aviator&font=raleway&bg=1a1a2e&textbg=0f3460",
    "jet-crash": "https://placehold.co/400x500?text=Jet+Crash&font=raleway&bg=16213e&textbg=0f3460",
    "moon-crash": "https://placehold.co/400x500?text=Moon+Crash&font=raleway&bg=0f3460&textbg=16213e",
    "mines": "https://placehold.co/400x500?text=Mines&font=raleway&bg=1a1a2e&textbg=e94560",
    "rocket-x": "https://placehold.co/400x500?text=Rocket+X&font=raleway&bg=16213e&textbg=0f3460",
    "cash-blast": "https://placehold.co/400x500?text=Cash+Blast&font=raleway&bg=0f3460&textbg=16213e",
    "sky-rider": "https://placehold.co/400x500?text=Sky+Rider&font=raleway&bg=1a1a2e&textbg=e94560",
    "meteor-rush": "https://placehold.co/400x500?text=Meteor+Rush&font=raleway&bg=16213e&textbg=0f3460",
    "multiplier-mania": "https://placehold.co/400x500?text=Multiplier+Mania&font=raleway&bg=0f3460&textbg=16213e",
    "balloon-burst": "https://placehold.co/400x500?text=Balloon+Burst&font=raleway&bg=1a1a2e&textbg=e94560",
    "zeppelin": "https://placehold.co/400x500?text=Zeppelin&font=raleway&bg=16213e&textbg=0f3460",
    "comet-crash": "https://placehold.co/400x500?text=Comet+Crash&font=raleway&bg=0f3460&textbg=16213e",

    # Table Games
    "plinko": "https://placehold.co/400x500?text=Plinko&font=raleway&bg=1a472a&textbg=2d5a3d",
    "dice": "https://placehold.co/400x500?text=Dice&font=raleway&bg=2d5a3d&textbg=1a472a",
    "limbo": "https://placehold.co/400x500?text=Limbo&font=raleway&bg=1a472a&textbg=2d5a3d",
    "wheel-of-fortune": "https://placehold.co/400x500?text=Wheel+of+Fortune&font=raleway&bg=2d5a3d&textbg=1a472a",
    "blackjack-classic": "https://placehold.co/400x500?text=Blackjack&font=raleway&bg=1a472a&textbg=2d5a3d",
    "european-roulette": "https://placehold.co/400x500?text=EU+Roulette&font=raleway&bg=2d5a3d&textbg=1a472a",
    "american-roulette": "https://placehold.co/400x500?text=US+Roulette&font=raleway&bg=1a472a&textbg=2d5a3d",
    "baccarat-pro": "https://placehold.co/400x500?text=Baccarat+Pro&font=raleway&bg=2d5a3d&textbg=1a472a",
    "three-card-poker": "https://placehold.co/400x500?text=3+Card+Poker&font=raleway&bg=1a472a&textbg=2d5a3d",
    "caribbean-stud": "https://placehold.co/400x500?text=Caribbean+Stud&font=raleway&bg=2d5a3d&textbg=1a472a",
    "craps-table": "https://placehold.co/400x500?text=Craps&font=raleway&bg=1a472a&textbg=2d5a3d",
    "hi-lo": "https://placehold.co/400x500?text=Hi-Lo&font=raleway&bg=2d5a3d&textbg=1a472a",
    "keno": "https://placehold.co/400x500?text=Keno&font=raleway&bg=1a472a&textbg=2d5a3d",
    "video-poker": "https://placehold.co/400x500?text=Video+Poker&font=raleway&bg=2d5a3d&textbg=1a472a",

    # Slots
    "golden-pharaoh": "https://placehold.co/400x500?text=Golden+Pharaoh&font=raleway&bg=4a3728&textbg=7a5c42",
    "spin-win": "https://placehold.co/400x500?text=Spin+%26+Win&font=raleway&bg=7a5c42&textbg=4a3728",
    "arcade-classic": "https://placehold.co/400x500?text=Arcade+Classic&font=raleway&bg=4a3728&textbg=7a5c42",
    "lucky-savana": "https://placehold.co/400x500?text=Lucky+Savana&font=raleway&bg=7a5c42&textbg=4a3728",
    "diamond-rush": "https://placehold.co/400x500?text=Diamond+Rush&font=raleway&bg=4a3728&textbg=7a5c42",
    "wild-jungle": "https://placehold.co/400x500?text=Wild+Jungle&font=raleway&bg=7a5c42&textbg=4a3728",
    "fortune-tiger": "https://placehold.co/400x500?text=Fortune+Tiger&font=raleway&bg=4a3728&textbg=7a5c42",
    "sugar-rush-reels": "https://placehold.co/400x500?text=Sugar+Rush&font=raleway&bg=7a5c42&textbg=4a3728",
    "book-of-mysteries": "https://placehold.co/400x500?text=Book+of+Mysteries&font=raleway&bg=4a3728&textbg=7a5c42",
    "fruit-frenzy": "https://placehold.co/400x500?text=Fruit+Frenzy&font=raleway&bg=7a5c42&textbg=4a3728",
    "pirates-treasure": "https://placehold.co/400x500?text=Pirates+Treasure&font=raleway&bg=4a3728&textbg=7a5c42",
    "viking-legends": "https://placehold.co/400x500?text=Viking+Legends&font=raleway&bg=7a5c42&textbg=4a3728",
    "mystic-forest": "https://placehold.co/400x500?text=Mystic+Forest&font=raleway&bg=4a3728&textbg=7a5c42",
    "cleopatras-gold": "https://placehold.co/400x500?text=Cleopatras+Gold&font=raleway&bg=7a5c42&textbg=4a3728",
    "samurai-storm": "https://placehold.co/400x500?text=Samurai+Storm&font=raleway&bg=4a3728&textbg=7a5c42",
    "candy-kingdom-riches": "https://placehold.co/400x500?text=Candy+Kingdom&font=raleway&bg=7a5c42&textbg=4a3728",
    "aztec-gold": "https://placehold.co/400x500?text=Aztec+Gold&font=raleway&bg=4a3728&textbg=7a5c42",
    "starlight-spins": "https://placehold.co/400x500?text=Starlight+Spins&font=raleway&bg=7a5c42&textbg=4a3728",
    "dragons-fortune": "https://placehold.co/400x500?text=Dragons+Fortune&font=raleway&bg=4a3728&textbg=7a5c42",
    "safari-kingdom": "https://placehold.co/400x500?text=Safari+Kingdom&font=raleway&bg=7a5c42&textbg=4a3728",
    "neon-nights": "https://placehold.co/400x500?text=Neon+Nights&font=raleway&bg=4a3728&textbg=7a5c42",
    "gold-rush-deluxe": "https://placehold.co/400x500?text=Gold+Rush&font=raleway&bg=7a5c42&textbg=4a3728",
    "mummys-curse": "https://placehold.co/400x500?text=Mummys+Curse&font=raleway&bg=4a3728&textbg=7a5c42",
    "wild-west-bounty": "https://placehold.co/400x500?text=Wild+West&font=raleway&bg=7a5c42&textbg=4a3728",
    "ocean-riches": "https://placehold.co/400x500?text=Ocean+Riches&font=raleway&bg=4a3728&textbg=7a5c42",
    "phoenix-fire": "https://placehold.co/400x500?text=Phoenix+Fire&font=raleway&bg=7a5c42&textbg=4a3728",

    # Live Casino
    "neon-roulette": "https://placehold.co/400x500?text=Neon+Roulette&font=raleway&bg=2d1b4e&textbg=5a3a8a",
    "texas-holdem": "https://placehold.co/400x500?text=Texas+Holdem&font=raleway&bg=5a3a8a&textbg=2d1b4e",
    "live-blackjack-vip": "https://placehold.co/400x500?text=Live+Blackjack&font=raleway&bg=2d1b4e&textbg=5a3a8a",
    "live-baccarat": "https://placehold.co/400x500?text=Live+Baccarat&font=raleway&bg=5a3a8a&textbg=2d1b4e",
    "speed-roulette": "https://placehold.co/400x500?text=Speed+Roulette&font=raleway&bg=2d1b4e&textbg=5a3a8a",
    "dream-wheel": "https://placehold.co/400x500?text=Dream+Wheel&font=raleway&bg=5a3a8a&textbg=2d1b4e",
    "live-sic-bo": "https://placehold.co/400x500?text=Live+Sic+Bo&font=raleway&bg=2d1b4e&textbg=5a3a8a",
    "andar-bahar-live": "https://placehold.co/400x500?text=Andar+Bahar&font=raleway&bg=5a3a8a&textbg=2d1b4e",
    "live-dragon-tiger": "https://placehold.co/400x500?text=Dragon+Tiger&font=raleway&bg=2d1b4e&textbg=5a3a8a",
    "casino-holdem-live": "https://placehold.co/400x500?text=Casino+Holdem&font=raleway&bg=5a3a8a&textbg=2d1b4e",

    # Jackpots
    "jackpot-city": "https://placehold.co/400x500?text=Jackpot+City&font=raleway&bg=4a2c1a&textbg=8b5a2b",
    "mega-millions-slots": "https://placehold.co/400x500?text=Mega+Millions&font=raleway&bg=8b5a2b&textbg=4a2c1a",
    "progressive-fortune": "https://placehold.co/400x500?text=Progressive&font=raleway&bg=4a2c1a&textbg=8b5a2b",
    "diamond-jackpot": "https://placehold.co/400x500?text=Diamond+Jackpot&font=raleway&bg=8b5a2b&textbg=4a2c1a",
    "millionaires-row": "https://placehold.co/400x500?text=Millionaires+Row&font=raleway&bg=4a2c1a&textbg=8b5a2b",
    "golden-jackpot-wheel": "https://placehold.co/400x500?text=Golden+Jackpot&font=raleway&bg=8b5a2b&textbg=4a2c1a",
    "super-jackpot-slots": "https://placehold.co/400x500?text=Super+Jackpot&font=raleway&bg=4a2c1a&textbg=8b5a2b",
    "vault-breaker": "https://placehold.co/400x500?text=Vault+Breaker&font=raleway&bg=8b5a2b&textbg=4a2c1a",
}


def run():
    """Update all existing games with thumbnail URLs."""
    updated = 0
    for slug, url in GAME_IMAGES.items():
        game = Game.query.filter_by(slug=slug).first()
        if game:
            game.thumbnail_url = url
            updated += 1
    
    db.session.commit()
    return updated


if __name__ == "__main__":
    from app import create_app

    app = create_app("development")
    with app.app_context():
        count = run()
        print(f"Updated {count} games with thumbnail URLs.")
