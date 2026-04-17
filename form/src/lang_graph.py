from __future__ import annotations

from typing import Dict
from langgraph.graph import StateGraph, END

from utils.functions import (
    log,
    register_user,
    verify_account,
    login_user,
    forgot_password as svc_forgot_password,
    get_user_subscription,
    upgrade_plan as svc_upgrade_plan,
    use_feature,
)

def logfile(msg: str) -> None:
    """
    step1: Centralize node logging via app logger.
    step2: Keep messages compact and traceable.
    step3: Provide uniform tags for grep-friendly logs.
    """
    log.info(msg)

# -------------------- Nodes (with step docstrings) --------------------

def start_router(state: Dict) -> Dict:
    """
    Node: start_router — Selects the first real node.
    step1: Read state['start_at'] indicating where to begin (default 'sign_in').
    step2: Normalize value to a known node name; keep in state for routing.
    step3: Return a pass-through dict; routing is handled by conditional edges.
    """
    start_at = (state.get("start_at") or "sign_in").strip().lower()
    state["start_at"] = start_at
    logfile(f"START_ROUTER: start_at={start_at}")
    return {"flag": "yes", **state}

def sign_up(state: Dict) -> Dict:
    """
    Node: sign_up — New user registration via MCP.
    step1: Collect name/email/phone/password/plan_id from UI.
    step2: Create user, hash password, emit OTP for verification.
    step3: Return status and user_id for the next node.
    """
    try:
        resp = register_user(
            state["full_name"], state["email"], state["phone"], state["password"], state.get("plan_id", "free")
        )
        ok = resp.get("status") == "success"
        logfile("SIGN_UP: ok" if ok else "SIGN_UP: failed")
        return {"status": "registered" if ok else "failed", "flag": "yes" if ok else "no", "user_id": resp.get("user_id")}
    except Exception as e:
        logfile(f"SIGN_UP: {e}")
        return {"status": "failed", "flag": "no"}

def user_registration(state: Dict) -> Dict:
    """
    Node: user_registration — Verify OTP.
    step1: Accept email + otp_code.
    step2: Consume token; mark verified when valid.
    step3: Return verification status.
    """
    if state.get("flag") != "yes":
        logfile("USER_REGISTRATION: skipped")
        return {"registration_status": "skipped", "flag": "no"}
    try:
        resp = verify_account(state["email"], state["otp_code"])
        ok = resp.get("status") == "success"
        logfile("USER_REGISTRATION: ok" if ok else "USER_REGISTRATION: failed")
        return {"registration_status": "verified" if ok else "failed", "flag": "yes" if ok else "no"}
    except Exception as e:
        logfile(f"USER_REGISTRATION: {e}")
        return {"registration_status": "failed", "flag": "no"}

def sign_in(state: Dict) -> Dict:
    """
    Node: sign_in — Authenticate user.
    step1: Accept email_or_phone + password.
    step2: Validate creds; ensure verified; record login.
    step3: Return login_status, user, and optional email (for verify path).
    """
    try:
        resp = login_user(state["email_or_phone"], state["password"])
        ok = resp.get("status") == "success"
        user = resp.get("user") or {}
        uid = user.get("id") or user.get("_id") or user.get("user_id")
        logfile("SIGN_IN: ok" if ok else f"SIGN_IN: {resp.get('message')}")
        return {
            "login_status": resp.get("status"),
            "flag": "yes" if ok else "no",
            "user": resp.get("user"),
            "user_id": uid,  
            "email": resp.get("email"),
        }
    except Exception as e:
        logfile(f"SIGN_IN: {e}")
        return {"login_status": "failed", "flag": "no"}

def forgot_password(state: Dict) -> Dict:
    """
    Node: forgot_password — Issue reset token.
    step1: Accept email + phone for ownership check.
    step2: Create/overwrite reset token and email it.
    step3: Return sent/failed.
    """
    try:
        resp = svc_forgot_password(state["email"], state["phone"])
        ok = resp.get("status") == "success"
        logfile("FORGOT_PASSWORD: ok" if ok else "FORGOT_PASSWORD: failed")
        return {"password_reset": "sent" if ok else "failed", "flag": "yes" if ok else "no"}
    except Exception as e:
        logfile(f"FORGOT_PASSWORD: {e}")
        return {"password_reset": "failed", "flag": "no"}

