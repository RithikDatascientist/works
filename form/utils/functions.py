# utils/functions.py
from __future__ import annotations

import os
import re
import smtplib
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from pymongo import MongoClient, ASCENDING
from bson import ObjectId

# -------------------------
# Settings (hardcoded for simplicity; adjust as needed)
# -------------------------
FASTAPI_HOST = "0.0.0.0"
FASTAPI_PORT = 8000

USERS_MONGODB_URI = os.getenv("USERS_MONGODB_URI", "mongodb://localhost:27017")
SUBS_MONGODB_URI = os.getenv("SUBS_MONGODB_URI", "mongodb://localhost:27017")
USERS_DB_NAME = "users_db"
SUBS_DB_NAME = "subs_db"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "rithik2k2003@gmail.com"
SMTP_PASS = "kdnfzjvqckcdpjxe"

# -------------------------
# Logging (single file, single configuration)
# -------------------------
def get_logger() -> logging.Logger:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d")
    logfile = log_dir / f"app_{ts}.log"

    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    # prevent duplicate handlers on reloads
    if not logger.handlers:
        fh = logging.FileHandler(logfile, encoding="utf-8")
        ch = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger

log = get_logger()

# -------------------------
# DB clients (tz aware)
# -------------------------
_users_client = MongoClient(USERS_MONGODB_URI, tz_aware=True, tzinfo=timezone.utc)
_subs_client = MongoClient(SUBS_MONGODB_URI, tz_aware=True, tzinfo=timezone.utc)
users_db = _users_client[USERS_DB_NAME]
subs_db = _subs_client[SUBS_DB_NAME]

# -------------------------
# Validators 
# -------------------------
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[0-9+\-() ]{6,20}$")

def validate_name(v: str) -> Tuple[bool, str]:
    if not isinstance(v, str) or not (2 <= len(v.strip()) <= 100):
        return False, "Name must be 2-100 characters."
    return True, ""

def validate_email(v: str) -> Tuple[bool, str]:
    if not isinstance(v, str) or not EMAIL_RE.match(v.strip()):
        return False, "Invalid email format."
    return True, ""

def validate_phone(v: str) -> Tuple[bool, str]:
    if not isinstance(v, str) or not PHONE_RE.match(v.strip()):
        return False, "Invalid phone format."
    return True, ""

def validate_password(v: str) -> Tuple[bool, str]:
    if not isinstance(v, str) or len(v) < 8:
        return False, "Password must be at least 8 characters."
    return True, ""

def validate_plan(v: str) -> Tuple[bool, str]:
    if not isinstance(v, str) or not (3 <= len(v) <= 20):
        return False, "Plan id must be 3-20 characters."
    return True, ""

# -------------------------
# Email
# -------------------------
def send_email(to_addr: str, subject: str, body: str) -> None:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and SMTP_PORT):
        log.info("SMTP not configured; printing email\nTo: %s\nSubject: %s\n%s", to_addr, subject, body)
        return
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = SMTP_USER
        msg["To"] = to_addr
        msg["Subject"] = subject

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        log.info("Email sent to %s subject='%s'", to_addr, subject)
    except Exception as e:
        log.error("Failed to send email to %s: %s", to_addr, e)
        # fall back to printing for visibility
        print(f"[EMAIL FALLBACK]\nTo: {to_addr}\nSubject: {subject}\n{body}")

# -------------------------
# Security helpers
# -------------------------
def _salted_hash(pw: str, salt: Optional[str] = None) -> Tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    h = hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()
    return h, salt

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

# -------------------------
# Bootstrapping
# -------------------------
def bootstrap_databases() -> None:
    # Users
    users_db.users.create_index([("email", ASCENDING)], unique=True, sparse=True)
    users_db.users.create_index([("phone", ASCENDING)], unique=True, sparse=True)
    users_db.verify_tokens.create_index([("email", ASCENDING), ("token", ASCENDING)], unique=True)
    users_db.verify_tokens.create_index([("expires_at", ASCENDING)])
    users_db.password_resets.create_index([("email", ASCENDING), ("token", ASCENDING)], unique=True)
    users_db.password_resets.create_index([("expires_at", ASCENDING)])
    log.info("NODE-00: DB_INIT users db ready")

    # Subscriptions
    subs_db.plans.create_index([("plan_id", ASCENDING)], unique=True)
    subs_db.subscriptions.create_index([("user_id", ASCENDING)], unique=True)
    subs_db.usage.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
    if subs_db.plans.count_documents({}) == 0:
        subs_db.plans.insert_many([
            {"plan_id": "free",  "name": "Free",  "price": 0,  "usage_limit": 3,   "features": ["login","image_basic"]},
            {"plan_id": "basic", "name": "Basic", "price": 9,  "usage_limit": 10,  "features": ["login","image_basic","report_basic"]},
            {"plan_id": "pro",   "name": "Pro",   "price": 29, "usage_limit": 100, "features": ["login","image_advanced","report_basic"]},
        ])
    log.info("NODE-06: subscription_validation -> subs db ready with seed plans")

