from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

from app.core.config import get_settings


class EmailDeliveryError(Exception):
    pass

VERIFICATION_TEMPLATE = """Welcome to {app_name}.

Please verify your email address by opening this link:

{verification_url}

This link expires in {expires_minutes} minutes.
If you did not create an account, you can safely ignore this email."""

RESET_PASSWORD_TEMPLATE = """You requested a password reset for {app_name}.

Open this link to choose a new password:

{reset_url}

This link expires in {expires_minutes} minutes.
If you did not request this, you can safely ignore this email."""


class EmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _check_smtp_config(self) -> None:
        if (
            not self.settings.smtp_host
            or not self.settings.smtp_username
            or not self.settings.smtp_password
            or not self.settings.smtp_from_email
        ):
            raise EmailDeliveryError("SMTP settings are not configured.")

    def _send(self, *, to_email: str, subject: str, body: str) -> None:
        self._check_smtp_config()
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.settings.smtp_from_email
        message["To"] = to_email
        message.attach(MIMEText(body, "plain", "utf-8"))
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message)
        except Exception as exc:
            raise EmailDeliveryError("Unable to deliver email.") from exc

    def send_verification_email(self, to_email: str, verification_url: str) -> None:
        expires_minutes = int(self.settings.verification_token_expire_minutes)
        body = VERIFICATION_TEMPLATE.format(
            app_name=self.settings.app_display_name,
            verification_url=verification_url,
            expires_minutes=expires_minutes,
        )
        self._send(
            to_email=to_email,
            subject=f"Verify your {self.settings.app_display_name} email address",
            body=body,
        )

    def send_password_reset_email(self, to_email: str, reset_url: str) -> None:
        expires_minutes = int(self.settings.verification_token_expire_minutes)
        body = RESET_PASSWORD_TEMPLATE.format(
            app_name=self.settings.app_display_name,
            reset_url=reset_url,
            expires_minutes=expires_minutes,
        )
        self._send(
            to_email=to_email,
            subject=f"Reset your {self.settings.app_display_name} password",
            body=body,
        )
