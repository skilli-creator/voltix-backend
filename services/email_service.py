# backend/services/email_service.py

import resend
from config import Config

class EmailService:
    
    @staticmethod
    def init_resend():
        """Initialize Resend with API key"""
        try:
            resend.api_key = Config.RESEND_API_KEY
            print("📧 Resend initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Resend initialization failed: {e}")
            return False
    
    @staticmethod
    def send_verification_email(to_email, code):
        """Send email verification code using Resend"""
        try:
            print("\n" + "="*50)
            print("📧 Sending verification email via Resend")
            print("="*50)
            print(f"📝 To: {to_email}")
            print(f"🔑 Code: {code}")
            print("="*50)
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Voltix | Verify Your Account</title>
                <style>
                    body {{ font-family: Arial, sans-serif; background: #0a0f1e; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: #10172e; border-radius: 20px; padding: 40px; border: 1px solid #22c55e20; }}
                    .code {{ font-size: 40px; letter-spacing: 8px; background: #1e293b; padding: 20px; border-radius: 12px; text-align: center; color: #22c55e; }}
                    h2 {{ color: #22c55e; }}
                    p {{ color: #94a3b8; }}
                    .footer {{ margin-top: 30px; color: #4b5563; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>🔷 Voltix Traders</h2>
                    <h3>Verify Your Email</h3>
                    <p>Welcome to Voltix! Please use the code below to verify your account:</p>
                    <div class="code"><strong>{code}</strong></div>
                    <p>This code expires in <strong>10 minutes</strong>.</p>
                    <div class="footer">© 2026 Voltix — AI Trading Platform</div>
                </div>
            </body>
            </html>
            """
            
            response = resend.Emails.send({
                "from": Config.RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": "Verify Your Voltix Account",
                "html": html
            })
            
            print(f"✅ Verification email sent successfully")
            print(f"📬 Response ID: {response}")
            return True
            
        except Exception as e:
            print(f"❌ Verification email error: {e}")
            return False
    
    @staticmethod
    def send_password_reset_email(to_email, code):
        """Send password reset code using Resend"""
        try:
            print("\n" + "="*50)
            print("📧 Sending password reset email via Resend")
            print("="*50)
            print(f"📝 To: {to_email}")
            print(f"🔑 Code: {code}")
            print("="*50)
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Voltix | Password Reset</title>
                <style>
                    body {{ font-family: Arial, sans-serif; background: #0a0f1e; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: #10172e; border-radius: 20px; padding: 40px; border: 1px solid #f59e0b20; }}
                    .code {{ font-size: 40px; letter-spacing: 8px; background: #1e293b; padding: 20px; border-radius: 12px; text-align: center; color: #f59e0b; }}
                    h2 {{ color: #f59e0b; }}
                    p {{ color: #94a3b8; }}
                    .warning {{ color: #ef4444; font-size: 12px; }}
                    .footer {{ margin-top: 30px; color: #4b5563; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>🔷 Voltix Traders</h2>
                    <h3>Password Reset Request</h3>
                    <p>You requested to reset your password. Use the code below to proceed:</p>
                    <div class="code"><strong>{code}</strong></div>
                    <p>This code expires in <strong>10 minutes</strong>.</p>
                    <p class="warning">⚠️ If you didn't request this, ignore this email.</p>
                    <div class="footer">© 2026 Voltix — AI Trading Platform</div>
                </div>
            </body>
            </html>
            """
            
            response = resend.Emails.send({
                "from": Config.RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": "🔑 Voltix - Password Reset Code",
                "html": html
            })
            
            print(f"✅ Password reset email sent successfully")
            print(f"📬 Response ID: {response}")
            return True
            
        except Exception as e:
            print(f"❌ Password reset email error: {e}")
            return False
    
    @staticmethod
    def send_admin_notification(subject, body):
        """Send admin notification using Resend"""
        try:
            print("\n" + "="*50)
            print("📧 Sending admin notification via Resend")
            print("="*50)
            
            html = f"""
            <div style="font-family: Arial, sans-serif; background: #0a0f1e; padding: 20px;">
                <h2>⚡ Voltix Admin Notification</h2>
                <hr>
                <pre style="background: #1e293b; padding: 15px; border-radius: 8px; color: #f1f5f9;">{body}</pre>
                <hr>
                <p style="color: #666; font-size: 12px;">Sent at: {__import__('datetime').datetime.now()}</p>
            </div>
            """
            
            response = resend.Emails.send({
                "from": Config.RESEND_FROM_EMAIL,
                "to": [Config.ADMIN_EMAIL],
                "subject": f"[Voltix Admin] {subject}",
                "html": html
            })
            
            print(f"✅ Admin notification sent successfully")
            print(f"📬 Response ID: {response}")
            return True
            
        except Exception as e:
            print(f"❌ Admin notification error: {e}")
            return False