"""
Background email worker for asynchronous email processing.

Processes emails from Redis queue with retry logic and error handling.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .redis_utils import email_queue
from .email import send_magic_link, send_registration_notification, send_otp_email, send_account_approved
from .logger import get_logger
from .repository import get_user_by_email
from .db import AsyncSessionLocal

logger = get_logger(__name__)


class EmailWorker:
    """Background worker for processing email queue."""

    def __init__(self, poll_interval: int = 5):
        self.poll_interval = poll_interval
        self.running = False
        self.processing_count = 0

    async def start(self):
        """Start the email worker."""
        if self.running:
            logger.warning("Email worker is already running")
            return

        self.running = True
        logger.info("Starting email worker")

        while self.running:
            try:
                # Requeue any stale items
                requeued = await email_queue.requeue_stale(max_processing_time=300)
                if requeued > 0:
                    logger.info(f"Requeued {requeued} stale email items")

                # Process next item from queue
                email_item = await email_queue.dequeue(timeout=1)

                if email_item:
                    await self._process_email(email_item)
                else:
                    # No items, wait before next poll
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Email worker error: {e}")
                await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the email worker."""
        logger.info("Stopping email worker")
        self.running = False

    async def _process_email(self, email_item: Dict[str, Any]):
        """Process a single email item."""
        self.processing_count += 1
        start_time = datetime.utcnow()

        try:
            email_data = email_item.get("data", {})
            email_type = email_data.get("type")
            recipient = email_data.get("recipient")

            if not email_type or not recipient:
                logger.error(f"Invalid email item: {email_item}")
                return

            logger.info(f"Processing email #{self.processing_count}: {email_type} to {recipient}")

            # Route to appropriate email function
            success = await self._route_email(email_type, email_data)

            if success:
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    f"Email sent successfully: {email_type} to {recipient} "
                    f"(took {processing_time:.2f}s)"
                )
            else:
                logger.error(f"Failed to send email: {email_type} to {recipient}")

        except Exception as e:
            logger.error(f"Error processing email item {email_item}: {e}")

    async def _route_email(self, email_type: str, email_data: Dict[str, Any]) -> bool:
        """Route email to appropriate sending function."""

        try:
            if email_type == "magic_link":
                return await self._send_magic_link_email(email_data)
            elif email_type == "registration_notification":
                return await self._send_registration_notification(email_data)
            elif email_type == "otp":
                return await self._send_otp_email(email_data)
            elif email_type == "account_approved":
                return await self._send_account_approved(email_data)
            else:
                logger.error(f"Unknown email type: {email_type}")
                return False

        except Exception as e:
            logger.error(f"Error routing email {email_type}: {e}")
            return False

    async def _send_magic_link_email(self, email_data: Dict[str, Any]) -> bool:
        """Send magic link email."""
        recipient = email_data.get("recipient")
        full_name = email_data.get("full_name", "User")
        magic_link = email_data.get("magic_link")

        if not recipient or not magic_link:
            logger.error("Missing required fields for magic link email")
            return False

        return await send_magic_link(recipient, full_name, magic_link)

    async def _send_registration_notification(self, email_data: Dict[str, Any]) -> bool:
        """Send registration notification email."""
        recipient = email_data.get("recipient")
        new_user_email = email_data.get("new_user_email")
        new_user_name = email_data.get("new_user_name")
        approval_url = email_data.get("approval_url")

        if not all([recipient, new_user_email, new_user_name, approval_url]):
            logger.error("Missing required fields for registration notification")
            return False

        return await send_registration_notification(
            recipient, new_user_email, new_user_name, approval_url
        )

    async def _send_otp_email(self, email_data: Dict[str, Any]) -> bool:
        """Send OTP email."""
        recipient = email_data.get("recipient")
        otp_code = email_data.get("otp_code")
        full_name = email_data.get("full_name")

        if not recipient or not otp_code:
            logger.error("Missing required fields for OTP email")
            return False

        # Get user name if not provided
        if not full_name:
            full_name = await self._get_user_name(recipient)

        return await send_otp_email(recipient, full_name, otp_code)

    async def _send_account_approved(self, email_data: Dict[str, Any]) -> bool:
        """Send account approved email."""
        recipient = email_data.get("recipient")
        full_name = email_data.get("full_name")
        login_url = email_data.get("login_url")

        if not recipient or not login_url:
            logger.error("Missing required fields for account approved email")
            return False

        return await send_account_approved(recipient, full_name, login_url)

    async def _get_user_name(self, email: str) -> str:
        """Get user name from database."""
        try:
            async with AsyncSessionLocal() as session:
                user = await get_user_by_email(session, email)
                if user:
                    return user.full_name
        except Exception as e:
            logger.error(f"Error getting user name for {email}: {e}")

        return "User"


# Global email worker instance
email_worker = EmailWorker()


async def queue_email(
    email_type: str,
    recipient: str,
    data: Optional[Dict[str, Any]] = None,
    priority: int = 0
) -> bool:
    """
    Queue an email for background processing.

    Args:
        email_type: Type of email (magic_link, registration_notification, otp, account_approved)
        recipient: Email recipient
        data: Additional email data
        priority: Priority (0 = highest, 10 = lowest)

    Returns:
        True if successfully queued, False otherwise
    """
    try:
        email_data = {
            "type": email_type,
            "recipient": recipient,
            "queued_at": datetime.utcnow().isoformat(),
            **(data or {})
        }

        success = await email_queue.enqueue(email_data, priority=priority)

        if success:
            logger.debug(f"Queued email: {email_type} to {recipient}")
        else:
            logger.error(f"Failed to queue email: {email_type} to {recipient}")

        return success

    except Exception as e:
        logger.error(f"Error queuing email {email_type} to {recipient}: {e}")
        return False


# Convenience functions for queuing common email types
async def queue_magic_link(recipient: str, full_name: str, magic_link: str) -> bool:
    """Queue magic link email."""
    return await queue_email(
        "magic_link",
        recipient,
        {
            "full_name": full_name,
            "magic_link": magic_link
        },
        priority=5  # Medium priority
    )


async def queue_registration_notification(
    recipient: str,
    new_user_email: str,
    new_user_name: str,
    approval_url: str
) -> bool:
    """Queue registration notification email."""
    return await queue_email(
        "registration_notification",
        recipient,
        {
            "new_user_email": new_user_email,
            "new_user_name": new_user_name,
            "approval_url": approval_url
        },
        priority=3  # Higher priority for admin notifications
    )


async def queue_otp_email(recipient: str, otp_code: str, full_name: Optional[str] = None) -> bool:
    """Queue OTP email."""
    return await queue_email(
        "otp",
        recipient,
        {
            "otp_code": otp_code,
            "full_name": full_name
        },
        priority=1  # High priority for time-sensitive OTP
    )


async def queue_account_approved(recipient: str, full_name: str, login_url: str) -> bool:
    """Queue account approved email."""
    return await queue_email(
        "account_approved",
        recipient,
        {
            "full_name": full_name,
            "login_url": login_url
        },
        priority=2  # High priority for user notifications
    )