"""Push notification provider abstraction.

ConsoleNotificationProvider is the default and safe: it never talks to any
external service, just prints what *would* be sent - exactly the same
"mock vs real" split as app/integrations/payments.py (MockPaymentProvider vs
StripePaymentProvider).

FCMNotificationProvider below is a real, working implementation using
Firebase Cloud Messaging (covers Android and iOS from one API) via the
`firebase-admin` SDK. It sends an actual push to a device - but it has
never been run against a real Firebase project from here, because creating
that project is something only you can do (a free Google account, no
credit card needed for FCM itself). See docs/NOTIFICATIONS.md for the exact
setup steps and what env vars to set.

Switch providers with the KVOC_NOTIFICATION_PROVIDER environment variable
("console" | "fcm"); "fcm" also needs KVOC_FIREBASE_CREDENTIALS_JSON.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .. import config


class NotificationProvider(ABC):
    @abstractmethod
    def send(self, hen_id: int, device_token: Optional[str], title: str, body: str) -> None:
        """device_token is the recipient's FCM registration token, as
        registered via POST /auth/device-token - None if that user's app
        has never registered one (nothing installed, or notifications
        never granted). Implementations must treat that as "nothing to do
        here", not an error.
        """
        raise NotImplementedError


class ConsoleNotificationProvider(NotificationProvider):
    def send(self, hen_id: int, device_token: Optional[str], title: str, body: str) -> None:
        print(f"[ConsoleNotificationProvider] -> hen #{hen_id}: {title} — {body}")


class FCMNotificationProvider(NotificationProvider):
    """Sends a real push via Firebase Cloud Messaging.

    Lazily initializes the firebase_admin app on first use (not at import
    time) so simply importing this module - e.g. while running the test
    suite with the default "console" provider - never requires the
    firebase-admin package to be configured, or even importable, if it's
    not installed. Import errors / bad credentials surface the first time
    something actually tries to send, with a clear message, not a crash on
    server boot.
    """

    _app = None

    def _ensure_app(self):
        if FCMNotificationProvider._app is not None:
            return FCMNotificationProvider._app
        if not config.FIREBASE_CREDENTIALS_JSON:
            raise RuntimeError(
                "KVOC_NOTIFICATION_PROVIDER=fcm but KVOC_FIREBASE_CREDENTIALS_JSON is not "
                "set - see docs/NOTIFICATIONS.md for how to get this from your Firebase "
                "project's service account settings."
            )
        import json

        import firebase_admin
        from firebase_admin import credentials

        cred_dict = json.loads(config.FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
        FCMNotificationProvider._app = firebase_admin.initialize_app(cred)
        return FCMNotificationProvider._app

    def send(self, hen_id: int, device_token: Optional[str], title: str, body: str) -> None:
        if not device_token:
            print(f"[FCMNotificationProvider] hen #{hen_id}: no device token registered, skipping ({title})")
            return

        from firebase_admin import messaging

        self._ensure_app()
        message = messaging.Message(
            notification=messaging.Notification(title=f"Kvoč · {title}", body=body),
            token=device_token,
        )
        try:
            response = messaging.send(message)
            print(f"[FCMNotificationProvider] -> hen #{hen_id}: sent ({response})")
        except Exception as exc:  # noqa: BLE001 - a failed push must never break the daily tick
            print(f"[FCMNotificationProvider] -> hen #{hen_id}: FAILED to send ({exc})")


def get_notification_provider() -> NotificationProvider:
    if config.NOTIFICATION_PROVIDER == "fcm":
        return FCMNotificationProvider()
    return ConsoleNotificationProvider()
