from email.message import EmailMessage
from typing import Optional
from loguru import logger
import aiosmtplib
from app.core.config import settings

class EmailService:
    @staticmethod
    async def send_otp_email(to_email: str, otp_code: str, full_name: Optional[str] = None) -> bool:
        """
        Sends OTP verification email via SMTP with a bulletproof, rich table-based email template.
        """
        subject = f"Your Verification Code: {otp_code} — Noesis"
        display_name = full_name or to_email.split("@")[0]
        name_greeting = f"Hello {display_name},"
        
        body_text = f"""{name_greeting}

Your verification code for Noesis is: {otp_code}

This code will expire in {settings.OTP_EXPIRE_SECONDS // 60} minutes. Please do not share this code with anyone.

If you did not request this verification code, you can safely ignore this email.

Best regards,
The Noesis Platform Team
"""

        html_content = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Verification Code - Noesis</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 36px 12px;">
  <tr>
    <td align="center">
      <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 540px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #e2e8f0;">
        <!-- Header -->
        <tr>
          <td align="center" style="background-color: #4f46e5; background-image: linear-gradient(135deg, #4338ca 0%, #6366f1 50%, #7c3aed 100%); padding: 32px 24px; text-align: center;">
            <table border="0" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center" style="background: rgba(255, 255, 255, 0.2); border: 1px solid rgba(255, 255, 255, 0.35); border-radius: 20px; padding: 4px 12px;">
                  <span style="color: #ffffff; font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase;">SECURITY VERIFICATION</span>
                </td>
              </tr>
            </table>
            <h1 style="color: #ffffff; font-size: 24px; font-weight: 800; margin: 12px 0 0 0; letter-spacing: -0.4px;">
              Noesis Authentication
            </h1>
          </td>
        </tr>

        <!-- Content -->
        <tr>
          <td style="padding: 32px 28px;">
            <h2 style="font-size: 16px; font-weight: 700; color: #0f172a; margin: 0 0 12px 0;">{name_greeting}</h2>
            <p style="font-size: 14px; color: #475569; line-height: 1.55; margin: 0 0 24px 0;">
              Please use the single-use verification code below to complete authentication:
            </p>

            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 24px;">
              <tr>
                <td align="center" style="background-color: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px;">
                  <div style="font-family: 'JetBrains Mono', Consolas, Monaco, monospace; font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #4f46e5; margin: 0;">
                    {otp_code}
                  </div>
                  <div style="font-size: 12px; color: #64748b; margin-top: 8px; font-weight: 500;">
                    ⏱️ Code expires in {settings.OTP_EXPIRE_SECONDS // 60} minutes
                  </div>
                </td>
              </tr>
            </table>

            <p style="font-size: 13px; color: #94a3b8; line-height: 1.5; margin: 0;">
              If you did not request this verification code, you can safely ignore this email.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background-color: #f8fafc; padding: 18px 28px; border-top: 1px solid #f1f5f9; text-align: center; font-size: 12px; color: #94a3b8;">
            © Noesis RAG Platform. Sent to {to_email}.
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""

        logger.info(f"============================================================")
        logger.info(f" [DEV EMAIL OTP] Destination: {to_email} | OTP: {otp_code}")
        logger.info(f"============================================================")

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
                return False

        return True

    @staticmethod
    async def send_welcome_email(to_email: str, full_name: Optional[str] = None) -> bool:
        """
        Sends a rich Welcome Email introducing Noesis and its key platform capabilities.
        """
        subject = "Welcome to Noesis — Enterprise Agentic RAG Platform"
        display_name = full_name or to_email.split("@")[0]
        name_greeting = f"Hi {display_name},"
        dashboard_url = settings.FRONTEND_URL

        body_text = f"""{name_greeting}

Welcome to Noesis! Your account is active and ready to use.

Key Capabilities:
- Multi-Format Document Ingestion (PDF, Markdown, DOCX, CSV, Excel, PPTX, JSON, HTML)
- Hybrid Intelligent OCR & Semantic Vector Search
- Stateful LangGraph Agentic RAG with Citation Groundedness
- Private & Encrypted Workspaces

Open your workspace: {dashboard_url}

Best regards,
The Noesis Platform Team
"""

        html_content = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Welcome to Noesis</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 36px 12px;">
  <tr>
    <td align="center">
      <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #e2e8f0;">
        <tr>
          <td align="center" style="background-color: #4f46e5; background-image: linear-gradient(135deg, #4338ca 0%, #6366f1 50%, #7c3aed 100%); padding: 36px 24px; text-align: center;">
            <h1 style="color: #ffffff; font-size: 26px; font-weight: 800; margin: 0 0 6px 0; letter-spacing: -0.5px;">
              Welcome to Noesis
            </h1>
            <p style="color: #e0e7ff; font-size: 14px; margin: 0; line-height: 1.4;">
              Enterprise Agentic RAG & Quality Verification Platform
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding: 32px 28px;">
            <h2 style="font-size: 16px; font-weight: 700; color: #0f172a; margin: 0 0 10px 0;">{name_greeting}</h2>
            <p style="font-size: 14px; line-height: 1.6; color: #475569; margin: 0 0 24px 0;">
              Your account is active! You can now ingest multi-modal documents, run deep RAG queries with verified citations, and evaluate quality benchmarks.
            </p>

            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 28px;">
              <tr>
                <td style="padding: 12px 14px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 10px;">
                  <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 2px;">📄 Multi-Format Ingestion</div>
                  <div style="font-size: 12.5px; color: #64748b;">Upload PDFs, DOCX, Markdown, CSV, Excel, and PPTX with full layout preservation.</div>
                </td>
              </tr>
              <tr><td height="8"></td></tr>
              <tr>
                <td style="padding: 12px 14px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
                  <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 2px;">🧠 Stateful LangGraph RAG</div>
                  <div style="font-size: 12.5px; color: #64748b;">Reason across multi-turn queries with grounded citations and zero hallucination risk.</div>
                </td>
              </tr>
            </table>

            <table border="0" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td align="center">
                  <a href="{dashboard_url}" style="display: inline-block; background-color: #4f46e5; background-image: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%); color: #ffffff; font-size: 14.5px; font-weight: 700; text-decoration: none; padding: 14px 36px; border-radius: 10px; box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);">
                    Open Your Workspace →
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="background-color: #f8fafc; padding: 18px 28px; border-top: 1px solid #f1f5f9; text-align: center; font-size: 12px; color: #94a3b8;">
            © Noesis RAG Platform. Sent to {to_email}.
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""

        logger.info(f"============================================================")
        logger.info(f" [DEV WELCOME EMAIL] Sent to: {to_email}")
        logger.info(f"============================================================")

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
        inviter_name: Optional[str] = None,
        role: str = "MEMBER",
        invite_token: Optional[str] = None
    ) -> bool:
        """
        Sends an interactive, visually stunning Developer Team Invitation email with a vibrant purple header and interactive layout.
        """
        role_label = "Admin" if role.upper() == "ADMIN" else "Developer Member"
        role_badge = "🛡️ ADMIN INVITATION" if role.upper() == "ADMIN" else "💻 DEVELOPER INVITATION"
        subject = f"You've been invited as {role_label} to Noesis RAG Studio"
        display_inviter = inviter_name or inviter_email
        display_name = to_email.split("@")[0]
        
        if invite_token:
            accept_url = f"{settings.FRONTEND_URL}/accept-invite?token={invite_token}"
        else:
            accept_url = f"{settings.FRONTEND_URL}/developer/evaluation"

        body_text = f"""Hello {display_name},

You have been invited to join the Noesis Developer Team as {role_label} by {display_inviter} ({inviter_email}).

To accept your invitation and activate your developer privileges, please click the secure link below:
{accept_url}

Security & Recipient Policy:
- This invitation link is strictly intended for {to_email}.
- This invitation link expires in 48 hours from the time it was dispatched.

As an authorized {role_label}, you will have access to:
- RAGAs Automated Benchmark & Quality Evaluation Suite
- Granular Atomic Claim Verification Audits & Hallucination Diagnostics
- Real-Time Retrieval, Reranking & LangGraph Pipeline Telemetry
{"- Team Access & Member Invitation Management" if role.upper() == "ADMIN" else "- Benchmark Execution & Test Case Inspection"}

Best regards,
The Noesis Platform Team
"""

        html_content = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Noesis Developer Invitation</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 36px 12px;">
  <tr>
    <td align="center">
      <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 12px 36px rgba(0,0,0,0.09); border: 1px solid #e2e8f0;">
        
        <!-- Hero Purple / Indigo Gradient Header -->
        <tr>
          <td align="center" style="background-color: #4f46e5; background-image: linear-gradient(135deg, #3730a3 0%, #4f46e5 45%, #7c3aed 100%); padding: 36px 24px; text-align: center;">
            <table border="0" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center" style="background-color: rgba(255, 255, 255, 0.2); border: 1px solid rgba(255, 255, 255, 0.35); border-radius: 20px; padding: 5px 14px;">
                  <span style="color: #ffffff; font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase;">
                    {role_badge}
                  </span>
                </td>
              </tr>
            </table>
            <h1 style="color: #ffffff; font-size: 25px; font-weight: 800; margin: 14px 0 6px 0; letter-spacing: -0.5px; line-height: 1.25;">
              Welcome to the Developer Team
            </h1>
            <p style="color: #e0e7ff; font-size: 14px; margin: 0; line-height: 1.45;">
              Noesis Enterprise Agentic RAG Platform
            </p>
          </td>
        </tr>

        <!-- Main Content Body -->
        <tr>
          <td style="padding: 30px 26px;">
            
            <!-- Inviter Hero Card (Soft Violet Accent) -->
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 12px; padding: 16px 18px; margin-bottom: 20px;">
              <tr>
                <td>
                  <span style="font-size: 14.5px; line-height: 1.5; color: #1e293b;">
                    👋 <strong style="color: #4338ca;">{display_inviter}</strong> has invited you to join the team with full <span style="background-color: #ede9fe; color: #6d28d9; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 13.5px;">{role_label}</span> privileges.
                  </span>
                </td>
              </tr>
            </table>

            <!-- Security & 48h Expiry Callout (Indigo Accent) -->
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #6366f1; border-radius: 8px; padding: 12px 14px; margin-bottom: 24px;">
              <tr>
                <td>
                  <div style="font-size: 13px; font-weight: 700; color: #4338ca; margin-bottom: 2px;">
                    🔒 Recipient Security Policy
                  </div>
                  <div style="font-size: 12px; color: #475569; line-height: 1.45;">
                    This invitation is cryptographically bound to <strong>{to_email}</strong> and expires in <strong>48 hours</strong> from dispatch.
                  </div>
                </td>
              </tr>
            </table>

            <!-- Feature Capabilities Title -->
            <div style="font-size: 12px; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; color: #64748b; margin-bottom: 12px;">
              ⚡ UNLOCKED DEVELOPER CAPABILITIES
            </div>

            <!-- Feature 1: RAGAs Benchmarking (Royal Indigo Accent) -->
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8faff; border: 1px solid #e0e7ff; border-left: 4px solid #4f46e5; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px;">
              <tr>
                <td width="42" valign="middle" align="center">
                  <div style="background-color: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; border-radius: 8px; width: 36px; height: 36px; line-height: 36px; text-align: center; font-size: 18px;">
                    📊
                  </div>
                </td>
                <td style="padding-left: 12px;">
                  <div style="font-size: 14px; font-weight: 700; color: #1e1b4b; margin-bottom: 2px;">
                    RAGAs Automated Quality Benchmark
                  </div>
                  <div style="font-size: 12.5px; color: #475569; line-height: 1.4;">
                    Evaluate multi-document retrieval with Faithfulness, Answer Relevance, and Context Precision scorecards.
                  </div>
                </td>
              </tr>
            </table>

            <!-- Feature 2: Atomic Claim Audits (Purple/Violet Accent) -->
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #faf5ff; border: 1px solid #f3e8ff; border-left: 4px solid #9333ea; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px;">
              <tr>
                <td width="42" valign="middle" align="center">
                  <div style="background-color: #f3e8ff; color: #6b21a8; border: 1px solid #e9d5ff; border-radius: 8px; width: 36px; height: 36px; line-height: 36px; text-align: center; font-size: 18px;">
                    🎯
                  </div>
                </td>
                <td style="padding-left: 12px;">
                  <div style="font-size: 14px; font-weight: 700; color: #3b0764; margin-bottom: 2px;">
                    Atomic Claim Verification Audits
                  </div>
                  <div style="font-size: 12.5px; color: #475569; line-height: 1.4;">
                    Inspect sentence-level groundedness checks and zero-tolerance hallucination diagnostics.
                  </div>
                </td>
              </tr>
            </table>

            <!-- Feature 3: Pipeline Telemetry (Ocean Sky Blue Accent) -->
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f0f9ff; border: 1px solid #e0f2fe; border-left: 4px solid #0284c7; border-radius: 10px; padding: 14px 16px; margin-bottom: 26px;">
              <tr>
                <td width="42" valign="middle" align="center">
                  <div style="background-color: #e0f2fe; color: #075985; border: 1px solid #bae6fd; border-radius: 8px; width: 36px; height: 36px; line-height: 36px; text-align: center; font-size: 18px;">
                    ⚡
                  </div>
                </td>
                <td style="padding-left: 12px;">
                  <div style="font-size: 14px; font-weight: 700; color: #082f49; margin-bottom: 2px;">
                    Multi-Modal Ingestion & Telemetry
                  </div>
                  <div style="font-size: 12.5px; color: #475569; line-height: 1.4;">
                    Monitor LangGraph stateful execution nodes, FTS hybrid searches, and cross-attention reranking.
                  </div>
                </td>
              </tr>
            </table>

            <!-- Main CTA Button (Indigo / Purple Gradient) -->
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 22px;">
              <tr>
                <td align="center">
                  <a href="{accept_url}" style="display: inline-block; background-color: #4f46e5; background-image: linear-gradient(135deg, #4338ca 0%, #4f46e5 50%, #7c3aed 100%); color: #ffffff !important; font-size: 15px; font-weight: 700; text-decoration: none; padding: 14px 38px; border-radius: 10px; box-shadow: 0 4px 16px rgba(79, 70, 229, 0.4); letter-spacing: -0.2px;">
                    Accept & Join Team as {role_label} →
                  </a>
                </td>
              </tr>
            </table>

            <!-- Clean Activation Roadmap with Benchmark Navigation Steps -->
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px 16px;">
              <tr>
                <td align="center" style="font-size: 11px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; color: #4338ca; padding-bottom: 12px;">
                  🚀 GETTING STARTED: BENCHMARK WORKFLOW
                </td>
              </tr>
              <tr>
                <td>
                  <table border="0" cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                      <td width="31%" align="center" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 6px;">
                        <div style="font-size: 11px; font-weight: 800; color: #4f46e5; margin-bottom: 2px;">STEP 1</div>
                        <div style="font-size: 12px; font-weight: 600; color: #1e293b;">Accept & Sign In</div>
                      </td>
                      <td width="3%"></td>
                      <td width="31%" align="center" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 6px;">
                        <div style="font-size: 11px; font-weight: 800; color: #4f46e5; margin-bottom: 2px;">STEP 2</div>
                        <div style="font-size: 12px; font-weight: 600; color: #1e293b;">Go to Benchmark</div>
                      </td>
                      <td width="3%"></td>
                      <td width="31%" align="center" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 6px;">
                        <div style="font-size: 11px; font-weight: 800; color: #4f46e5; margin-bottom: 2px;">STEP 3</div>
                        <div style="font-size: 12px; font-weight: 600; color: #1e293b;">▷ Run Benchmark</div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td style="padding-top: 14px;">
                  <div style="background-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; font-size: 12px; color: #475569; line-height: 1.5;">
                    💡 <strong>How to evaluate:</strong> In the <strong>Benchmark section</strong>, select your desired test depth (e.g. <code>Cases/Doc: 2 Cases</code>) and click <code>▷ Run Dynamic Benchmark</code> to compute real-time Faithfulness & Precision scores.
                  </div>
                </td>
              </tr>
            </table>

          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background-color: #f8fafc; padding: 20px 24px; border-top: 1px solid #f1f5f9; text-align: center; font-size: 12px; color: #94a3b8; line-height: 1.5;">
            <div>Sent exclusively to <strong>{to_email}</strong>.</div>
            <div style="margin-top: 4px;">© Noesis Agentic RAG Platform. All rights reserved.</div>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""

        logger.info(f"============================================================")
        logger.info(f" [DEV DEVELOPER INVITE EMAIL] Sent to: {to_email} | Role: {role_label} | URL: {accept_url}")
        logger.info(f"============================================================")

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
