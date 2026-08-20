"""
FIXED v5: Catalog now only lists games that have a real, working HTML
template/route in app/templates/games/ — no more placeholder tiles that
404 (Golden Pharaoh, Fortune Tiger, Live Baccarat, jackpot placeholders,
etc. have all been removed since they have no matching engine).

Real games confirmed against app/templates/games/:
  mzizicrash.html, aviatormzizi.html, jetx.html, mines.html, dice.html,
  european-roulette.html, hilocard.html, plinkomzizi.html, slots.html

Thumbnails still come from the Unsplash Search API (one distinct,
hand-written query per game), with a generated SVG fallback if
UNSPLASH_ACCESS_KEY isn't set or the API call fails.

Setup:
  1. Get a free Unsplash API key: https://unsplash.com/developers
     (Demo tier: 50 requests/hour)
  2. Set UNSPLASH_ACCESS_KEY in your environment / Render env vars.
  3. Run: python seed_fixed.py
"""
import base64
import hashlib
import logging
import os
import time

import requests

from app.extensions import db
from app.models.casino import GameCategory, Game

logger = logging.getLogger(__name__)

UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"

# ============================================
# PER-GAME SEARCH QUERIES (only real, templated games)
# ============================================

GAME_IMAGE_QUERIES = {
    "mzizicrash": "crash game multiplier flying",
    "aviatormzizi": "airplane wing sky flight",
    "jetx": "military jet cockpit speed",
    "mines": "minefield warning explosive",
    "dice": "dice red casino",
    "european-roulette": "roulette wheel numbers casino",
    "hilocard": "playing cards stack",
    "plinkomzizi": "pachinko pinball lights",
    "slots": "slot machine reels neon casino",
}

CATEGORIES = [
    ("Crash Games", "crash", 1),
    ("Table Games", "table", 2),
    ("Slots", "slots", 3),
]

# Games: (name, slug, category, badge, rtp)
GAMES = [
    # --- Crash Games ---
    ("mzizicrash", "mzizicrash", "crash", "HOT", None),
    ("Aviator", "aviatormzizi", "crash", "HOT", None),
    ("JetX", "jetx", "crash", "HOT", None),
    ("Mines", "mines", "crash", "POPULAR", None),

    # --- Table Games ---
    ("Dice", "dice", "table", None, 98.5),
    ("European Roulette", "european-roulette", "table", None, 97.3),
    ("Hi-Lo", "hilocard", "table", None, 97.5),
    ("Plinko", "plinkomzizi", "table", "HOT", 97.0),

    # --- Slots ---
    ("Slots", "slots", "slots", "HOT", 96.0),
]


# ============================================
# SVG FALLBACK (used if Unsplash is unavailable / unconfigured)
# ============================================

PALETTE = [
    ("#7C3AED", "#4C1D95"), ("#0EA5E9", "#075985"), ("#F59E0B", "#92400E"),
    ("#10B981", "#065F46"), ("#EF4444", "#7F1D1D"), ("#EC4899", "#831843"),
    ("#22D3EE", "#155E75"), ("#84CC16", "#365314"), ("#F97316", "#7C2D12"),
    ("#8B5CF6", "#5B21B6"),
]

CATEGORY_ICON_SVG = {
    "crash": """<g transform="translate(200,250)">
      <path d="M0,-120 C40,-70 45,-10 30,50 L-30,50 C-45,-10 -40,-70 0,-120 Z" fill="#fff" opacity="0.95"/>
      <circle cx="0" cy="-40" r="14" fill="#0891b2"/>
      <path d="M-30,50 L-55,95 L-15,80 Z" fill="#fff" opacity="0.85"/>
      <path d="M30,50 L55,95 L15,80 Z" fill="#fff" opacity="0.85"/>
      <path d="M-12,55 L0,110 L12,55 Z" fill="#fde047"/></g>""",
    "slots": "".join(
        f'<rect x="{x}" y="150" width="70" height="200" rx="10" fill="#fff" opacity="0.95"/>'
        f'<text x="{x+35}" y="270" font-size="60" text-anchor="middle" fill="#111827" '
        f'font-family="Arial">{sym}</text>'
        for x, sym in [(85, "7"), (165, "\u2605"), (245, "$")]
    ),
    "table": """<g transform="translate(200,250)">
      <rect x="-70" y="-70" width="100" height="140" rx="10" fill="#fff" opacity="0.95" transform="rotate(-12)"/>
      <rect x="-30" y="-70" width="100" height="140" rx="10" fill="#fff" opacity="0.95" transform="rotate(8)"/>
      <text x="0" y="12" font-size="46" text-anchor="middle" fill="#dc2626" font-family="Arial">&#9829;</text></g>""",
}


