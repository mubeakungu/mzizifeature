# Mzizibet Game Architecture

## Canonical rule
Each catalog slug has one implementation. The catalog never embeds a second
client-side version of a game.

## Registry
`app/games/registry.py` is the single source of truth for game launch routing.

| Slug | Canonical implementation | Transport |
|---|---|---|
| `mzizicrash` | `app/routes/mzizicrash_blueprint.py` + `games/crash_game.html` | Socket.IO + HTTP |
| `aviatormzizi` | `app/routes/aviatormzizi_blueprint.py` + `games/aviatormzizi.html` | Socket.IO + HTTP |
| `jetx` | `app/routes/jetx_blueprint.py` + `games/jetx.html` | Socket.IO + HTTP |
| `hilocard` | `app/routes/hilocard_blueprint.py` + `games/hilocard.html` | HTTP |
| `plinkomzizi` | `app/routes/plinkomzizi_blueprint.py` + `games/plinkomzizi.html` | Socket.IO + HTTP |
| `dice` | `games/dice.html` + `/api/casino/*` | HTTP |
| `european-roulette` | `games/european-roulette.html` + `/api/casino/*` | HTTP |
| `mines` | `games/mines.html` + `/api/casino/*` | HTTP |
| `slots` | `games/slots.html` + `/api/casino/*` | HTTP |

## Removed duplication
- Removed the generic fake game implementations from `casino_play.html`.
- Removed unused duplicate `casino_blueprint.py`.
- Removed duplicate root templates for crash, cards and JetX.
- Moved game JavaScript assets out of `static/css/` into `static/js/games/`.
- Removed `__pycache__` from the source package.

## Security/logic rule
The browser is a UI client only. Outcomes, wallet debits, payouts and round
state must remain authoritative on the server. Never use `Math.random()` in a
production game UI to decide a wager outcome.

## Next UI phase
The next step is to introduce a shared responsive game shell/partial so all
canonical game templates use the same desktop/mobile header, game field,
betting panel, balance area, history and navigation without duplicating the
actual game engine.
