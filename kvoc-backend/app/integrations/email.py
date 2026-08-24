"""Email provider abstraction - same mock/real split as payments.py and
notifications.py.

ConsoleEmailProvider is the default and safe: never sends anything real,
just prints what would be sent. SMTPEmailProvider is a real, working
implementation against plain SMTP (works with Gmail + an app password, or
any other SMTP account - deliberately not tied to one dedicated
transactional-email vendor) - but it has never sent a real email from here,
because configuring real SMTP credentials is something only you can do.
See docs/EMAIL.md.

Switch providers with the KVOC_EMAIL_PROVIDER environment variable
("console" | "smtp"); "smtp" also needs KVOC_SMTP_HOST/USERNAME/PASSWORD.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .. import config


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None:
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    def send(self, to: str, subject: str, body: str) -> None:
        print(f"[ConsoleEmailProvider] -> {to}: {subject}\n{body}\n")


class SMTPEmailProvider(EmailProvider):
    def __init__(self) -> None:
        if not (config.SMTP_HOST and config.SMTP_USERNAME and config.SMTP_PASSWORD):
            raise RuntimeError(
                "KVOC_EMAIL_PROVIDER=smtp but KVOC_SMTP_HOST/KVOC_SMTP_USERNAME/"
                "KVOC_SMTP_PASSWORD aren't all set - see docs/EMAIL.md."
            )

    def send(self, to: str, subject: str, body: str) -> None:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = config.EMAIL_FROM
        msg["To"] = to

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.sendmail(config.EMAIL_FROM, [to], msg.as_string())


def get_email_provider() -> EmailProvider:
    if config.EMAIL_PROVIDER == "smtp":
        return SMTPEmailProvider()
    return ConsoleEmailProvider()
