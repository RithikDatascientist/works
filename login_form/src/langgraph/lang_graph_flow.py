# src/langgraph/lang_graph_flow.py
from typing import Dict
import os
import logging
from datetime import datetime

import requests
from langgraph.graph import StateGraph, END

# -------------------------
# Logging (creates logs on import)
# -------------------------
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
_ts = datetime.now().strftime("%Y%m%d")
_logger = logging.getLogger("langgraph")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    fh = logging.FileHandler(f"{LOG_DIR}/langgraph_auth_{_ts}.log")
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(fmt); ch.setFormatter(fmt)
    _logger.addHandler(fh); _logger.addHandler(ch)

API_BASE = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

def _post(path: str, payload: Dict) -> Dict:
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=20)
        if r.headers.get("content-type","").startswith("application/json"): return r.json()
        return {"status":"error","message":r.text}
    except Exception as e:
        _logger.error("HTTP POST %s failed: %s", path, e)
        return {"status":"error","message":str(e)}

def _get(path: str) -> Dict:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=15)
        if r.headers.get("content-type","").startswith("application/json"): return r.json()
        return {"status":"error","message":r.text}
    except Exception as e:
        _logger.error("HTTP GET %s failed: %s", path, e)
        return {"status":"error","message":str(e)}

# -------------------------
# NODES
# -------------------------

# Node 1 : sign_up
def sign_up(state: Dict) -> Dict:
    """
    New user registration via API.
    step1: Collect user details
    step2: Validate inputs (handled in API/UI)
    step3: Create new account and issue OTP
    """
    try:
        payload = {
            "name": state["full_name"],
            "email": state["email"],
            "phone": state["phone"],
            "password": state["password"],
            "plan_id": state.get("plan_id", "free"),
        }
        _logger.info("NODE-01: sign_up -> register %s", payload.get("email"))
        r = _post("/auth/register", payload)
        if r.get("status") == "success":
            return {"status": "registered", "flag": "yes", "user_id": r.get("user_id")}
        return {"status": "failed", "flag": "no", "error": r.get("message")}
    except Exception as e:
        _logger.error("NODE-01: sign_up failed %s", e)
        return {"status": "failed", "flag": "no"}

# Node 2 : user_registration
def user_registration(state: Dict) -> Dict:
    """
    Confirm user registration via OTP.
    step1: Send/collect verification token
    step2: Validate OTP
    step3: Mark user verified
    """
    if state.get("flag") != "yes":
        _logger.info("NODE-02: user_registration -> skipped (prev failure)")
        return {"registration_status": "skipped", "flag": "no"}
    try:
        payload = {"email": state["email"], "otp_code": state["otp_code"]}
        _logger.info("NODE-02: user_registration -> verify %s", payload.get("email"))
        r = _post("/auth/verify", payload)
        ok = r.get("status") == "success"
        return {"registration_status": "verified" if ok else "failed", "flag": "yes" if ok else "no"}
    except Exception as e:
        _logger.error("NODE-02: user_registration failed %s", e)
        return {"registration_status": "failed", "flag": "no"}

# Node 3 : sign_in
def sign_in(state: Dict) -> Dict:
    """
    Existing user login via API.
    step1: Collect credentials
    step2: Validate credentials
    step3: Log authentication status
    """
    try:
        payload = {"email_or_phone": state["email_or_phone"], "password": state["password"]}
        _logger.info("NODE-03: sign_in -> login %s", payload.get("email_or_phone"))
        r = _post("/auth/login", payload)
        if r.get("status") == "success":
            return {"login_status": "success", "flag": "yes", "user": r.get("user")}
        elif r.get("status") == "verification_required":
            return {"login_status": "verification_required", "flag": "no", "email": r.get("email")}
        return {"login_status": "failed", "flag": "no", "error": r.get("message")}
    except Exception as e:
        _logger.error("NODE-03: sign_in failed %s", e)
        return {"login_status": "failed", "flag": "no"}

# Node 4 : forgot_password
def forgot_password(state: Dict) -> Dict:
    """
    Password reset via API.
    step1: Collect email/phone
    step2: Send reset token
    step3: Confirm reset (separate page)
    """
    try:
        payload = {"email": state["email"], "phone": state["phone"]}
        _logger.info("NODE-04: forgot_password -> request %s", payload.get("email"))
        r = _post("/auth/forgot-password", payload)
        ok = r.get("status") == "success"
        return {"password_reset": "sent" if ok else "failed", "flag": "yes" if ok else "no"}
    except Exception as e:
        _logger.error("NODE-04: forgot_password failed %s", e)
        return {"password_reset": "failed", "flag": "no"}

# Node 5 : user_login_validation
def user_login_validation(state: Dict) -> Dict:
    """Validate login and session."""
    if state.get("login_status") == "success":
        _logger.info("NODE-05: user_login_validation -> session active")
        return {"session": "active", "flag": "yes"}
    _logger.info("NODE-05: user_login_validation -> inactive")
    return {"session": "inactive", "flag": "no"}

