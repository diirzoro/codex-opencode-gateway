"""Conservative denylist for known throwaway mail domains at signup.

No external DNS calls and no rejection of ordinary custom business domains.
The list is deliberately narrow; expand via reviewed updates as needed.
"""
from fastapi import HTTPException

BLOCKED_DOMAINS = frozenset({
    "10minutemail.com", "10minutemail.net", "20minutemail.com",
    "guerrillamail.com", "guerrillamail.net", "guerrillamail.org",
    "guerrillamailblock.com", "grr.la", "sharklasers.com",
    "mailinator.com", "mailinator.net", "mailinator.org",
    "tempmail.com", "temp-mail.org", "temp-mail.io",
    "throwawaymail.com", "yopmail.com", "yopmail.fr",
    "getnada.com", "emailondeck.com", "trashmail.com",
    "dispostable.com", "maildrop.cc", "fakeinbox.com",
    "mohmal.com", "minuteinbox.com",
})


def require_permanent_email(email: str):
    domain = email.strip().lower().rsplit("@", 1)[-1].rstrip(".")
    if domain in BLOCKED_DOMAINS:
        raise HTTPException(422, "Temporary or disposable email addresses are not accepted")
