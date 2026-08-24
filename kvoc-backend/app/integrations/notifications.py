"""Push notification provider abstraction.

ConsoleNotificationProvider below just prints - it stands in for a real push
service so the rest of the app (the daily tick, the API) never needs to know
which one is actually wired up.

TODO before a real launch: implement a provider against Firebase Cloud
Messaging (covers both iOS and Android from one API) or APNs directly:
  - FCM:  https://firebase.google.com/docs/cloud-messaging
  - APNs: https://developer.apple.com/documentation/usernotifications
Store device push tokens against the Hen (or a future User) once the mobile
client registers for notifications, and keep service credentials in
environment variables / a secrets manager, never in source control.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class NotificationProvider(ABC):
    @abstractmethod
    def send(self, hen_id: int, title: str, body: str) -> None:
        raise NotImplementedError


class ConsoleNotificationProvider(NotificationProvider):
    def send(self, hen_id: int, title: str, body: str) -> None:
        print(f"[ConsoleNotificationProvider] -> hen #{hen_id}: {title} — {body}")


def get_notification_provider() -> NotificationProvider:
    return ConsoleNotificationProvider()
