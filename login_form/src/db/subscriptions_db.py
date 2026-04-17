# src/db/subscriptions_db.py
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from config.settings import SUBS_MONGODB_URI, SUBS_DB_NAME, init_logger

log = init_logger("subs_db")
_client = MongoClient(SUBS_MONGODB_URI)
db = _client[SUBS_DB_NAME]

def init_subs_db():
    db.plans.create_index([("plan_id", ASCENDING)], unique=True)
    db.subscriptions.create_index([("user_id", ASCENDING)], unique=True)
    db.usage.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
    if db.plans.count_documents({}) == 0:
        db.plans.insert_many([
            {"plan_id": "free", "name": "Free", "price": 0, "usage_limit": 3, "features": ["login","image_basic"]},
            {"plan_id": "basic", "name": "Basic", "price": 9, "usage_limit": 10, "features": ["login","image_basic","report_basic"]},
            {"plan_id": "pro", "name": "Pro", "price": 29, "usage_limit": 100, "features": ["login","image_advanced","report_basic"]},
        ])
    log.info("NODE-06: subscription_validation -> subs db ready with seed plans")

def get_plan(pid: str) -> Optional[Dict[str, Any]]:
    return db.plans.find_one({"plan_id": pid}, {"_id": 0})

def list_plans() -> List[Dict[str, Any]]:
    return list(db.plans.find({}, {"_id": 0}).sort("price", ASCENDING))

def get_subscription(user_id: str) -> Dict[str, Any]:
    sub = db.subscriptions.find_one({"user_id": user_id}) or {}
    pid = sub.get("plan_id", "free")
    plan = get_plan(pid)
    if not plan:
        # Fallback to free if plan missing or not seeded yet
        plan = get_plan("free") or {"plan_id": "free", "name": "Free", "price": 0, "usage_limit": 3, "features": ["login","image_basic"]}
        # Optionally heal the record to free
        db.subscriptions.update_one({"user_id": user_id}, {"$set": {"user_id": user_id, "plan_id": "free"}}, upsert=True)
    return {
        "plan_id": plan.get("plan_id", "free"),
        "plan_name": plan.get("name", "Free"),
        "price": plan.get("price", 0),
        "usage_limit": plan.get("usage_limit", 3),
        "features": plan.get("features", ["login","image_basic"]),
    }

def set_subscription(user_id: str, plan_id: str) -> Dict[str, Any]:
    plan = get_plan(plan_id)
    if not plan: raise ValueError("Invalid plan_id")
    db.subscriptions.update_one({"user_id": user_id}, {"$set": {"user_id": user_id, "plan_id": plan_id}}, upsert=True)
    log.info("NODE-07: subscription_plan -> set plan %s for user %s", plan_id, user_id)
    return get_subscription(user_id)

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def record_login(user_id: str):
    today = _today()
    db.usage.update_one({"user_id": user_id, "date": today}, {"$inc": {"current_usage": 1}, "$setOnInsert": {"recent_activities": []}}, upsert=True)
    log.info("NODE-05: user_login_validation -> login counted for %s", user_id)

def record_activity(user_id: str, feature: str):
    today = _today()
    now = datetime.now(timezone.utc).isoformat()
    doc = db.usage.find_one({"user_id": user_id, "date": today})
    acts = (doc or {}).get("recent_activities", [])
    acts.insert(0, {"feature": feature, "timestamp": now})
    acts = acts[:100]
    db.usage.update_one({"user_id": user_id, "date": today}, {"$set": {"recent_activities": acts}, "$inc": {"current_usage": 1}}, upsert=True)
    log.info("NODE-10/11: feature used '%s' by %s", feature, user_id)

def get_usage(user_id: str) -> Dict[str, Any]:
    today = _today()
    doc = db.usage.find_one({"user_id": user_id, "date": today}, {"_id": 0})
    if not doc: return {"current_usage": 0, "period": "Today", "recent_activities": []}
    return {"current_usage": doc.get("current_usage", 0), "period": "Today", "recent_activities": doc.get("recent_activities", [])}
