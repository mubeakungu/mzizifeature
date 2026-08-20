"""Single source of truth for how catalog games are launched.

The catalog slug is the stable public identifier. Every self-hosted game has
exactly one canonical template/route here. The casino lobby must not contain
another implementation of a game in JavaScript.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GameDefinition:
    slug: str
    template: Optional[str] = None
    route: Optional[str] = None
    kind: str = "self_hosted"  # self_hosted | redirect | provider
    namespace: Optional[str] = None


GAME_REGISTRY = {
    # Real-time games: their dedicated blueprints own the game loop + API.
    "mzizicrash": GameDefinition(
        slug="mzizicrash", route="/crash/", kind="redirect", namespace="/crash"
    ),
    "aviatormzizi": GameDefinition(
        slug="aviatormzizi", route="/aviator-mzizi/", kind="redirect", namespace="/aviator-mzizi"
    ),
    "jetx": GameDefinition(
        slug="jetx", route="/jetx/", kind="redirect", namespace="/jetx"
    ),
    "hilocard": GameDefinition(
        slug="hilocard", route="/hi-lo-card/", kind="redirect", namespace="/hi-lo-card"
    ),
    "plinkomzizi": GameDefinition(
        slug="plinkomzizi", route="/plinko-mzizi/", kind="redirect", namespace="/plinko-mzizi"
    ),

    # HTTP/API games: their dedicated templates are the canonical UI and
    # /api/casino is the canonical settlement API.
    "dice": GameDefinition(slug="dice", template="games/dice.html"),
    "european-roulette": GameDefinition(
        slug="european-roulette", template="games/european-roulette.html"
    ),
    "mines": GameDefinition(slug="mines", template="games/mines.html"),
    "slots": GameDefinition(slug="slots", template="games/slots.html"),
}


def get_game_definition(slug: str) -> Optional[GameDefinition]:
    return GAME_REGISTRY.get(slug)


def is_canonical_game(slug: str) -> bool:
    return slug in GAME_REGISTRY
