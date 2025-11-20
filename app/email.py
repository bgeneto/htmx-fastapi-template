"""Email service using Brevo (Sendinblue) API for transactional emails"""

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)


def _get_brevo_client():
    """Initialize Brevo API client"""
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = settings.BREVO_API_KEY.get_secret_value()
    return sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )


async def send_magic_link(email: str, full_name: str, magic_link: str) -> bool:
    """
    Send magic link email for passwordless login

    Args:
        email: Recipient email address
        full_name: Recipient's full name
        magic_link: Complete magic link URL with token

    Returns:
        True if email sent successfully, False otherwise
    """
    api_instance = _get_brevo_client()

    subject = "Your login link"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb;">Login to {settings.app_name}</h2>
            <p>Hi {full_name},</p>
            <p>Click the button below to log in to your account. This link will expire in {settings.MAGIC_LINK_EXPIRY_MINUTES} minutes.</p>
            <div style="margin: 30px 0;">
                <a href="{magic_link}"
                   style="background-color: #2563eb; color: white; padding: 12px 30px;
                          text-decoration: none; border-radius: 5px; display: inline-block;">
                    Log In
                </a>
            </div>
            <p style="color: #666; font-size: 14px;">
                Or copy and paste this link into your browser:<br>
                <a href="{magic_link}" style="color: #2563eb;">{magic_link}</a>
            </p>
            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 20px;">
                If you didn't request this login link, you can safely ignore this email.
            </p>
        </div>
    </body>
    </html>
    """

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": email, "name": full_name}],
        sender={"email": settings.EMAIL_FROM_ADDRESS, "name": settings.EMAIL_FROM_NAME},
        subject=subject,
        html_content=html_content,
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Magic link email sent to {email}: {api_response}")
        return True
    except ApiException as e:
        logger.error(f"Failed to send magic link email to {email}: {e}")
        return False


async def send_registration_notification(
    admin_email: str, new_user_email: str, new_user_name: str, approval_url: str
) -> bool:
    """
    Notify admin about new user registration pending approval

    Args:
        admin_email: Admin email address
        new_user_email: New user's email
        new_user_name: New user's full name
        approval_url: URL to admin user management page

    Returns:
        True if email sent successfully, False otherwise
    """
    api_instance = _get_brevo_client()

    subject = f"New user registration: {new_user_name}"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb;">New User Registration</h2>
            <p>A new user has registered and is waiting for approval:</p>
            <div style="background-color: #f3f4f6; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p style="margin: 5px 0;"><strong>Name:</strong> {new_user_name}</p>
                <p style="margin: 5px 0;"><strong>Email:</strong> {new_user_email}</p>
            </div>
            <div style="margin: 30px 0;">
                <a href="{approval_url}"
                   style="background-color: #2563eb; color: white; padding: 12px 30px;
                          text-decoration: none; border-radius: 5px; display: inline-block;">
                    Review User
                </a>
            </div>
            <p style="color: #666; font-size: 14px;">
                Or visit the admin panel at:<br>
                <a href="{approval_url}" style="color: #2563eb;">{approval_url}</a>
            </p>
        </div>
    </body>
    </html>
    """

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": admin_email}],
        sender={"email": settings.EMAIL_FROM_ADDRESS, "name": settings.EMAIL_FROM_NAME},
        subject=subject,
        html_content=html_content,
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Registration notification sent to {admin_email}: {api_response}")
        return True
    except ApiException as e:
        logger.error(f"Failed to send registration notification to {admin_email}: {e}")
        return False


async def send_account_approved(email: str, full_name: str, login_url: str) -> bool:
    """
    Notify user that their account has been approved by admin

    Args:
        email: User email address
        full_name: User's full name
        login_url: URL to request magic link

    Returns:
        True if email sent successfully, False otherwise
    """
    api_instance = _get_brevo_client()

    subject = "Your account has been approved"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #10b981;">Account Approved!</h2>
            <p>Hi {full_name},</p>
            <p>Great news! Your account has been approved and you can now log in to {settings.app_name}.</p>
            <div style="margin: 30px 0;">
                <a href="{login_url}"
                   style="background-color: #2563eb; color: white; padding: 12px 30px;
                          text-decoration: none; border-radius: 5px; display: inline-block;">
                    Log In Now
                </a>
            </div>
            <p style="color: #666; font-size: 14px;">
                We use passwordless authentication for your security. Simply enter your email address
                and we'll send you a secure login link.
            </p>
        </div>
    </body>
    </html>
    """

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": email, "name": full_name}],
        sender={"email": settings.EMAIL_FROM_ADDRESS, "name": settings.EMAIL_FROM_NAME},
        subject=subject,
        html_content=html_content,
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Account approved email sent to {email}: {api_response}")
        return True
    except ApiException as e:
        logger.error(f"Failed to send account approved email to {email}: {e}")
        return False
