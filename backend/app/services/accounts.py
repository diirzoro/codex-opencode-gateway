from datetime import datetime, timezone
from math import ceil

def user_payload(user) -> dict:
    now = datetime.now(timezone.utc)
    trial_end = user.trial_ends_at
    if trial_end.tzinfo is None:
        trial_end = trial_end.replace(tzinfo=timezone.utc)
    return {
        "id": str(user.id), "username": user.username, "email": user.email,
        "phone": user.phone, "postal_code": user.postal_code,
        "country": user.country.name, "region": user.region.name if user.region else None,
        "city": user.city.name if user.city else None, "role": user.role, "status": user.status,
        "preferred_language": user.preferred_language, "preferred_theme": user.preferred_theme,
        "trial_started_at": user.trial_started_at, "trial_ends_at": user.trial_ends_at,
        "advanced_trial_started_at": user.advanced_trial_started_at,
        "trial_remaining_days": max(0, ceil((trial_end - now).total_seconds() / 86400)),
        "last_login_at": user.last_login_at,
    }
