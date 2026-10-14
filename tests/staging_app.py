"""Loopback-only disposable QA app. SMTP is a local fixture mailbox, never sent."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

assert os.environ.get("AUDIT_DISPOSABLE_DB") == "1"
assert urlsplit(os.environ["DATABASE_URL"]).hostname == "127.0.0.1"
from backend.app.main import app
from backend.app.services import email_verification

def fixture_mail(email, token):
    Path(os.environ["AUDIT_MAILBOX"]).write_text(json.dumps({"email":email,"token":token}))

email_verification.smtp_ready=lambda: True
email_verification.send_link=fixture_mail

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ["AUDIT_STAGING_PORT"]), log_level="warning")
