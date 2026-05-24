import logging
import os

logger = logging.getLogger("app.email")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def send_email(to: str, subject: str, body: str) -> None:
    # TODO: integrate SMTP (mailpit/sendgrid/ses). For now log to stdout so dev can see.
    logger.info("EMAIL to=%s subject=%r", to, subject)
    print(f"\n--- EMAIL ---\nto: {to}\nsubject: {subject}\n{body}\n-------------\n", flush=True)


def send_email_verify(to: str, token: str) -> None:
    link = f"{FRONTEND_URL}/verify-email?token={token}"
    send_email(
        to=to,
        subject="Xác minh email TRCF LMS",
        body=(
            f"Chào bạn,\n\nNhấn vào liên kết sau để xác minh email:\n{link}\n\n"
            "Liên kết có hiệu lực trong 24 giờ.\nBỏ qua nếu bạn không tạo tài khoản."
        ),
    )


def send_password_reset(to: str, token: str) -> None:
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    send_email(
        to=to,
        subject="Đặt lại mật khẩu TRCF LMS",
        body=(
            f"Chào bạn,\n\nNhấn vào liên kết sau để đặt lại mật khẩu:\n{link}\n\n"
            "Liên kết có hiệu lực trong 1 giờ.\nBỏ qua nếu bạn không yêu cầu."
        ),
    )