def user_login_validation(state: Dict) -> Dict:
    """
    Node: user_login_validation — Session on success.
    step1: Check login_status from sign_in.
    step2: Mark session as active on success.
    step3: Return session status for routing.
    """
    if state.get("login_status") == "success":
        logfile("USER_LOGIN_VALIDATION: active")
        return {"session": "active", "flag": "yes"}
    logfile("USER_LOGIN_VALIDATION: inactive")
    return {"session": "inactive", "flag": "no"}

def subscription_validation(state: Dict) -> Dict:
    """
    Node: subscription_validation — Determine plan state.
    step1: Load current subscription for the authenticated user.
    step2: Classify active/expired/none (or failed/unknown).
    step3: Return subscription status and user_id for routing.
    """
    if state.get("flag") != "yes":
        logfile("SUBSCRIPTION_VALIDATION: skipped")
        return {"subscription": "unknown", "flag": "no"}
    try:
        uid = (state.get("user") or {}).get("id") or state.get("user_id")
        sub = get_user_subscription(uid)["subscription"]
        status = "active" if sub.get("plan_id") else "none"
        logfile(f"SUBSCRIPTION_VALIDATION: {status}")
        return {"subscription": status, "flag": "yes", "user_id": uid, "sub_detail": sub}
    except Exception as e:
        logfile(f"SUBSCRIPTION_VALIDATION: {e}")
        return {"subscription": "failed", "flag": "no"}

def subscription_plan(state: Dict) -> Dict:
    """
    Node: subscription_plan — Apply the selected plan.
    step1: Accept new_plan_id coming from UI selection.
    step2: Update subscription; email confirmation.
    step3: Return subscription_status for routing/UX.
    """
    if state.get("flag") != "yes":
        logfile("SUBSCRIPTION_PLAN: skipped")
        return {"subscription_status": "not_subscribed", "flag": "no"}
    try:
        new_plan = state.get("new_plan_id")
        uid = state.get("user_id") or (state.get("user") or {}).get("id")
        if new_plan and uid:
            resp = svc_upgrade_plan(uid, new_plan)
            ok = resp.get("status") == "success"
            logfile("SUBSCRIPTION_PLAN: ok" if ok else "SUBSCRIPTION_PLAN: failed")
            return {"subscription_status": "subscribed" if ok else "failed", "flag": "yes" if ok else "no"}
        logfile("SUBSCRIPTION_PLAN: pending")
        return {"subscription_status": "pending", "flag": "yes"}
    except Exception as e:
        logfile(f"SUBSCRIPTION_PLAN: {e}")
        return {"subscription_status": "failed", "flag": "no"}

def subscribed(state: Dict) -> Dict:
    """
    Node: subscribed — Gate to features.
    step1: Confirm prior steps passed; plan is usable.
    step2: Echo user_id, user, login_status for the UI.
    step3: Provide stable end point for auth flows.
    """
    if state.get("flag") != "yes":
        logfile("SUBSCRIBED: denied")
        return {"access": "denied", "flag": "no"}
    uid = state.get("user_id") or (state.get("user") or {}).get("id")
    logfile("SUBSCRIBED: granted")
    return {
        "access": "granted",
        "flag": "yes",
        "login_status": state.get("login_status", "success"),
        "user": state.get("user"),
        "user_id": uid,
    }

def user_selection(state: Dict) -> Dict:
    """
    Node: user_selection — Choose workflow.
    step1: Require user_id; otherwise block usage.
    step2: Accept 'image' or 'report' from UI.
    step3: Return selection for conditional routing.
    """
    if state.get("flag") != "yes":
        logfile("USER_SELECTION: skipped")
        return {"selection": None, "flag": "no"}
    uid = state.get("user_id") or (state.get("user") or {}).get("id")
    if not uid:
        logfile("USER_SELECTION: missing user_id")
        return {"selection": None, "flag": "no"}
    choice = state.get("selection")
    logfile(f"USER_SELECTION: {choice}")
    return {"selection": choice, "flag": "yes", "user_id": uid}

def image_processing(state: Dict) -> Dict:
    """
    Node: image_processing — Execute image workflow.
    step1: Ensure valid user_id; enforce access control.
    step2: Record feature usage (no login counter).
    step3: Return image_done on success.
    """
    if state.get("flag") != "yes":
        logfile("IMAGE_PROCESSING: skipped")
        return {"task": "not_processed", "flag": "no"}
    uid = state.get("user_id")
    if not uid:
        logfile("IMAGE_PROCESSING: missing user_id")
        return {"task": "failed", "flag": "no"}
    use_feature(uid, "image")
    logfile("IMAGE_PROCESSING: done")
    return {"task": "image_done", "flag": "yes"}