def _svg_fallback(slug: str, category_slug: str) -> str:
    idx = int(hashlib.md5(slug.encode()).hexdigest(), 16) % len(PALETTE)
    c1, c2 = PALETTE[idx]
    icon = CATEGORY_ICON_SVG.get(category_slug, CATEGORY_ICON_SVG["slots"])
    grad_id = f"g_{slug.replace('-', '_')}"
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500">'
        f'<defs><linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/>'
        f'</linearGradient></defs>'
        f'<rect width="400" height="500" rx="18" fill="url(#{grad_id})"/>{icon}</svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


# ============================================
# UNSPLASH LOOKUP
# ============================================

def _fetch_unsplash_photo(query: str):
    """Search Unsplash for one relevant photo. Returns a cropped image URL,
    or None if unavailable/failed."""
    if not UNSPLASH_ACCESS_KEY:
        return None
    try:
        resp = requests.get(
            UNSPLASH_SEARCH_URL,
            params={"query": query, "per_page": 1, "orientation": "portrait"},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=8,
        )
        if resp.status_code != 200:
            logger.warning(f"  ⚠️  Unsplash {resp.status_code} for '{query}': {resp.text[:200]}")
            return None
        results = resp.json().get("results", [])
        if not results:
            logger.warning(f"  ⚠️  No Unsplash results for '{query}'")
            return None
        raw_url = results[0]["urls"]["raw"]
        return f"{raw_url}&w=400&h=500&fit=crop&q=80"
    except Exception as e:
        logger.warning(f"  ⚠️  Unsplash lookup failed for '{query}': {e}")
        return None


def get_thumbnail_url(slug: str, category_slug: str) -> str:
    query = GAME_IMAGE_QUERIES.get(slug)
    if query:
        photo_url = _fetch_unsplash_photo(query)
        if photo_url:
            return photo_url
        logger.warning(f"  ↳ falling back to generated thumbnail for {slug}")
    return _svg_fallback(slug, category_slug)


# ============================================
# SEED
# ============================================

def run(force=False):
    """Seed catalog data with per-game Unsplash photos (SVG fallback)."""
    if not force and Game.query.count() > 0:
        return False

    if not UNSPLASH_ACCESS_KEY:
        logger.warning(
            "⚠️  UNSPLASH_ACCESS_KEY not set — all thumbnails will use the "
            "generated SVG fallback. Get a free key at https://unsplash.com/developers"
        )

    slug_to_cat = {}
    for name, slug, order in CATEGORIES:
        cat = GameCategory.query.filter_by(slug=slug).first()
        if not cat:
            cat = GameCategory(name=name, slug=slug, display_order=order)
            db.session.add(cat)
            db.session.flush()
        slug_to_cat[slug] = cat

    for i, (name, slug, cat_slug, badge, rtp) in enumerate(GAMES):
        existing = Game.query.filter_by(slug=slug).first()
        if existing and not force:
            continue

        thumbnail_url = get_thumbnail_url(slug, cat_slug)
        if UNSPLASH_ACCESS_KEY:
            time.sleep(0.3)

        if existing:
            existing.thumbnail_url = thumbnail_url
            continue

        db.session.add(Game(
            name=name,
            slug=slug,
            category_id=slug_to_cat[cat_slug].id,
            badge=badge,
            rtp_percent=rtp,
            thumbnail_url=thumbnail_url,
            display_order=i,
            is_active=True,
        ))

    db.session.commit()
    return True


if __name__ == "__main__":
    from app import create_app

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    app = create_app("development")
    with app.app_context():
        db.create_all()
        if run(force=True):
            print(f"✅ Seeded {len(CATEGORIES)} categories and {len(GAMES)} games.")
        else:
            print("⚠️  Catalog already populated — use run(force=True) to reseed.")
