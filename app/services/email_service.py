from email.message import EmailMessage
from typing import Optional
from loguru import logger
import aiosmtplib
from app.core.config import settings

class EmailService:
    @staticmethod
    async def send_otp_email(to_email: str, otp_code: str, full_name: Optional[str] = None) -> bool:
        """
        Sends OTP verification email via SMTP if configured, or outputs clearly to the logger in development.
        """
        subject = f"Your Verification Code - {otp_code}"
        name_greeting = f"Hello {full_name}," if full_name else "Hello,"
        
        body_text = f"""{name_greeting}

Your verification code is: {otp_code}

This code is valid for {settings.OTP_EXPIRE_SECONDS // 60} minutes. Please do not share this code with anyone.

If you did not request this code, please ignore this email.
"""

        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                <h2 style="color: #2563eb; margin-top: 0;">Verification Code</h2>
                <p>{name_greeting}</p>
                <p>Please use the following 6-digit code to complete your verification:</p>
                <div style="background: #f1f5f9; padding: 16px; text-align: center; border-radius: 6px; font-size: 28px; font-weight: bold; letter-spacing: 6px; color: #0f172a; margin: 24px 0;">
                    {otp_code}
                </div>
                <p style="color: #64748b; font-size: 14px;">This code will expire in <strong>{settings.OTP_EXPIRE_SECONDS // 60} minutes</strong>.</p>
                <p style="color: #64748b; font-size: 14px;">If you did not request this code, you can safely ignore this message.</p>
            </body>
        </html>
        """

        # Log clearly for local development/debugging
        logger.info(f"============================================================")
        logger.info(f" [DEV EMAIL OTP] Destination: {to_email} | OTP: {otp_code}")
        logger.info(f"============================================================")

        # If SMTP settings are fully populated, attempt real SMTP transmission
        if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
            try:
                message = EmailMessage()
                from_addr = settings.EMAILS_FROM_EMAIL or settings.SMTP_USER
                from_name = settings.EMAILS_FROM_NAME or "Noesis Auth"
                message["From"] = f"{from_name} <{from_addr}>"
                message["To"] = to_email
                message["Subject"] = subject
                message.set_content(body_text)
                message.add_alternative(html_content, subtype="html")

                await aiosmtplib.send(
                    message,
                    hostname=settings.SMTP_HOST,
                    port=settings.SMTP_PORT or 587,
                    username=settings.SMTP_USER,
                    password=settings.SMTP_PASSWORD,
                    start_tls=True if (settings.SMTP_PORT or 587) == 587 else False
                )
                logger.info(f"Successfully dispatched OTP email via SMTP to {to_email}")
                return True
            except Exception as e:
                logger.error(f"Failed to send email via SMTP to {to_email}: {e}")
                # We do not fail the request if local logging captured the OTP
                return False

        return True
