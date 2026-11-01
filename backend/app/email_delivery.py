import smtplib
import ssl
from email.message import EmailMessage

from .config import settings


class EmailDeliveryError(Exception):
    pass


def send_action_email(recipient: str, subject: str, action_url: str, action_label: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_address:
        raise EmailDeliveryError("Email delivery is not configured.")
    message = EmailMessage()
    message["From"] = settings.smtp_from_address
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(
        f"Use the following link to {action_label}. It expires in "
        f"{settings.auth_action_token_ttl_minutes} minutes:\n\n{action_url}\n\n"
        "If you did not request this, you can ignore this message."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError("Could not deliver the account email.") from error
