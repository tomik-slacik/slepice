"""Tests that app/integrations/notifications.py calls the Firebase Admin SDK
correctly.

This does NOT touch a real Firebase project - there isn't one configured
anywhere in this project (see docs/NOTIFICATIONS.md for why that's
deliberate, same reasoning as tests/test_payments.py for Stripe). It mocks
`firebase_admin` itself and checks the right things get called with the
right parameters - verifying the integration is *wired correctly*, which is
a different claim from "has pushed a real notification to a real phone".
ConsoleNotificationProvider (tested via tests/test_api.py's device-token
tests + the daily tick tests) is what actually exercises the real, working
default code path end to end.
"""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("KVOC_DATABASE_URL", "sqlite:///./test_kvoc.db")

import pytest  # noqa: E402

from app import config  # noqa: E402
from app.integrations.notifications import (  # noqa: E402
    ConsoleNotificationProvider,
    FCMNotificationProvider,
    get_notification_provider,
)


@pytest.fixture
def firebase_creds(monkeypatch):
    monkeypatch.setattr(
        config, "FIREBASE_CREDENTIALS_JSON",
        '{"type": "service_account", "project_id": "kvoc-test"}',
    )
    # never let a test leak a real firebase_admin app across test runs
    monkeypatch.setattr(FCMNotificationProvider, "_app", None)


def test_provider_selection_defaults_to_console():
    # KVOC_NOTIFICATION_PROVIDER is unset throughout this test suite -
    # same pattern as test_payments.py's equivalent check for payments.
    assert isinstance(get_notification_provider(), ConsoleNotificationProvider)


def test_provider_selection_returns_fcm_when_configured(monkeypatch):
    monkeypatch.setattr(config, "NOTIFICATION_PROVIDER", "fcm")
    assert isinstance(get_notification_provider(), FCMNotificationProvider)


def test_console_provider_never_raises_without_a_token():
    # a hen whose owner never registered a device - must be a silent no-op,
    # never an error that could break the daily tick for every other hen
    ConsoleNotificationProvider().send(1, None, "TITLE", "body")


def test_fcm_provider_refuses_to_start_without_credentials(monkeypatch):
    monkeypatch.setattr(config, "FIREBASE_CREDENTIALS_JSON", "")
    monkeypatch.setattr(FCMNotificationProvider, "_app", None)
    with pytest.raises(RuntimeError):
        FCMNotificationProvider()._ensure_app()


def test_fcm_provider_skips_cleanly_with_no_device_token(firebase_creds):
    # must not even try to initialize firebase_admin - nothing to send to
    with patch("firebase_admin.initialize_app") as init_app:
        FCMNotificationProvider().send(1, None, "TITLE", "body")
    init_app.assert_not_called()


def test_fcm_provider_sends_with_correct_token_and_text(firebase_creds):
    with patch("firebase_admin.initialize_app") as init_app, \
         patch("firebase_admin.credentials.Certificate") as certificate, \
         patch("firebase_admin.messaging.Message") as message_cls, \
         patch("firebase_admin.messaging.Notification") as notification_cls, \
         patch("firebase_admin.messaging.send", return_value="projects/x/messages/1") as send:
        FCMNotificationProvider().send(42, "device-token-xyz", "BONUS", "Nuška má dobrý den.")

    certificate.assert_called_once_with({"type": "service_account", "project_id": "kvoc-test"})
    init_app.assert_called_once()
    notification_cls.assert_called_once_with(title="Mazlík · BONUS", body="Nuška má dobrý den.")
    _, kwargs = message_cls.call_args
    assert kwargs["token"] == "device-token-xyz"
    send.assert_called_once()


def test_fcm_provider_send_failure_does_not_raise(firebase_creds):
    # a dead token / Firebase outage must never break the daily tick for
    # every other hen - the caller (app/tick.py) doesn't wrap this in try/except
    with patch("firebase_admin.initialize_app"), \
         patch("firebase_admin.credentials.Certificate"), \
         patch("firebase_admin.messaging.Message"), \
         patch("firebase_admin.messaging.Notification"), \
         patch("firebase_admin.messaging.send", side_effect=Exception("boom")):
        FCMNotificationProvider().send(42, "device-token-xyz", "BONUS", "text")
