"""
Thin wrapper around MessageTemplate so the rest of the app never formats
SMS/email copy inline — it just calls send_templated(code, to=..., **vars).

NOTE: this repo snapshot doesn't include the Africa's Talking SMS client
you built for Mzizibet's deposit-confirmation flow (per your other
sessions), so `_dispatch_sms()` below is a stub that logs instead of
sending. Swap the body of `_dispatch_sms()` for your existing
africastalking client call — everything upstream of it (template lookup,
placeholder rendering, call sites in admin_extra.py / auth.py) is already
wired and doesn't need to change.
"""
import logging
from app.models.notification import MessageTemplate

logger = logging.getLogger(__name__)


def _dispatch_sms(phone_number: str, body: str):
    """Replace this with your existing Africa's Talking send call, e.g.:

        import africastalking
        africastalking.initialize(username=..., api_key=...)
        sms = africastalking.SMS
        sms.send(body, [phone_number])
    """
    logger.info(f"[SMS STUB] to={phone_number} body={body!r}")


def send_templated(code: str, to_phone: str, **template_vars) -> bool:
    """Look up a MessageTemplate by code, render it with template_vars,
    and dispatch it. Returns False (and logs a warning) instead of raising
    if the template is missing, so a missing/renamed template code never
    takes down the calling request (e.g. a KYC approval)."""
    tpl = MessageTemplate.query.filter_by(code=code).first()
    if not tpl:
        logger.warning(f"send_templated: no MessageTemplate with code={code!r}")
        return False

    body = tpl.render(**template_vars)

    if tpl.channel == "sms":
        _dispatch_sms(to_phone, body)
        return True

    logger.warning(f"send_templated: channel {tpl.channel!r} not implemented yet")
    return False
