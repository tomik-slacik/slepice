"""Tests that app/integrations/email.py talks to smtplib correctly.

Same reasoning and pattern as tests/test_payments.py (Stripe) and
tests/test_notifications.py (Firebase) - this does NOT send a real email,
there is no SMTP account configured anywhere in this project (see
docs/EMAIL.md for why that's deliberate). It mocks smtplib.SMTP itself and
checks the right methods get called with the right arguments - verifying
the integration is *wired correctly*, a different claim from "has
delivered a real email to a real inbox". ConsoleEmailProvider (the
default, exercised via tests/test_api.py's registration/forgot-password
tests) is what actually runs end to end.

Unlike Stripe/Firebase, smtplib is the standard library, always
importable - so unlike test_payments.py/test_notifications.py there's no
optional dependency to worry about here.
"""
import email
import os
from unittest.mock import patch

os.environ.setdefault("KVOC_DATABASE_URL", "sqlite:///./test_kvoc.db")

import pytest  # noqa: E402

from app import config  # noqa: E402
from app.integrations.email import (  # noqa: E402
    ConsoleEmailProvider,
    SMTPEmailProvider,
    get_email_provider,
)


@pytest.fixture
def smtp_config(monkeypatch):
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_PORT", 587)
    monkeypatch.setattr(config, "SMTP_USERNAME", "user@example.com")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "app-password")
    # ASCII on purpose - the default ("Mazlík <noreply@mazlik.cz>") has a
    # diacritic, which MIMEText/email.mime would RFC-2047-encode in the
    # header and make the sendmail() payload assertions below fragile for
    # no real benefit - this test is about the SMTP call shape, not about
    # re-proving MIME encodes non-ASCII text (a real but separate concern)
    monkeypatch.setattr(config, "EMAIL_FROM", "Mazlik <noreply@example.com>")


def test_provider_selection_defaults_to_console():
    # KVOC_EMAIL_PROVIDER is unset throughout this test suite - same
    # pattern as test_payments.py/test_notifications.py's equivalent checks
    assert isinstance(get_email_provider(), ConsoleEmailProvider)


def test_provider_selection_returns_smtp_when_configured(monkeypatch, smtp_config):
    monkeypatch.setattr(config, "EMAIL_PROVIDER", "smtp")
    assert isinstance(get_email_provider(), SMTPEmailProvider)


def test_console_provider_never_raises():
    # must be a trivial no-op path - nothing here should ever be able to
    # break registration/forgot-password just because email "sending" failed
    ConsoleEmailProvider().send("a@b.com", "Vitej", "Ahoj a diky.")


def test_smtp_provider_refuses_to_start_without_credentials(monkeypatch):
    monkeypatch.setattr(config, "SMTP_HOST", "")
    with pytest.raises(RuntimeError):
        SMTPEmailProvider()


def test_smtp_provider_sends_with_starttls_login_and_correct_recipient(smtp_config):
    with patch("smtplib.SMTP") as smtp_cls:
        server = smtp_cls.return_value.__enter__.return_value
        SMTPEmailProvider().send("zakaznik@example.com", "Vitej v Mazliku", "Ahoj a diky za registraci.")

    smtp_cls.assert_called_once_with("smtp.example.com", 587)
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("user@example.com", "app-password")

    args, _ = server.sendmail.call_args
    from_addr, to_addrs, raw_message = args
    assert from_addr == "Mazlik <noreply@example.com>"
    # a real list of exactly the one intended recipient - never accidentally
    # a bare string (smtplib would then send one character per "recipient")
    assert to_addrs == ["zakaznik@example.com"]

    # parsed like a real mail server would, not string-matched on the raw
    # dump - MIMEText base64-encodes the body by default even for plain
    # ASCII text (charset="utf-8" always does, see the msg construction in
    # email.py), so a literal substring check on raw_message would fail here
    # despite the message being completely correct
    parsed = email.message_from_string(raw_message)
    assert parsed["Subject"] == "Vitej v Mazliku"
    assert parsed.get_payload(decode=True).decode("utf-8") == "Ahoj a diky za registraci."


def test_smtp_provider_propagates_a_login_failure(smtp_config):
    # a wrong password/host must surface as a real error the caller can
    # react to (see docs/EMAIL.md), never look like a silently "sent" email
    with patch("smtplib.SMTP") as smtp_cls:
        server = smtp_cls.return_value.__enter__.return_value
        server.login.side_effect = Exception("535 authentication failed")
        with pytest.raises(Exception, match="authentication failed"):
            SMTPEmailProvider().send("zakaznik@example.com", "Subject", "Body")
