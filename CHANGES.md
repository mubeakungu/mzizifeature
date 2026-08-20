# mzizibet-updates — what's in here and how to deploy

## 1. mzizicrash — restyled UI, same backend
Drop-in replace:
    app/templates/games/crash_game.html

Nothing else changes for this game — your wallet debits/credits, provably-fair
engine, auto-cashout, stats, and bet history are all untouched. Only the
look changed (big pulsing multiplier + crash-history strip instead of the
Chart.js graph, matching the crash-game-main visual style).

## 2. Aviator + JetX — replaced by the Unity "aviator-crash-main" game
Both old demo blueprints (aviatormzizi_blueprint.py, jetx_blueprint.py) are
now REPLACED by one real, wallet-integrated, provably-fair backend that
drives the Unity WebGL plane. `/aviator-mzizi/` and `/jetx/` both serve the
exact same game now — same as before, nothing in your lobby/nav needs to
change since those URLs are unchanged.

Drop-in replace / add:
    app/__init__.py                          (replace — registers the new
                                               blueprints instead of the old
                                               aviator/jetx ones)
    app/models/aviatorcrash_models.py        (new)
    app/routes/aviatorcrash_blueprint.py     (new — the whole game engine)
    app/static/aviatorcrash/                 (new — built React+Unity bundle,
                                               ~7MB, copy the whole folder)

You can leave app/routes/aviatormzizi_blueprint.py and jetx_blueprint.py in
the repo untouched — app/__init__.py no longer imports or registers them,
so they're just dead code. Same for the old JetXGame/JetXBet/JetXStats and
inline AviatorRound/AviatorBet/AviatorStats tables — they're simply unused
now; no migration needed to remove them.

### What's real vs. what to know
- Payouts are computed **server-side** from elapsed time on the same curve
  the Unity animation uses — the client's own multiplier claim (`endTarget`)
  is never trusted for money.
- The "Top" leaderboard tab (day/month/year) is backed by real data too —
  `/api/get-day-history` etc. return each winner's real masked name and
  avatar (`w***1`, not the template's original hardcoded `d***3` for every
  row). I fixed that in both the backend query and the React source, then
  rebuilt the bundle.
- Provably-fair: SHA-256(server_seed:round_number), ~3% house edge, same
  family of algorithm as your other games.
- Dual bet slots (f/s) per round, independent auto-cashout targets, exactly
  matching the original frontend's protocol.
- Round loop: 5s betting window → live (until crash) → 3s pause showing the
  crash point → repeat.
- Known simplification: if a player has this game open in two browser tabs
  at once, closing one tab can stop personalized events (`finishGame`) to
  the other until they re-open the page. Doesn't affect wallet correctness,
  only that one edge-case UI refresh.

### Deploy
This zip is your complete mzizibet-main repo with everything already applied
— unzip it over (or in place of) your existing project and push. No manual
file-copying needed.

1. Replace your working copy with this folder (or diff/merge if you have
   local changes elsewhere), then:
   `git add -A && git commit -m "Restyle mzizicrash, replace aviator/jetx with aviator-crash-main" && git push`
2. Render will pick it up. `db.create_all()` in your app factory creates the
   three new tables (`aviatorcrash_rounds`, `aviatorcrash_bets`,
   `aviatorcrash_stats`) automatically on boot — no manual migration needed.
3. The old `app/routes/aviatormzizi_blueprint.py` and `jetx_blueprint.py`
   files are still present but unused (app/__init__.py no longer imports or
   registers them) — safe to delete later, or leave as dead code.

I load- and protocol-tested the whole flow locally (connect → bet → live
round → cashout → crash → lost bet → stats/history/finishGame) before
packaging this — it's not just written, it runs.
