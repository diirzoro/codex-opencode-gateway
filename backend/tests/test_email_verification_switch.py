"""Early-launch verification policy checks (no SMTP or live DB required)."""
import os
import unittest
from unittest.mock import patch
from app.services.email_verification import required_for_registration

class EmailVerificationSwitchTests(unittest.TestCase):
    def test_default_is_verification_required(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(required_for_registration())

    def test_explicit_temporary_disable(self):
        with patch.dict(os.environ, {"EMAIL_VERIFICATION_REQUIRED": "false"}):
            self.assertFalse(required_for_registration())

    def test_reenable_without_code_changes(self):
        with patch.dict(os.environ, {"EMAIL_VERIFICATION_REQUIRED": "true"}):
            self.assertTrue(required_for_registration())

    def test_invalid_flag_fails_closed(self):
        with patch.dict(os.environ, {"EMAIL_VERIFICATION_REQUIRED": "maybe"}):
            with self.assertRaises(RuntimeError):
                required_for_registration()

if __name__ == "__main__":
    unittest.main()
