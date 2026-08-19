# Mzizibet Feature Pack — Integration Guide

What this is: seven features ported from the purchased Laravel template into
your existing Flask/PostgreSQL app, written to match your app-factory +
blueprint pattern. No PHP, no MySQL — pure Flask, using your existing
`db.create_all()` startup flow. All new tables, zero `ALTER TABLE` on
anything that already exists (including `users`), so this is safe to drop
in without a manual migration step.

## What's new
- KYC document upload + admin review queue
- Support ticket system (user + admin)
- Admin roles & permissions (layered on your existing `User.role` string —
  doesn't touch the users table)
- Referral program (code, signup bonus, admin-configurable)
- CMS content pages (Terms/Privacy/FAQ/etc, editable in admin, no redeploy)
- In-app notifications bell
- SMS/email message templates (editable copy, no redeploy)
- Payment gateway admin config (limits/fees/on-off toggle; your Daraja
  credentials stay in env vars — this doesn't touch those)

## How to install

1. **Copy every file in this pack into the matching path in your repo.**
   These are complete files — overwrite `app/__init__.py`,
   `app/routes/auth.py`, and `app/templates/base.html`; everything else is
   new, so it just adds files.

   ```
   app/models/kyc.py                    (new)
   app/models/support.py                (new)
   app/models/rbac.py                   (new)
   app/models/referral.py               (new)
   app/models/content.py                (new)
   app/models/notification.py           (new)
   app/models/gateway.py                (new)
   app/routes/kyc.py                    (new)
   app/routes/support.py                (new)
   app/routes/referral.py               (new)
   app/routes/content.py                (new)
   app/routes/notifications.py          (new)
   app/routes/admin_extra.py            (new)
   app/routes/admin.py                  (UNCHANGED — leave as is)
   app/routes/auth.py                   (OVERWRITE — adds referral capture + notify/SMS)
   app/routes/wallet.py                 (OVERWRITE — adds gateway limit checks)
   app/services/messaging.py            (new — templated SMS dispatch, see below)
   app/__init__.py                      (OVERWRITE — registers everything)
   app/templates/base.html              (OVERWRITE — adds bell/referral/support icons)
   app/templates/admin/*.html           (new)
   app/templates/kyc/upload.html        (new)
   app/templates/support/*.html         (new)
   app/templates/referral/dashboard.html(new)
   app/templates/content/page.html      (new)
   app/templates/notifications/list.html(new)
   ```

2. **Create the upload folder** (or let it auto-create — `kyc.py` calls
   `os.makedirs(..., exist_ok=True)` on first upload, but on some hosts
   the app user won't have write permission to a fresh path, so it's
   worth creating it explicitly):
   ```
   mkdir -p app/static/uploads/kyc
   ```
   On cPanel/Render, make sure this path is in a **persistent** volume —
   Render's ephemeral filesystem wipes on redeploy, so for production KYC
   images you'll eventually want to point `_save()` in `app/routes/kyc.py`
   at S3/Cloudinary instead of local disk. Fine for testing as-is.

3. **Deploy / restart.** On next boot, `db.create_all()` creates all the
   new tables automatically (your existing pattern), and the new seed
   functions populate:
   - Default roles (`ceo`, `admin`, `support`, `player`) with sensible
     starting permissions
   - Default SMS templates (kyc_approved, kyc_rejected,
     withdrawal_processed, referral_bonus, ticket_reply)
   - Default gateway rows for `mpesa_stk` (deposit) and `mpesa_b2c`
     (withdrawal) with placeholder limits — **go set the real min/max/fees
     in Admin → Gateways before relying on them for anything.**

4. **Nothing is wired into enforcement yet** — on purpose. Specifically:
   - `PaymentGateway.in_range()` / `.fee_for()` exist but your existing
     M-Pesa deposit/withdraw routes don't call them yet. Wire that in once
     you've reviewed the limits.
   - `MessageTemplate.render()` exists but nothing calls it yet — your
     existing Africa's Talking SMS calls still use whatever strings they
     already had. Swap those call sites to pull from
     `MessageTemplate.query.filter_by(code=...).first().render(...)`
     when you're ready.
   - The `notify()` helper in `app/routes/notifications.py` is ready to
     call from anywhere (e.g. after a KYC approval, a withdrawal
     completing) but I haven't sprinkled calls to it through your existing
     wallet/game code — that's a good next pass once you've smoke-tested
     this batch.

## Testing checklist before this touches real money

- [ ] Register a new account with `/auth/register?ref=<existing_user_code>`
      and confirm the referrer's wallet balance increases by the configured
      signup bonus (set one first in Admin → Referrals — it defaults to 0).
- [ ] Upload a KYC submission as a test user, approve it from
      Admin → KYC, confirm `kyc_verified` flips and withdrawals unlock.
- [ ] Reject a KYC submission with a reason, confirm the user sees the
      reason and can resubmit.
- [ ] Open a support ticket as a user, reply as admin, confirm status
      transitions (open → pending → resolved) work both directions.
- [ ] As a `support`-role account, confirm you're blocked (403) from
      Admin → Roles and Admin → Gateways, but can reach Admin → KYC and
      Admin → Support — that's the default permission split.
- [ ] Publish a content page (e.g. slug `terms`) and confirm
      `/page/terms` renders and unpublished pages 404.
- [ ] Confirm the notification bell badge count matches unread rows, and
      clears after visiting `/notifications/`.

## Enforcement — now wired in

- **`app/routes/wallet.py` (OVERWRITE)** — the deposit route now checks the
  `mpesa_stk` `PaymentGateway` row for active/min/max before accepting a
  deposit amount, and computes the fee via `gateway.fee_for(amount)`. The
  actual STK Push call is still the same stub it always was (pending your
  Daraja go-live creds) — this only adds the admin-configurable guardrails
  in front of it.
- **`app/services/messaging.py` (new)** — a `send_templated(code, phone, **vars)`
  helper that looks up a `MessageTemplate` by code and renders it.
  `_dispatch_sms()` inside it is a **stub that logs instead of sending** —
  this repo snapshot doesn't include the Africa's Talking client from your
  other Mzizibet sessions. Swap that one function's body for your existing
  `africastalking` call and every call site below starts actually texting
  people.
- **Wired call sites**:
  - KYC approve/reject (`admin_extra.py`) → in-app notification + SMS via
    `kyc_approved` / `kyc_rejected` templates.
  - Support ticket admin reply (`admin_extra.py`) → notification + SMS via
    `ticket_reply` template.
  - Referral signup bonus (`auth.py`) → notification + SMS via
    `referral_bonus` template.
  - `withdrawal_processed` template exists and is seeded, but there's no
    withdrawal route in this repo snapshot to hook it into — wire
    `send_templated("withdrawal_processed", ...)` into whichever route
    handles your M-Pesa B2C payout once you paste this pack in, right
    after you mark the transaction completed.

## Still not wired (by design, needs your review first)

- The Daraja STK Push / B2C call themselves — still stubs, same as before
  this pack. Nothing here changes your credentials flow.
- `mpesa_b2c` gateway limits exist in the DB but nothing calls
  `PaymentGateway.query.filter_by(code="mpesa_b2c")` yet, since the
  withdrawal route isn't in this snapshot.



- Did not touch the PHP/Laravel template's actual code or database — this
  pack only borrows the *feature list*, everything is fresh Flask/Python.
- Did not add multi-language support (template had it; skipped as
  lowest-value for a Kenya-only launch — say the word if you want it).
- Did not migrate the template's payout-gateway integrations
  (Khalti/Paystack/Flutterwave) — you're on M-Pesa Daraja, so those
  don't apply, but the `PaymentGateway` model is generic enough to add a
  new gateway row (e.g. `card_paystack`) later without a schema change.
