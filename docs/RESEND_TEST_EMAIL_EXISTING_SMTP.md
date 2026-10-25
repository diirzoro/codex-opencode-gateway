# Resend SMTP — existing Gateway email verification (TEST only)

## Confirmed existing implementation
- `backend/app/services/email_verification.py` already sends registration verification via SMTP STARTTLS.
- `backend/app/routes/auth.py` already creates one-time verification tokens, verifies links and supports resend.
- No new email agent, service, queue, API relay, or Native AI change is needed.
- The domain `opencode-gateway.codes` has verified DKIM, sending CNAMEs and receiving MX in the supplied Resend screenshot. This verifies domain DNS, **not** delivery credentials or application delivery.

## Configure once on TEST
Keep the actual API key only in the existing protected runtime environment used by `opencode-gateway-test.service` (the appropriate environment source must be determined from the service's EnvironmentFile/Environment; do not infer it from a repository file). Never commit the key.

```dotenv
EMAIL_VERIFICATION_REQUIRED=true
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=<Resend API key; enter directly into the protected TEST environment>
SMTP_FROM=verify@opencode-gateway.codes
```

SMTP_FROM must be an authorized address on the verified domain. The `SMTP_PASSWORD` must have Resend sending permission. Set no secret in GitHub Actions, frontend JS or public URLs.

## Rollout and safe acceptance
1. Read TEST's actual systemd environment references *without printing any values* and confirm which protected environment file controls the running service.
2. Make a root-private, permissions-preserving backup of **only** that existing environment file. Insert or update the six keys above; preserve every other variable. Avoid command-history disclosure or echoing credentials.
3. Restart **only** `opencode-gateway-test.service`, not Nginx, LIVE or Native OpenCode.
4. Check service status and trigger registration with a test-owned email address. Confirm email delivery, HTTPS verification link, one-time expiry behavior and login after verification.
5. Test resend and unavailable/invalid SMTP error handling. Never log the verification token or API key.
6. If email verification was temporarily disabled, changing `EMAIL_VERIFICATION_REQUIRED` to true changes registration behavior; do not claim test registration works without sending a real message.

## Known current state (2026-10-25)
Verified DNS records are established from owner screenshots. No SMTP credentials have been supplied or installed, and no send test has occurred. GitHub source contains the SMTP implementation; adding this document/template alone does not enable runtime delivery.
