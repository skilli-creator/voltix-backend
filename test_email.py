# backend/test_email.py

from services.email_service import EmailService
from config import Config

print("=" * 50)
print("📧 Email Configuration Test")
print("=" * 50)
print(f"EMAIL_HOST: {Config.EMAIL_HOST}")
print(f"EMAIL_PORT: {Config.EMAIL_PORT}")
print(f"EMAIL_USER: {Config.EMAIL_USER}")
print(f"EMAIL_PASS: {'*' * len(Config.EMAIL_PASS)}")
print("=" * 50)

# Test verification email
print("\n📤 Sending test verification email...")
result = EmailService.send_verification_email(
    to_email="tonnykyalo054@gmail.com",  # Your email for testing
    code="123456"
)

if result:
    print("\n✅ Email sent successfully! Check your inbox.")
else:
    print("\n❌ Email failed. Check the error above.")