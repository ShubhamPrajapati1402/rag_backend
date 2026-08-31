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
        display_name = full_name or to_email.split("@")[0]
        name_greeting = f"Hello {display_name},"
        
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
        display_name = full_name or to_email.split("@")[0]
        name_greeting = f"Hi {display_name},"
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

    @staticmethod
    async def send_developer_invite_email(
        to_email: str,
        inviter_email: str,
        inviter_name: Optional[str] = None
    ) -> bool:
        """
        Sends a beautifully formatted Developer Team Invitation email when developer privileges are granted.
        """
        subject = "You've been invited as a Developer to Noesis RAG Studio"
        display_inviter = inviter_name or inviter_email
        eval_url = f"{settings.FRONTEND_URL}/developer/evaluation"
        display_name = to_email.split("@")[0]

        body_text = f"""Hello {display_name},

You have been granted Developer & Superuser privileges on the Noesis RAG Studio platform by {display_inviter} ({inviter_email}).

As an authorized Developer, you have full access to:
- RAGAs Automated Benchmark & Quality Evaluation Suite
- Granular Atomic Claim Verification Audits & Hallucination Diagnostics
- Real-Time Retrieval, Reranking & LangGraph Pipeline Telemetry
- Team Access & Developer Privilege Management

You can access the Developer Studio immediately:
{eval_url}

Sign in using your Google account or email ({to_email}) to get started.

Best regards,
The Noesis Platform Team
"""

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #f1f5f9; margin: 0; padding: 24px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #1e1e1e; border-radius: 14px; overflow: hidden; border: 1px solid #333333; box-shadow: 0 12px 36px rgba(0, 0, 0, 0.4); }}
                .header {{ background: linear-gradient(135deg, #4f46e5 0%, #6366f1 50%, #8b5cf6 100%); padding: 32px 24px; text-align: center; }}
                .badge {{ display: inline-block; background: rgba(255, 255, 255, 0.2); backdrop-filter: blur(4px); color: #ffffff; font-size: 11px; font-weight: 700; letter-spacing: 0.08em; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; margin-bottom: 10px; }}
                .header h1 {{ margin: 0; font-size: 26px; color: #ffffff; letter-spacing: -0.5px; font-weight: 700; }}
                .header p {{ margin: 8px 0 0 0; color: #e0e7ff; font-size: 14px; }}
                .content {{ padding: 30px 24px; }}
                .inviter-card {{ background: #262626; border: 1px solid #3a3a3a; border-radius: 10px; padding: 14px 16px; margin-bottom: 22px; display: flex; align-items: center; gap: 10px; }}
                .inviter-avatar {{ width: 34px; height: 34px; border-radius: 50%; background: #6366f1; color: #ffffff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; }}
                .inviter-text {{ font-size: 13px; color: #d4d4d4; line-height: 1.4; }}
                .inviter-email {{ color: #a5b4fc; font-weight: 600; }}
                .feature-list {{ margin: 20px 0; }}
                .feature-item {{ background: #262626; border: 1px solid #333333; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; }}
                .feature-title {{ font-size: 14px; font-weight: 600; color: #ffffff; margin: 0 0 3px 0; }}
                .feature-desc {{ font-size: 12px; color: #a3a3a3; margin: 0; line-height: 1.4; }}
                .cta-box {{ text-align: center; margin: 30px 0 10px 0; }}
                .cta-btn {{ display: inline-block; background: #6366f1; color: #ffffff !important; font-weight: 600; font-size: 14px; padding: 13px 28px; border-radius: 10px; text-decoration: none; box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4); }}
                .cta-btn:hover {{ background: #4f46e5; }}
                .footer {{ background: #171717; padding: 18px 24px; text-align: center; border-top: 1px solid #2a2a2a; font-size: 11px; color: #737373; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <span class="badge">DEVELOPER ACCESS GRANTED</span>
                    <h1>Welcome to the Developer Team</h1>
                    <p>Noesis Enterprise Agentic RAG Platform</p>
                </div>
                <div class="content">
                    <div class="inviter-card">
                        <div class="inviter-avatar">{display_inviter[0].upper()}</div>
                        <div class="inviter-text">
                            <strong>{display_inviter}</strong> has invited you to the developer team with full administrative and benchmarking privileges.
                        </div>
                    </div>

                    <p style="font-size: 14px; color: #cccccc; line-height: 1.5; margin-bottom: 16px;">
                        Your account <strong>{to_email}</strong> is now pre-authorized for Developer Mode. You have unlocked access to deep diagnostics and RAG auditing tools:
                    </p>

                    <div class="feature-list">
                        <div class="feature-item">
                            <div class="feature-title">🛡️ RAGAs Automated Quality Benchmark</div>
                            <div class="feature-desc">Dynamically test multi-document retrieval with Faithfulness, Answer Relevance, and Context Precision scorecards.</div>
                        </div>

                        <div class="feature-item">
                            <div class="feature-title">🔬 Atomic Claim Verification Audits</div>
                            <div class="feature-desc">Inspect sentence-level groundedness checks and zero-tolerance hallucination detection.</div>
                        </div>

                        <div class="feature-item">
                            <div class="feature-title">⚡ Multi-Modal Ingestion & Telemetry</div>
                            <div class="feature-desc">Monitor LangGraph stateful execution nodes, FTS hybrid searches, and cross-attention reranking.</div>
                        </div>
                    </div>

                    <div class="cta-box">
                        <a href="{eval_url}" class="cta-btn">Access Developer Suite →</a>
                    </div>
                </div>
                <div class="footer">
                    <p>Signed in with {to_email} to access developer features. © Noesis RAG Platform.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Log clearly for development
        logger.info(f"============================================================")
        logger.info(f" [DEV DEVELOPER INVITE EMAIL] Sent to: {to_email} | Invited by: {inviter_email}")
        logger.info(f"============================================================")

        # Dispatch via SMTP if configured
        if settings.SMTP_HOST and settings.SMTP_PORT and settings.SMTP_USER and settings.SMTP_PASSWORD:
            try:
                message = EmailMessage()
                from_addr = settings.EMAILS_FROM_EMAIL or settings.SMTP_USER
                from_name = settings.EMAILS_FROM_NAME or "Noesis Developer Team"
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
                logger.info(f"Successfully dispatched Developer Invite email via SMTP to {to_email}")
                return True
            except Exception as e:
                logger.error(f"Failed to send developer invite email via SMTP to {to_email}: {e}")
                return False

        return True

