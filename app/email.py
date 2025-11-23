"""Email service using Resend API for transactional emails"""

import resend

from .config import settings
from .i18n import gettext as _
from .logger import get_logger

logger = get_logger(__name__)


def _create_safe_html_template(
    preheader_text: str, subject: str, content_body: str, sender_footer: bool = False
) -> str:
    """
    Create a transactional email HTML template that follows best practices.
    """
    unsubscribe_footer = ""
    if sender_footer:
        unsubscribe_footer = f"""
        <tr>
            <td style="padding: 20px; font-size: 12px; color: #666; border-top: 1px solid #eee; text-align: center;">
                This is an automated message from {settings.EMAIL_FROM_NAME}.<br>
                If you have questions, please contact us or reply to this email.<br><br>
                <a href="{settings.APP_BASE_URL}" style="color: #666; text-decoration: none;">{settings.app_name}</a>
            </td>
        </tr>
        """

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="x-apple-disable-message-reformatting" />
    <meta name="format-detection" content="telephone=no,address=no,email=no,date=no,url=no" />
    <!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->
    <title>{subject}</title>
    <style type="text/css">
        body {{margin: 0; padding: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.6; color: #333333;}}
        table {{border-collapse: collapse;}}
        td {{vertical-align: top;}}
        @media only screen and (max-width: 480px) {{
            .mobile-padding {{ padding-left: 10px !important; padding-right: 10px !important; }}
            .mobile-font-size {{ font-size: 16px !important; }}
        }}
    </style>
    <!-- Preheader text for email clients -->
    <div style="display: none; visibility: hidden; opacity: 0; color: transparent; height: 0; width: 0;">{preheader_text}</div>
</head>
<body>
    <table width="100%" border="0" cellspacing="0" cellpadding="0" bgcolor="#ffffff">
        <tr>
            <td align="center" valign="top">
                <table width="600" border="0" cellspacing="0" cellpadding="0" class="mobile-padding">
                    <tr>
                        <td align="center" valign="top" style="padding: 20px 0;">
                            <h1 style="margin: 0; font-size: 24px; font-weight: normal; color: #333;">{settings.app_name}</h1>
                        </td>
                    </tr>
                </table>
                <table width="600" border="0" cellspacing="0" cellpadding="0" class="mobile-padding">
                    {content_body}
                    {unsubscribe_footer}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def _create_plain_text_version(html_content: str, key_action_text: str = "") -> str:
    """
    Generate a plain text version from HTML content for accessibility and spam prevention.
    """
    # Remove HTML tags and decode entities (simplified version)
    import re

    plain_text = re.sub(r"<[^>]+>", " ", html_content)
    plain_text = re.sub(r"&[^;]+;", " ", plain_text)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()

    return f"""{settings.app_name}

{plain_text}

---
This is an automated message. Please do not reply.

{key_action_text}

Sent by {settings.EMAIL_FROM_NAME}
{settings.APP_BASE_URL}
"""


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
    subject = "Your login link"
    preheader_text = f"Click your login link from {settings.app_name} - expires in {settings.MAGIC_LINK_EXPIRY_MINUTES} minutes"

    content_body = f"""
        <tr>
            <td style="padding: 40px 30px; text-align: center; background-color: #ffffff;">
                <h2 style="margin: 0 0 20px 0; font-size: 24px; font-weight: normal; color: #2563eb;">Login to {settings.app_name}</h2>
                <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 1.6; color: #333;">
                    Hi {full_name},<br><br>
                    Click the button below to log in to your account. This link will expire in {settings.MAGIC_LINK_EXPIRY_MINUTES} minutes.
                </p>
                <table border="0" cellspacing="0" cellpadding="0" style="margin: 30px auto;">
                    <tr>
                        <td style="border-radius: 5px; background-color: #2563eb;" bgcolor="#2563eb">
                            <a href="{magic_link}" style="padding: 12px 30px; border: 1px solid #2563eb; border-radius: 5px; color: #ffffff; display: inline-block; font-family: sans-serif; font-size: 16px; font-weight: bold; text-decoration: none; text-transform: capitalize;" class="mobile-font-size">
                                Log In
                            </a>
                        </td>
                    </tr>
                </table>
                <p style="margin: 30px 0 0 0; font-size: 14px; line-height: 1.6; color: #666;">
                    Or copy and paste this link into your browser:<br>
                    <a href="{magic_link}" style="color: #2563eb; word-break: break-all;">{magic_link}</a>
                </p>
                <hr style="border: none; border-top: 1px solid #eeeeee; margin: 40px 0;">
                <p style="margin: 0; font-size: 12px; line-height: 1.6; color: #666;">
                    <strong>Security note:</strong> If you didn't request this login link, you can safely ignore this email.<br>
                    Links expire quickly for your security.
                </p>
            </td>
        </tr>
    """

    html_content = _create_safe_html_template(
        preheader_text, subject, content_body, sender_footer=True
    )

    plain_text = _create_plain_text_version(
        f"{subject} - Hi {full_name}, click this link to log in: {magic_link} (expires in {settings.MAGIC_LINK_EXPIRY_MINUTES} minutes)",
        f"Login link: {magic_link}",
    )

    # Create escape URL for List-Unsubscribe header
    from urllib.parse import quote

    unsubscribe_url = f"{settings.APP_BASE_URL}/unsubscribe?email={quote(email)}"

    try:
        logger.info(f"Attempting to send magic link email to {email} via Resend")
        logger.debug(f"Resend API Key configured: {bool(settings.EMAIL_API_KEY)}")
        logger.debug(f"From address: {settings.EMAIL_FROM_ADDRESS}")
        logger.debug(f"From name: {settings.EMAIL_FROM_NAME}")

        api_response = resend.Emails.send(
            {
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
                "to": [email],
                "subject": subject,
                "html": html_content,
                "text": plain_text,
                "headers": {
                    "List-Unsubscribe": f"<{unsubscribe_url}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    "X-Auto-Response-Suppress": "AutoReply, DR, NDR, RN, NRN",
                    "X-Transaction-Type": "transactional",
                    "X-Email-Type": "authentication",
                },
            }
        )
        logger.info(f"Magic link email sent successfully to {email}: {api_response}")
        return True
    except Exception as e:
        logger.error(f"Failed to send magic link email to {email}: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
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
    subject = f"New user registration: {new_user_name}"
    preheader_text = f"New user {new_user_name} has registered and needs approval"

    content_body = f"""
        <tr>
            <td style="padding: 40px 30px; background-color: #f9fafb;">
                <h2 style="margin: 0 0 20px 0; font-size: 20px; font-weight: normal; color: #2563eb;">New User Registration Pending</h2>
                <p style="margin: 0 0 25px 0; font-size: 16px; line-height: 1.6; color: #374151;">
                    Hello admin,<br><br>
                    A new user has registered and is waiting for your approval:
                </p>

                <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; margin: 20px 0;">
                    <tr>
                        <td style="padding: 20px;">
                            <table width="100%" border="0" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #f3f4f6;">
                                        <strong style="color: #374151;">Name:</strong> <span style="color: #6b7280;">{new_user_name}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <strong style="color: #374151;">Email:</strong> <span style="color: #6b7280;">{new_user_email}</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                <table border="0" cellspacing="0" cellpadding="0" style="margin: 30px auto;">
                    <tr>
                        <td style="border-radius: 6px; background-color: #2563eb;" bgcolor="#2563eb">
                            <a href="{approval_url}" style="padding: 14px 28px; border: 1px solid #2563eb; border-radius: 6px; color: #ffffff; display: inline-block; font-family: sans-serif; font-size: 16px; font-weight: bold; text-decoration: none;" class="mobile-font-size">
                                Review & Approve User
                            </a>
                        </td>
                    </tr>
                </table>

                <p style="margin: 25px 0 0 0; font-size: 14px; line-height: 1.6; color: #6b7280;">
                    Or manage all users from the admin panel:<br>
                    <a href="{approval_url}" style="color: #2563eb; word-break: break-all;">{approval_url}</a>
                </p>
            </td>
        </tr>
    """

    html_content = _create_safe_html_template(
        preheader_text, subject, content_body, sender_footer=True
    )

    plain_text = _create_plain_text_version(
        f"New user {new_user_name} ({new_user_email}) has registered and needs your approval. Review: {approval_url}",
        f"Review user: {approval_url}",
    )

    try:
        logger.info(
            f"Attempting to send registration notification to {admin_email} via Resend"
        )
        api_response = resend.Emails.send(
            {
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
                "to": [admin_email],
                "subject": subject,
                "html": html_content,
                "text": plain_text,
                "headers": {
                    "X-Auto-Response-Suppress": "AutoReply, DR, NDR, RN, NRN",
                    "X-Transaction-Type": "transactional",
                    "X-Email-Type": "notification",
                },
            }
        )
        logger.info(
            f"Registration notification sent successfully to {admin_email}: {api_response}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send registration notification to {admin_email}: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
        return False


async def send_otp_code(email: str, full_name: str, otp_code: str) -> bool:
    """
    Send OTP code for login verification using Resend

    Args:
        email: Recipient email address
        full_name: Recipient's full name
        otp_code: 6-digit OTP code

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"=== send_otp_code() CALLED === email={email}, full_name={full_name}, otp_code={otp_code[:2]}****"
    )

    subject = _("Your verification code")
    preheader_text = _("Enter this 6-digit code to log in to {app_name}").format(
        app_name=settings.app_name
    )

    content_body = f"""
        <tr>
            <td style="padding: 40px 30px; background-color: #ffffff;">
                <!-- Greeting -->
                <h2 style="margin: 0 0 8px 0; font-size: 28px; font-weight: 600; color: #1f2937; text-align: center;">{_("Verification Required")}</h2>
                <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 1.6; color: #6b7280; text-align: center;">
                    {_("Hi")} {full_name},
                </p>

                <!-- Instructions -->
                <p style="margin: 0 0 25px 0; font-size: 15px; line-height: 1.6; color: #374151; text-align: center;">
                    {_("To complete your login to {app_name}, please enter this verification code:").format(app_name=settings.app_name)}
                </p>

                <!-- OTP Code Display -->
                <div style="margin: 0 auto 35px; text-align: center;">
                    <div style="display: inline-block; background: linear-gradient(135deg, #f0f9ff 0%, #f8fafc 100%); border: 2px solid #dbeafe; border-radius: 16px; padding: 30px 40px;">
                        <div style="font-size: 48px; font-weight: 700; letter-spacing: 12px; color: #1e40af; font-family: 'Courier New', monospace; tracking: 0.15em;">
                            {otp_code}
                        </div>
                    </div>
                </div>

                <!-- Important Info Section -->
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin: 25px 0;">
                    <p style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; color: #92400e;">
                        ⚠️ {_("Important")}:
                    </p>
                    <table width="100%" border="0" cellspacing="0" cellpadding="0">
                        <tr>
                            <td style="padding: 4px 0; font-size: 14px; color: #b45309; line-height: 1.5;">
                                • {_("This code will expire in {minutes} minutes").format(minutes=settings.OTP_EXPIRY_MINUTES)}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-size: 14px; color: #b45309; line-height: 1.5;">
                                • {_("Never share this code with anyone")}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-size: 14px; color: #b45309; line-height: 1.5;">
                                • {_("Enter the code exactly as shown")}
                            </td>
                        </tr>
                    </table>
                </div>

                <!-- Security Notice -->
                <div style="background: #f0fdf4; border-left: 4px solid #22c55e; padding: 16px; border-radius: 8px; margin: 20px 0 0 0;">
                    <p style="margin: 0; font-size: 13px; color: #166534; line-height: 1.5;">
                        <strong>✓ {_("Security tip:")}</strong> {_("If you didn't request this verification code, you can safely ignore this email. Your account remains secure.")}
                    </p>
                </div>
            </td>
        </tr>
    """

    html_content = _create_safe_html_template(
        preheader_text, subject, content_body, sender_footer=True
    )

    verification_text = _("your verification code is:")
    expiry_text = _("This code will expire in {minutes} minutes").format(
        minutes=settings.OTP_EXPIRY_MINUTES
    )
    share_warning = _("Never share this code.")
    code_label = _("Verification code:")

    plain_text = _create_plain_text_version(
        f"{subject} - {_('Hi')} {full_name}, {verification_text}: {otp_code}. {expiry_text}. {share_warning}",
        f"{code_label}: {otp_code}",
    )

    # Create escape URL for List-Unsubscribe header
    from urllib.parse import quote

    unsubscribe_url = f"{settings.APP_BASE_URL}/unsubscribe?email={quote(email)}"

    try:
        logger.info(f"Attempting to send OTP email to {email} via Resend")
        logger.debug(f"Resend API Key configured: {bool(settings.EMAIL_API_KEY)}")
        logger.debug(f"From address: {settings.EMAIL_FROM_ADDRESS}")
        logger.debug(f"From name: {settings.EMAIL_FROM_NAME}")
        logger.debug(f"OTP code: {otp_code}")

        api_response = resend.Emails.send(
            {
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
                "to": [email],
                "subject": subject,
                "html": html_content,
                "text": plain_text,
                "headers": {
                    "List-Unsubscribe": f"<{unsubscribe_url}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    "X-Auto-Response-Suppress": "AutoReply, DR, NDR, RN, NRN",
                    "X-Transaction-Type": "transactional",
                    "X-Email-Type": "authentication",
                },
            }
        )
        logger.info(f"OTP email sent successfully to {email}: {api_response}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
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
    subject = _("Your account has been approved")
    preheader_text = _("Welcome to {app_name} - your account is now approved!").format(
        app_name=settings.app_name
    )

    content_body = f"""
        <tr>
            <td style="padding: 40px 30px; background-color: #ecfdf5;">
                <h2 style="margin: 0 0 20px 0; font-size: 24px; font-weight: normal; color: #065f46;">{_("Account Approved! 🎉")}</h2>
                <p style="margin: 0 0 25px 0; font-size: 16px; line-height: 1.6; color: #374151;">
                    {_("Congratulations")} {full_name}!<br><br>
                    {_("Your account has been approved and you can now log in to {app_name}.").format(app_name=settings.app_name)}
                </p>

                <table border="0" cellspacing="0" cellpadding="0" style="margin: 30px auto;">
                    <tr>
                        <td style="border-radius: 6px; background-color: #10b981;" bgcolor="#10b981">
                            <a href="{login_url}" style="padding: 14px 28px; border: 1px solid #10b981; border-radius: 6px; color: #ffffff; display: inline-block; font-family: sans-serif; font-size: 16px; font-weight: bold; text-decoration: none;" class="mobile-font-size">
                                {_("Get Started Now")}
                            </a>
                        </td>
                    </tr>
                </table>

                <p style="margin: 25px 0 15px 0; font-size: 14px; line-height: 1.6; color: #6b7280;">
                    {_("You can now access all features by entering your email address at:")}<br>
                    <a href="{login_url}" style="color: #10b981; word-break: break-all;">{login_url}</a>
                </p>

                <hr style="border: none; border-top: 1px solid #d1fae5; margin: 30px 0;">
                <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #6b7280;">
                    <strong>{_("What happens next?")}</strong><br>
                    {_("You can now request magic links for passwordless login, upload files, and access your account securely. We use passwordless authentication for your security - no passwords needed!")}
                </p>
            </td>
        </tr>
    """

    html_content = _create_safe_html_template(
        preheader_text, subject, content_body, sender_footer=True
    )

    great_news = _("Great news")
    approved_msg = _(
        "Your account has been approved and you can now login to {app_name}"
    ).format(app_name=settings.app_name)
    get_started = _("Get started")
    login_label = _("Login to your account")

    plain_text = _create_plain_text_version(
        f"{great_news} {full_name}! {approved_msg}. {get_started}: {login_url}",
        f"{login_label}: {login_url}",
    )

    # Create escape URL for List-Unsubscribe header (though unlikely to be used for approval emails)
    from urllib.parse import quote

    unsubscribe_url = f"{settings.APP_BASE_URL}/unsubscribe?email={quote(email)}"

    try:
        logger.info(f"Attempting to send account approved email to {email} via Resend")
        api_response = resend.Emails.send(
            {
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
                "to": [email],
                "subject": subject,
                "html": html_content,
                "text": plain_text,
                "headers": {
                    "List-Unsubscribe": f"<{unsubscribe_url}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    "X-Auto-Response-Suppress": "AutoReply, DR, NDR, RN, NRN",
                    "X-Transaction-Type": "transactional",
                    "X-Email-Type": "notification",
                },
            }
        )
        logger.info(
            f"Account approved email sent successfully to {email}: {api_response}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send account approved email to {email}: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
        return False
