# Mzizibet

Flask scaffold for a real-money casino + sports betting platform, built with
your usual stack (Flask app factory, PostgreSQL via SQLAlchemy, Jinja2,
M-Pesa Daraja for deposits, cPanel/Render-ready).

## What's here

- **Auth** — registration with DOB capture and an 18+ gate, login, session
  management (Flask-Login).
- **Wallet** — balance ledger, M-Pesa STK Push deposit flow (skeleton —
  see below), transaction history.
- **Casino lobby** — category tabs, search, game grid matching the Mzizibet
  brand. Catalog only; see "Before going live" below.
- **Sports lobby** — fixture list with market/odds display, ready to be
  populated from a live odds feed.
- **Admin** — role-gated dashboard (admin/CEO) with user and transaction
  overview.
- **Responsible gambling hooks** — `User.can_play()` centralizes age,
  self-exclusion, and account-status checks; `DEFAULT_DAILY_DEPOSIT_LIMIT`
  in config.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your real values
flask db init && flask db migrate -m "init" && flask db upgrade
python seed.py          # demo game catalog + categories
python run.py
```

## Before going live — read this

This scaffold deliberately does **not** implement:

1. **Casino game RNG / payout logic.** Real-money slots, crash games, and
   table games need a certified, independently audited RNG — regulators
   (BCLB included) expect this to come from a licensed game provider or
   aggregator, not custom code. `Game.provider_name` /
   `Game.provider_game_code` are the integration points; `casino_play.html`
   has a marked spot for the provider's signed game-launch iframe.

2. **Sports odds compilation.** `SportsEvent` / `SportsMarket` /
   `SportsSelection` are shaped to be populated from a licensed odds feed.
   Don't hand-set odds for real-money markets.

3. **M-Pesa STK Push credentials and callback verification.** The flow in
   `app/routes/wallet.py` follows the same pattern as your Ufanisi Sacco
   integration (build password from shortcode+passkey+timestamp, POST to
   Daraja, credit wallet only from a verified callback matched to a pending
   `Transaction` by `CheckoutRequestID`) — plug in your production
   credentials and finish the callback verification before handling real
   money.

4. **KYC verification workflow.** `User.national_id` and `kyc_verified`
   exist as fields; you'll want an actual ID-verification step (manual or
   via a KYC provider) gating withdrawals, per BCLB requirements.

5. **BCLB compliance items generally** — self-exclusion is scaffolded
   (`is_self_excluded`, `self_exclusion_until`) but you'll want a user-facing
   self-exclusion flow, deposit-limit controls the player can set
   themselves, and responsible-gambling messaging/links in the footer
   (already stubbed) pointing to real resources.

## Structure

```
mzizibet/
  app/
    models/        user, wallet, casino, sports
    routes/        auth, casino, sports, wallet, admin
    templates/      base + per-section pages
    static/css/     design system (style.css)
  config.py
  run.py
  seed.py           demo catalog data
```
