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
        if settings.SMTP_HOST and settings.SMTP_PORT and settings.SMTP_USER and settings.SMTP_PASSWORD:
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
                    port=settings.SMTP_PORT,
                    username=settings.SMTP_USER,
                    password=settings.SMTP_PASSWORD,
                    start_tls=True if settings.SMTP_PORT == 587 else False
                )
                logger.info(f"Successfully dispatched OTP email via SMTP to {to_email}")
                return True
            except Exception as e:
                logger.error(f"Failed to send email via SMTP to {to_email}: {e}")
                # We do not fail the request if local logging captured the OTP
                return False

        return True

    @staticmethod
    async def send_welcome_email(to_email: str, full_name: Optional[str] = None) -> bool:
        """
        Sends a rich Welcome Email introducing Noesis and its key platform capabilities.
        """
        subject = "Welcome to Noesis - Supercharge Your Knowledge with Agentic RAG"
        name_greeting = f"Hi {full_name}," if full_name else "Hi there,"
        dashboard_url = settings.FRONTEND_URL

        body_text = f"""{name_greeting}

Welcome to Noesis! Your account is now active and ready to use.

Key Features of Noesis:
1. Multi-Format Ingestion: Effortlessly upload and parse 10+ document types (PDFs, Markdown, Word, Excel, CSV, PPTX, JSON, HTML).
2. Intelligent Hybrid OCR: Scans and extracts complex tables and images with zero structural data loss.
3. Agentic RAG & Vector Search: Chat with your documents using blazing-fast Groq LLMs and state-of-the-art vector embeddings.
4. Secure Workspaces: Private, isolated, and encrypted storage for all your critical data.

Get started by visiting your dashboard: {dashboard_url}

Best regards,
The Noesis Team
"""

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 12px; overflow: hidden; border: 1px solid #334155; }}
                .header {{ background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 32px 24px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; color: #ffffff; letter-spacing: -0.5px; font-weight: 700; }}
                .header p {{ margin: 8px 0 0 0; color: #e2e8f0; font-size: 15px; }}
                .content {{ padding: 32px 24px; }}
                .greeting {{ font-size: 18px; font-weight: 600; color: #f8fafc; margin-bottom: 16px; }}
                .intro {{ font-size: 15px; line-height: 1.6; color: #94a3b8; margin-bottom: 24px; }}
                .feature-grid {{ margin: 24px 0; }}
                .feature-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-bottom: 12px; display: flex; align-items: flex-start; }}
                .feature-icon {{ font-size: 22px; margin-right: 14px; line-height: 1; }}
                .feature-title {{ font-size: 15px; font-weight: 600; color: #f1f5f9; margin: 0 0 4px 0; }}
                .feature-desc {{ font-size: 13px; color: #94a3b8; margin: 0; line-height: 1.4; }}
                .cta-box {{ text-align: center; margin: 32px 0 16px 0; }}
                .cta-btn {{ display: inline-block; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); color: #ffffff !important; font-weight: 600; font-size: 15px; padding: 14px 32px; border-radius: 8px; text-decoration: none; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3); }}
                .footer {{ background: #0f172a; padding: 20px 24px; text-align: center; border-top: 1px solid #334155; font-size: 12px; color: #64748b; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Noesis</h1>
                    <p>Next-Gen Enterprise Retrieval-Augmented Generation</p>
                </div>
                <div class="content">
                    <div class="greeting">{name_greeting}</div>
                    <p class="intro">Your account is successfully verified and active! Noesis empowers you to ingest, understand, and extract deep insights from your data using state-of-the-art AI.</p>
                    
                    <div class="feature-grid">
                        <div class="feature-card">
                            <div class="feature-icon">📄</div>
                            <div>
                                <h4 class="feature-title">Multi-Format Ingestion</h4>
                                <p class="feature-desc">Upload 10+ formats including PDF, Markdown, DOCX, CSV, Excel, PPTX, JSON, and HTML seamlessly.</p>
                            </div>
                        </div>

                        <div class="feature-card">
                            <div class="feature-icon">⚡</div>
                            <div>
                                <h4 class="feature-title">Hybrid Intelligent OCR & Parsing</h4>
                                <p class="feature-desc">Dynamic visual classification preserves tables, images, and complex page layouts with 100% structural fidelity.</p>
                            </div>
                        </div>

                        <div class="feature-card">
                            <div class="feature-icon">🧠</div>
                            <div>
                                <h4 class="feature-title">Agentic RAG & Semantic Search</h4>
                                <p class="feature-desc">Ask complex, multi-turn questions powered by high-speed Groq LLMs and Hugging Face vector embeddings.</p>
                            </div>
                        </div>

                        <div class="feature-card">
                            <div class="feature-icon">🔒</div>
                            <div>
                                <h4 class="feature-title">Secure & Isolated Workspaces</h4>
                                <p class="feature-desc">Your documents and vectors are isolated and protected with enterprise-level security.</p>
                            </div>
                        </div>
                    </div>

                    <div class="cta-box">
                        <a href="{dashboard_url}" class="cta-btn">Open Your Dashboard</a>
                    </div>
                </div>
                <div class="footer">
                    <p>© Noesis RAG Platform. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Development console logging
        logger.info(f"============================================================")
        logger.info(f" [DEV WELCOME EMAIL] Sent to: {to_email}")
        logger.info(f"============================================================")

        # Dispatch via SMTP if credentials are configured
        if settings.SMTP_HOST and settings.SMTP_PORT and settings.SMTP_USER and settings.SMTP_PASSWORD:
            try:
                message = EmailMessage()
                from_addr = settings.EMAILS_FROM_EMAIL or settings.SMTP_USER
                from_name = settings.EMAILS_FROM_NAME or "Noesis"
                message["From"] = f"{from_name} <{from_addr}>"
                message["To"] = to_email
                message["Subject"] = subject
                message.set_content(body_text)
                message.add_alternative(html_content, subtype="html")

                await aiosmtplib.send(
                    message,
                    hostname=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    username=settings.SMTP_USER,
                    password=settings.SMTP_PASSWORD,
                    start_tls=True if settings.SMTP_PORT == 587 else False
                )
                logger.info(f"Successfully dispatched Welcome email via SMTP to {to_email}")
                return True
            except Exception as e:
                logger.error(f"Failed to send welcome email via SMTP to {to_email}: {e}")
                return False

        return True