def report_processing(state: Dict) -> Dict:
    """
    Node: report_processing — Execute report workflow.
    step1: Ensure valid user_id; enforce access control.
    step2: Record feature usage (no login counter).
    step3: Return report_done on success.
    """
    if state.get("flag") != "yes":
        logfile("REPORT_PROCESSING: skipped")
        return {"task": "not_processed", "flag": "no"}
    uid = state.get("user_id")
    if not uid:
        logfile("REPORT_PROCESSING: missing user_id")
        return {"task": "failed", "flag": "no"}
    use_feature(uid, "report")
    logfile("REPORT_PROCESSING: done")
    return {"task": "report_done", "flag": "yes"}

# -------------------- Single Master Graph --------------------

workflow = StateGraph(dict)

# Nodes
for name, fn in [
    ("start_router", start_router),
    ("sign_up", sign_up),
    ("user_registration", user_registration),
    ("sign_in", sign_in),
    ("forgot_password", forgot_password),
    ("user_login_validation", user_login_validation),
    ("subscription_validation", subscription_validation),
    ("subscription_plan", subscription_plan),
    ("subscribed", subscribed),
    ("user_selection", user_selection),
    ("image_processing", image_processing),
    ("report_processing", report_processing),
]:
    workflow.add_node(name, fn)

# Entry and initial routing
workflow.set_entry_point("start_router")

def _route_start(x: Dict) -> str:
    """
    step1: Map start_at to a real node.
    step2: Support all entry paths from the UI.
    step3: Default to 'sign_in' when missing.
    """
    route = x.get("start_at") or "sign_in"
    mapping = {
        "sign_in": "sign_in",
        "sign_up": "sign_up",
        "user_registration": "user_registration",
        "forgot_password": "forgot_password",
        "subscription_validation": "subscription_validation",
        "subscription_plan": "subscription_plan",
        "user_selection": "user_selection",
    }
    return mapping.get(route, "sign_in")

workflow.add_conditional_edges(
    "start_router",
    _route_start,
    {
        "sign_in": "sign_in",
        "sign_up": "sign_up",
        "user_registration": "user_registration",
        "forgot_password": "forgot_password",
        "subscription_validation": "subscription_validation",
        "subscription_plan": "subscription_plan",
        "user_selection": "user_selection",
    },
)



# Common flow edges (your diagram)
workflow.add_edge("sign_up", "user_registration")
workflow.add_edge("user_registration", "user_login_validation")
workflow.add_edge("sign_in", "user_login_validation")
workflow.add_edge("forgot_password", "user_login_validation")
workflow.add_edge("user_login_validation", "subscription_validation")

def _route_sub(x: Dict) -> str:
    """
    step1: Inspect subscription classification.
    step2: Route 'active' directly to subscribed.
    step3: Route others to subscription_plan.
    """
    return "subscribed" if x.get("subscription") == "active" else "subscription_plan"

workflow.add_conditional_edges(
    "subscription_validation",
    _route_sub,
    {"subscribed": "subscribed", "subscription_plan": "subscription_plan"},
)

def _after_subscribed(x: Dict) -> str:
    """
    step1: Check if a valid selection is present.
    step2: If selection exists, proceed to user_selection.
    step3: Otherwise, end the flow (login/upgrade complete).
    """
    sel = (x.get("selection") or "").strip().lower()
    return "user_selection" if sel in ("image", "report") else "end"

workflow.add_conditional_edges(
    "subscribed",
    _after_subscribed,
    {"user_selection": "user_selection", "end": END},
)

workflow.add_edge("subscription_plan", "subscribed")

def _route_choice(x: Dict) -> str:
    """
    step1: Normalize selection to image/report.
    step2: Route accordingly.
    step3: Default to report for unknown values.
    """
    return "image_processing" if x.get("selection") == "image" else "report_processing"

workflow.add_conditional_edges(
    "user_selection",
    _route_choice,
    {"image_processing": "image_processing", "report_processing": "report_processing"},
)

workflow.add_edge("image_processing", END)
workflow.add_edge("report_processing", END)

graph = workflow.compile()
