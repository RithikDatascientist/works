# src/auth/service.py
from typing import Dict, Any
from config.settings import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, init_logger
from src.db.users_db import (
    init_users_db, create_user, get_user_by_identifier, verify_password, set_verified,
    create_verify_token, consume_verify_token, create_reset_token, consume_reset_token, set_new_password
)
from src.db.subscriptions_db import (
    init_subs_db, get_subscription, set_subscription, list_plans, record_login, record_activity, get_usage
)
import smtplib
from email.message import EmailMessage

log = init_logger("auth_service")

def bootstrap_databases():
    init_users_db(); init_subs_db()
    log.info("NODE-00: DB_INIT complete")

def _send_email(to_email: str, subject: str, body: str):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        log.info("NODE-02: user_registration -> SMTP not configured; printing email\n%s", body); return
    msg = EmailMessage()
    msg["From"] = SMTP_USER; msg["To"] = to_email; msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    log.info("NODE-02: user_registration -> OTP email sent to %s", to_email)

# NODE-01: sign_up
def register_user(full_name: str, email: str, phone: str, password: str, plan_id: str) -> Dict[str, Any]:
    u = create_user(full_name, email, phone, password)
    otp = create_verify_token(email)
    _send_email(email, "Verify your account", f"Your verification token is: {otp['token']}")
    # create default subscription record
    set_subscription(u["id"], plan_id or "free")
    return {"status": "success", "message": "Registration created, please verify with OTP.", "user_id": u["id"]}

# NODE-02: user_registration
def verify_account(email: str, token: str) -> Dict[str, Any]:
    if not consume_verify_token(email, token):
        return {"status": "error", "message": "Invalid or expired verification token."}
    set_verified(email)
    return {"status": "success", "message": "Account verified. Please login."}

# NODE-03/05: sign_in + user_login_validation
def login_user(identifier: str, password: str) -> Dict[str, Any]:
    u = get_user_by_identifier(identifier)
    if not u: return {"status": "error", "message": "User not found."}
    if not verify_password(password, u["password_salt"], u["password_hash"]):
        return {"status": "error", "message": "Invalid credentials."}
    if not u.get("verified"):
        return {"status": "verification_required", "message": "Verification required. Check email for OTP.", "email": u.get("email")}
    # usage gating
    sub = get_subscription(str(u["_id"]))
    usage = get_usage(str(u["_id"]))
    if usage.get("current_usage", 0) >= sub.get("usage_limit", 0):
        return {"status": "error", "message": "Daily login limit reached."}
    record_login(str(u["_id"]))
    public = {
        "id": str(u["_id"]), "name": u.get("full_name"), "email": u.get("email"),
        "phone": u.get("phone")
    }
    return {"status": "success", "message": "Login successful.", "user": public}

# NODE-04: forgot_password
def forgot_password(email: str, phone: str) -> Dict[str, Any]:
    # simple lookup check
    u = get_user_by_identifier(email) or get_user_by_identifier(phone)
    if not u: return {"status": "error", "message": "Account not found."}
    if email != u.get("email") or phone != u.get("phone"):
        return {"status": "error", "message": "Email/phone mismatch."}
    tok = create_reset_token(email)
    _send_email(email, "Reset password", f"Your reset token is: {tok['token']}")
    return {"status": "success", "message": "Reset token sent."}

def reset_password(email: str, reset_token: str, new_password: str) -> Dict[str, Any]:
    if not consume_reset_token(email, reset_token):
        return {"status": "error", "message": "Invalid or expired reset token."}
    set_new_password(email, new_password)
    return {"status": "success", "message": "Password reset successful."}

# NODE-06/07/08: subscription
def get_user_subscription(user_id: str) -> Dict[str, Any]:
    return {"subscription": get_subscription(user_id)}

def upgrade_plan(user_id: str, new_plan_id: str) -> Dict[str, Any]:
    sub = set_subscription(user_id, new_plan_id)
    return {"status": "success", "message": "Plan upgraded.", "subscription": sub}

def list_all_plans() -> Dict[str, Any]:
    return {"plans": list_plans()}

# NODE-09/10/11: feature usage
def use_feature(user_id: str, feature: str) -> Dict[str, Any]:
    # count against daily usage the same as demo UI
    record_activity(user_id, feature)
    return {"status": "success", "message": "Feature recorded."}

def get_user_usage(user_id: str) -> Dict[str, Any]:
    return {"usage": get_usage(user_id)}