# Node 6 : subscription_validation
def subscription_validation(state: Dict) -> Dict:
    """
    Check subscription via API.
    step1: Fetch subscription
    step2: Determine status (active/none)
    """
    if state.get("flag") != "yes":
        _logger.info("NODE-06: subscription_validation -> skipped")
        return {"subscription": "unknown", "flag": "no"}
    try:
        uid = state.get("user",{}).get("id") or state.get("user_id")
        r = _get(f"/user/{uid}/subscription")
        sub = r.get("subscription", {}) if r else {}
        status = "active" if sub.get("plan_id") else "none"
        _logger.info("NODE-06: subscription status %s for %s", status, uid)
        return {"subscription": status, "flag": "yes", "sub_detail": sub, "user_id": uid}
    except Exception as e:
        _logger.error("NODE-06: subscription_validation failed %s", e)
        return {"subscription": "failed", "flag": "no"}

# Node 7 : subscription_plan
def subscription_plan(state: Dict) -> Dict:
    """
    Handle plan purchase/renewal (UI-driven).
    This node acknowledges routing to UI for upgrade; API call happens from UI.
    """
    if state.get("flag") != "yes":
        _logger.info("NODE-07: subscription_plan -> not eligible")
        return {"subscription_status": "not_subscribed", "flag": "no"}
    _logger.info("NODE-07: subscription_plan -> awaiting UI upgrade flow")
    return {"subscription_status": "pending", "flag": "yes"}

# Node 8 : subscribed
def subscribed(state: Dict) -> Dict:
    """Confirm subscription active and grant access."""
    if state.get("flag") != "yes":
        _logger.info("NODE-08: subscribed -> denied")
        return {"access": "denied", "flag": "no"}
    _logger.info("NODE-08: subscribed -> granted")
    return {"access": "granted", "flag": "yes"}

# Node 9 : user_selection
def user_selection(state: Dict) -> Dict:
    """Route to selected workflow."""
    if state.get("flag") != "yes":
        _logger.info("NODE-09: user_selection -> skipped")
        return {"selection": None, "flag": "no"}
    choice = state.get("selection")
    _logger.info("NODE-09: user_selection -> %s", choice)
    return {"selection": choice, "flag": "yes"}

# Node 10 : image_processing
def image_processing(state: Dict) -> Dict:
    """Record image feature usage via API."""
    if state.get("flag") != "yes":
        _logger.info("NODE-10: image_processing -> skipped")
        return {"task": "not_processed", "flag": "no"}
    try:
        uid = state.get("user_id") or state.get("user",{}).get("id")
        _logger.info("NODE-10: image_processing -> record for %s", uid)
        _post(f"/user/{uid}/use-feature", {"feature": "image"})
        return {"task": "image_done", "flag": "yes"}
    except Exception as e:
        _logger.error("NODE-10: image_processing failed %s", e)
        return {"task": "failed", "flag": "no"}

# Node 11 : report_processing
def report_processing(state: Dict) -> Dict:
    """Record report feature usage via API."""
    if state.get("flag") != "yes":
        _logger.info("NODE-11: report_processing -> skipped")
        return {"task": "not_processed", "flag": "no"}
    try:
        uid = state.get("user_id") or state.get("user",{}).get("id")
        _logger.info("NODE-11: report_processing -> record for %s", uid)
        _post(f"/user/{uid}/use-feature", {"feature": "report"})
        return {"task": "report_done", "flag": "yes"}
    except Exception as e:
        _logger.error("NODE-11: report_processing failed %s", e)
        return {"task": "failed", "flag": "no"}

# -------------------------
# GRAPH
# -------------------------
workflow = StateGraph(dict)

# Register nodes
workflow.add_node("sign_up", sign_up)                              # Node1
workflow.add_node("user_registration", user_registration)          # Node2
workflow.add_node("sign_in", sign_in)                              # Node3
workflow.add_node("forgot_password", forgot_password)              # Node4
workflow.add_node("user_login_validation", user_login_validation)  # Node5
workflow.add_node("subscription_validation", subscription_validation)  # Node6
workflow.add_node("subscription_plan", subscription_plan)          # Node7
workflow.add_node("subscribed", subscribed)                        # Node8
workflow.add_node("user_selection", user_selection)                # Node9
workflow.add_node("image_processing", image_processing)            # Node10
workflow.add_node("report_processing", report_processing)          # Node11

# Edges
workflow.add_edge("sign_up", "user_registration")
workflow.add_edge("user_registration", "user_login_validation")
workflow.add_edge("sign_in", "user_login_validation")
workflow.add_edge("forgot_password", "user_login_validation")
workflow.add_edge("user_login_validation", "subscription_validation")

# Conditional branch based on subscription status
def _route_sub(x: Dict) -> str:
    status = x.get("subscription", "none")
    return status

workflow.add_conditional_edges(
    "subscription_validation",
    _route_sub,
    {
        "active": "subscribed",
        "expired": "subscription_plan",
        "none": "subscription_plan",
        "failed": "subscription_plan",
        "unknown": "subscription_plan",
    },
)

workflow.add_edge("subscription_plan", "subscribed")
workflow.add_edge("subscribed", "user_selection")

# Branch selection
def _route_sel(x: Dict) -> str:
    sel = (x or {}).get("selection")
    if sel == "image": return "image"
    if sel == "report": return "report"
    return "image"  # default

workflow.add_conditional_edges(
    "user_selection",
    _route_sel,
    {
        "image": "image_processing",
        "report": "report_processing",
    },
)

# End
workflow.add_edge("image_processing", END)
workflow.add_edge("report_processing", END)

graph = workflow.compile()