# -------------------------
# Users / Auth
# -------------------------
def create_user(full_name: str, email: str, phone: str, password: str) -> Dict[str, Any]:
    ok, msg = validate_name(full_name);  assert ok, msg
    ok, msg = validate_email(email);     assert ok, msg
    ok, msg = validate_phone(phone);     assert ok, msg
    ok, msg = validate_password(password); assert ok, msg

    pw_hash, salt = _salted_hash(password)
    doc = {
        "name": full_name.strip(),
        "email": email.strip().lower(),
        "phone": phone.strip(),
        "password_hash": pw_hash,
        "salt": salt,
        "verified": False,
        "created_at": datetime.now(timezone.utc),
    }
    res = users_db.users.insert_one(doc)
    user_id = str(res.inserted_id)
    log.info("NODE-01: sign_up -> user created %s", user_id)

    token = secrets.token_urlsafe(24)
    users_db.verify_tokens.insert_one({
        "email": doc["email"],
        "token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
    })
    log.info("NODE-02: user_registration -> issued verify token for %s", doc["email"])
    send_email(
        doc["email"],
        "Verify your account",
        f"Hello {doc['name']},\n\nYour verification code is:\n\n{token}\n\nThis code expires in 15 minutes.",
    )
    return {"id": user_id, "name": doc["name"], "email": doc["email"], "phone": doc["phone"]}

def consume_verify_token(email: str, token: str) -> bool:
    rec = users_db.verify_tokens.find_one({"email": email.strip().lower(), "token": token})
    if not rec:
        return False
    exp = rec.get("expires_at")
    exp = exp if getattr(exp, "tzinfo", None) else exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        users_db.verify_tokens.delete_many({"email": email})
        return False
    users_db.verify_tokens.delete_many({"email": email})
    return True

def verify_account(email: str, otp_code: str) -> Dict[str, Any]:
    if not consume_verify_token(email, otp_code):
        return {"status": "error", "message": "Invalid or expired token."}
    users_db.users.update_one({"email": email.lower()}, {"$set": {"verified": True}})
    log.info("NODE-02: user_registration -> verified %s", email)
    return {"status": "success", "message": "Account verified."}

def login_user(email_or_phone: str, password: str) -> Dict[str, Any]:
    q = {"email": email_or_phone.lower()} if "@" in email_or_phone else {"phone": email_or_phone}
    user = users_db.users.find_one(q)
    if not user:
        return {"status": "error", "message": "User not found."}
    h, _ = _salted_hash(password, user.get("salt"))
    if h != user.get("password_hash"):
        return {"status": "error", "message": "Invalid credentials."}
    if not user.get("verified"):
        return {"status": "verification_required", "email": user.get("email"), "message": "Please verify your account."}
    record_login(str(user["_id"]))
    return {
        "status": "success",
        "message": "Login successful.",
        "user": {"id": str(user["_id"]), "name": user["name"], "email": user["email"]},
    }

