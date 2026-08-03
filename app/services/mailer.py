"""Outbound email with swappable delivery.

`EMAIL_BACKEND=console` (the default) writes the message to the server log, so
onboarding works with no mail configuration and no chance of a test invite
reaching a real inbox. `EMAIL_BACKEND=smtp` delivers for real using the SMTP_*
settings. Callers just call `send()` and never learn which is in use.
"""
import logging
import smtplib
from email.message import EmailMessage

from rag_engine import settings

logger = logging.getLogger("orbis.mailer")


def _send_console(to: str, subject: str, body: str) -> None:
    logger.warning(
        "\n%s\n[EMAIL · console backend — not actually sent]\nTo:      %s\n"
        "From:    %s\nSubject: %s\n%s\n%s\n%s",
        "=" * 70, to, settings.EMAIL_FROM, subject, "-" * 70, body, "=" * 70,
    )


def _send_smtp(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        raise RuntimeError("EMAIL_BACKEND=smtp but SMTP_HOST is not set")
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
        smtp.send_message(message)


def send(to: str, subject: str, body: str) -> bool:
    """Deliver a message. Returns False if delivery failed — never raises, so a
    mail outage cannot roll back the employee record that was just created."""
    try:
        if settings.EMAIL_BACKEND == "smtp":
            _send_smtp(to, subject, body)
        else:
            _send_console(to, subject, body)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_password_reset(to: str, full_name: str, link: str) -> bool:
    """Send a reset link. Says plainly what to do if the request wasn't theirs."""
    company = settings.COMPANY_NAME
    return send(
        to,
        f"Reset your {company} password",
        f"""Hi {full_name},

Someone asked to reset the password for your {company} account. If that was
you, choose a new password here:

    {link}

This link expires in {settings.RESET_TTL_MINUTES} minutes and can only be used
once. Setting a new password signs you out on every device.

If you did not request this, you can ignore this message — your password has
not changed. If it keeps happening, please tell HR.

— {company} People Team
""",
    )


def send_invite(to: str, full_name: str, company_email: str, link: str) -> bool:
    """Welcome a new hire and point them at their set-password link."""
    company = settings.COMPANY_NAME
    return send(
        to,
        f"Welcome to {company} — set up your account",
        f"""Hi {full_name},

Welcome to {company}! Your company email address is:

    {company_email}

To finish setting up your account, choose a password here:

    {link}

This link is valid for {settings.INVITE_TTL_DAYS} days and can only be used once.
Sign in with your company email address once it is set.

If you weren't expecting this, please contact HR.

— {company} People Team
""",
    )
