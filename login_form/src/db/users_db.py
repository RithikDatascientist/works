# src/db/users_db.py
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import hashlib, secrets
from pymongo import MongoClient, ASCENDING
from bson import ObjectId
from config.settings import USERS_MONGODB_URI, USERS_DB_NAME, init_logger

log = init_logger("users_db")
_client = MongoClient(USERS_MONGODB_URI, tz_aware=True, tzinfo=timezone.utc)
db = _client[USERS_DB_NAME]

def init_users_db():
    db.users.create_index([("email", ASCENDING)], unique=True, sparse=True)
    db.users.create_index([("phone", ASCENDING)], unique=True, sparse=True)
    db.verify_tokens.create_index([("email", ASCENDING), ("token", ASCENDING)], unique=True)
    db.verify_tokens.create_index([("expires_at", ASCENDING)])
    db.password_resets.create_index([("email", ASCENDING), ("token", ASCENDING)], unique=True)
    db.password_resets.create_index([("expires_at", ASCENDING)])
    log.info("NODE-00: DB_INIT users db ready")

def _salted_hash(pw: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()
    return salt, digest

def create_user(full_name: str, email: str, phone: str, password: str) -> Dict[str, Any]:
    salt, ph = _salted_hash(password)
    doc = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "password_salt": salt,
        "password_hash": ph,
        "verified": False,
        "status": "active",
        "created_at": datetime.now(timezone.utc)
    }
    res = db.users.insert_one(doc)
    log.info("NODE-01: sign_up -> user created %s", str(res.inserted_id))
    return {"id": str(res.inserted_id), "email": email, "full_name": full_name, "phone": phone, "verified": False}

def get_user_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
    return db.users.find_one({"$or": [{"email": identifier}, {"phone": identifier}]})

def get_user_by_id(uid: str) -> Optional[Dict[str, Any]]:
    try:
        return db.users.find_one({"_id": ObjectId(uid)})
    except Exception:
        return None

def verify_password(pw: str, salt: str, digest: str) -> bool:
    _, check = _salted_hash(pw, salt)
    return check == digest

def set_verified(email: str) -> bool:
    r = db.users.update_one({"email": email}, {"$set": {"verified": True}})
    log.info("NODE-02: user_registration -> set verified for %s matched=%s", email, r.matched_count)
    return r.matched_count == 1

def create_verify_token(email: str, ttl_min: int = 15) -> Dict[str, Any]:
    token = secrets.token_urlsafe(16)
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_min)
    db.verify_tokens.delete_many({"email": email})
    db.verify_tokens.insert_one({"email": email, "token": token, "expires_at": expires})
    log.info("NODE-02: user_registration -> issued verify token for %s", email)
    return {"email": email, "token": token, "expires_at": expires.isoformat()}

def consume_verify_token(email: str, token: str) -> bool:
    rec = db.verify_tokens.find_one({"email": email, "token": token})
    if not rec:
        return False

    def as_utc(dt):
        return dt if getattr(dt, "tzinfo", None) else dt.replace(tzinfo=timezone.utc)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    now_utc = datetime.now(timezone.utc)

    if expires_at < now_utc:
        db.verify_tokens.delete_many({"email": email})
        return False
    db.verify_tokens.delete_many({"email": email})
    return True

def create_reset_token(email: str, ttl_min: int = 15) -> Dict[str, Any]:
    token = secrets.token_urlsafe(16)
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_min)
    db.password_resets.delete_many({"email": email})
    db.password_resets.insert_one({"email": email, "token": token, "expires_at": expires})
    log.info("NODE-04: forgot_password -> issued reset token for %s", email)
    return {"email": email, "token": token, "expires_at": expires.isoformat()}

def consume_reset_token(email: str, token: str) -> bool:
    rec = db.password_resets.find_one({"email": email, "token": token})
    if not rec: return False
    if rec["expires_at"] < datetime.now(timezone.utc):
        db.password_resets.delete_many({"email": email})
        return False
    db.password_resets.delete_many({"email": email})
    return True

def set_new_password(email: str, new_password: str) -> bool:
    salt, ph = _salted_hash(new_password)
    r = db.users.update_one({"email": email}, {"$set": {"password_salt": salt, "password_hash": ph}})
    log.info("NODE-04: forgot_password -> password updated for %s matched=%s", email, r.matched_count)
    return r.matched_count == 1