def forgot_password(email: str, phone: str) -> Dict[str, Any]:
    ok, _ = validate_email(email); ok2, _ = validate_phone(phone)
    if not (ok and ok2):
        return {"status": "error", "message": "Invalid email/phone."}
    user = users_db.users.find_one({"email": email.lower(), "phone": phone})
    if not user:
        return {"status": "error", "message": "No matching account."}
    token = secrets.token_urlsafe(24)
    users_db.password_resets.update_one(
        {"email": email.lower()},
        {"$set": {"email": email.lower(), "token": token, "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30)}},
        upsert=True,
    )
    send_email(email, "Password reset token", f"Your reset token is:\n\n{token}")
    log.info("NODE-04: forgot_password -> issued reset token for %s", email)
    return {"status": "success", "message": "Reset token sent."}

def reset_password(email: str, reset_token: str, new_password: str) -> Dict[str, Any]:
    ok, msg = validate_password(new_password)
    if not ok:
        return {"status": "error", "message": msg}
    rec = users_db.password_resets.find_one({"email": email.lower(), "token": reset_token})
    if not rec:
        return {"status": "error", "message": "Invalid token."}
    exp = rec["expires_at"]
    exp = exp if getattr(exp, "tzinfo", None) else exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        users_db.password_resets.delete_one({"_id": rec["_id"]})
        return {"status": "error", "message": "Token expired."}
    pw_hash, salt = _salted_hash(new_password)
    users_db.users.update_one({"email": email.lower()}, {"$set": {"password_hash": pw_hash, "salt": salt}})
    users_db.password_resets.delete_many({"email": email.lower()})
    log.info("NODE-04: reset_password for %s", email)
    return {"status": "success", "message": "Password reset successful."}

def register_user(full_name: str, email: str, phone: str, password: str, plan_id: str) -> Dict[str, Any]:
    try:
        user = create_user(full_name, email, phone, password)
        set_subscription(user["id"], plan_id or "free")
        return {"status": "success", "message": "Registration created, verify OTP.", "user_id": user["id"]}
    except Exception as e:
        # surface duplicate key and validation errors cleanly
        msg = str(e)
        if "E11000" in msg or "duplicate key" in msg:
            return {"status": "error", "message": "Email or phone already registered."}
        return {"status": "error", "message": msg}

# -------------------------
# Plans / Usage
# -------------------------
def list_all_plans() -> Dict[str, Any]:
    plans = list(subs_db.plans.find({}, {"_id": 0}).sort("price", ASCENDING))
    return {"plans": plans}

def get_plan(pid: str) -> Optional[Dict[str, Any]]:
    return subs_db.plans.find_one({"plan_id": pid}, {"_id": 0})

def get_user_subscription(user_id: str) -> Dict[str, Any]:
    sub = subs_db.subscriptions.find_one({"user_id": user_id})
    if not sub:
        plan = get_plan("free") or {"plan_id": "free", "name": "Free", "price": 0, "usage_limit": 3, "features": ["login","image_basic"]}
        return {"subscription": {"plan_id": plan["plan_id"], "plan_name": plan["name"], "price": plan["price"], "usage_limit": plan["usage_limit"], "features": plan.get("features",[]) }}
    plan = get_plan(sub.get("plan_id","free")) or get_plan("free")
    return {"subscription": {"plan_id": plan["plan_id"], "plan_name": plan["name"], "price": plan["price"], "usage_limit": plan["usage_limit"], "features": plan.get("features",[])}}

def set_subscription(user_id: str, plan_id: str) -> Dict[str, Any]:
    plan = get_plan(plan_id)
    if not plan:
        raise ValueError("Invalid plan_id")
    subs_db.subscriptions.update_one({"user_id": user_id}, {"$set": {"user_id": user_id, "plan_id": plan_id}}, upsert=True)
    log.info("NODE-07: subscription_plan -> set plan %s for user %s", plan_id, user_id)
    return get_user_subscription(user_id)

def record_login(user_id: str) -> None:
    today = _today()
    subs_db.usage.update_one({"user_id": user_id, "date": today}, {"$inc": {"current_usage": 1}, "$setOnInsert": {"recent_activities": []}}, upsert=True)
    log.info("NODE-05: user_login_validation -> login counted for %s", user_id)

def record_activity(user_id: str, feature: str) -> None:
    today = _today()
    now = datetime.now(timezone.utc).isoformat()
    doc = subs_db.usage.find_one({"user_id": user_id, "date": today})
    acts = (doc or {}).get("recent_activities", [])
    acts.insert(0, {"feature": feature, "timestamp": now})
    acts = acts[:100]
    subs_db.usage.update_one(
        {"user_id": user_id, "date": today},
        {"$set": {"recent_activities": acts}},
        upsert=True,
    )
    log.info("NODE-10/11: feature used '%s' by %s", feature, user_id)

def get_user_usage(user_id: str) -> Dict[str, Any]:
    today = _today()
    doc = subs_db.usage.find_one({"user_id": user_id, "date": today}, {"_id": 0})
    if not doc:
        return {"usage": {"current_usage": 0, "period": "Today", "recent_activities": []}}
    return {"usage": {"current_usage": doc.get("current_usage", 0), "period": "Today", "recent_activities": doc.get("recent_activities", [])}}

def upgrade_plan(user_id: str, new_plan_id: str) -> Dict[str, Any]:
    resp = set_subscription(user_id, new_plan_id)
    plan_name = resp["subscription"]["plan_name"]
    # notify user
    user = users_db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        send_email(user["email"], "Plan upgraded", f"Your plan is now {plan_name}.")
    return {"status": "success", "message": f"Upgraded to {plan_name}."}

def use_feature(user_id: str, feature: str) -> Dict[str, Any]:
    record_activity(user_id, feature)
    return {"status": "success", "message": f"Feature '{feature}' recorded."}
