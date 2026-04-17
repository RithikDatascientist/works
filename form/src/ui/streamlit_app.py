from __future__ import annotations

import os
import sys
import streamlit as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.lang_graph import graph
from utils.functions import get_user_subscription, get_user_usage

def init_session():
    defaults = dict(
        current_page="welcome",
        logged_in=False,
        user=None,
        user_id=None,          # persist canonical id here
        pending_email="",
        notice=None,
        error=None,
        last_selection=None,
        _open_upgrade=False,
    )
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def current_user_id() -> str | None:
    # Resolve from session; normalize common keys
    uid = st.session_state.get("user_id")
    if uid:
        return uid
    user = st.session_state.get("user") or {}
    uid = user.get("id") or user.get("_id") or user.get("user_id")
    if uid:
        st.session_state.user_id = uid
    return uid

def page_welcome():
    st.title("Welcome")
    c1, c2, c3 = st.columns(3)
    if c1.button("Login"): st.session_state.current_page = "login"; st.rerun()
    if c2.button("Register"): st.session_state.current_page = "register"; st.rerun()
    if c3.button("Forgot password"): st.session_state.current_page = "forgot_password"; st.rerun()

def page_register():
    st.title("Register")
    plan_id = st.selectbox("Plan", options=["free","basic","pro"], index=0)
    with st.form("register_form"):
        name = st.text_input("Full name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        pw = st.text_input("Password", type="password")
        cpw = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account")
    if submitted:
        if pw != cpw:
            st.error("Passwords do not match."); return
        out = graph.invoke({
            "start_at": "sign_up",
            "full_name": name,
            "email": email,
            "phone": phone,
            "password": pw,
            "plan_id": plan_id
        })
        if out.get("flag") == "yes":
            st.success("Registration created, check email for OTP.")
            st.session_state.pending_email = email
            st.session_state.current_page = "verify_account"; st.rerun()
        else:
            st.error("Registration failed.")

def page_verify_account():
    st.title("Verify Account")
    with st.form("verify_form"):
        email = st.text_input("Email", value=st.session_state.get("pending_email",""))
        otp = st.text_input("OTP Code")
        submitted = st.form_submit_button("Verify")
    if submitted:
        out = graph.invoke({"start_at": "user_registration", "email": email, "otp_code": otp, "flag": "yes"})
        if out.get("registration_status") == "verified":
            st.success("Verified. Please login.")
            st.session_state.current_page = "login"; st.rerun()
        else:
            st.error("Verification failed.")

def page_login():
    st.title("Login")
    with st.form("login_form"):
        identifier = st.text_input("Email or Phone")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        out = graph.invoke({"start_at": "sign_in", "email_or_phone": identifier, "password": password})
        status = out.get("login_status")
        if status == "success":
            user = out.get("user", {}) or {}
            uid = out.get("user_id") or user.get("id") or user.get("_id") or user.get("user_id")
            # Fallback: if uid still None, query subscription_validation to resolve it from user
            if not uid:
                probe = graph.invoke({"start_at": "subscription_validation", "user": user, "flag": "yes"})
                uid = probe.get("user_id")
            if not uid:
                st.error("Login succeeded but user id is missing; please try again.")
                return
            st.session_state.user = user
            st.session_state.user_id = uid
            st.session_state.logged_in = True
            st.session_state.current_page = "dashboard"; st.rerun()
        elif status == "verification_required":
            st.info("Please verify your account first.")
            st.session_state.pending_email = out.get("email","")
            st.session_state.current_page = "verify_account"; st.rerun()
        else:
            st.error("Login failed.")

def page_forgot_password():
    st.title("Forgot password")
    with st.form("forgot_form"):
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        submitted = st.form_submit_button("Send reset token")
    if submitted:
        st.success("If this email/phone exists, a reset token was sent.")

def _top_plan_id(plans: list[dict]) -> str:
    if not plans: return "pro"
    return sorted(plans, key=lambda p: p.get("price", 0))[-1]["plan_id"]

def page_dashboard():
    if not st.session_state.logged_in:
        st.session_state.current_page = "login"; st.rerun()
    user = st.session_state.user or {}
    uid = current_user_id()
    st.title(f"Dashboard — Welcome {user.get('name','User')}")

    sub = get_user_subscription(uid or "").get("subscription", {})
    usage = get_user_usage(uid or "").get("usage", {})
    plan_name = sub.get("plan_name", "Unknown")
    plan_id = sub.get("plan_id", "free")
    limit_ = sub.get("usage_limit", 0)
    used = usage.get("current_usage", 0)
    st.metric("Plan", plan_name)
    st.metric("Daily Remaining", f"{max(0, limit_-used)}/{limit_}")
    st.metric("Usage Today", f"{(used/limit_ * 100 if limit_ else 0):.1f}%")

    plans = [{"plan_id":"free","price":0},{"plan_id":"basic","price":9},{"plan_id":"pro","price":29}]
    top_plan = _top_plan_id(plans)
    is_top = (plan_id == top_plan)

    cols = st.columns([1,1,8])
    if not is_top and cols[0].button("⬆️ Upgrade", help="Open upgrade options"):
        st.session_state._open_upgrade = True

    if not is_top:
        with st.expander("Upgrade plan", expanded=st.session_state.get("_open_upgrade", False)):
            st.session_state._open_upgrade = False
            plan_ids = [p["plan_id"] for p in plans]
            sel_index = plan_ids.index(plan_id) if plan_id in plan_ids else 0
            sel = st.selectbox("Choose new plan", options=plan_ids, index=sel_index)
            if st.button("Upgrade now"):
                if sel == plan_id:
                    st.info("Already on this plan."); return
                if not uid:
                    st.error("Missing user id; please re-login."); return
                out = graph.invoke({
                    "start_at": "subscription_plan",
                    "flag": "yes",
                    "user_id": uid,
                    "new_plan_id": sel
                })
                if out.get("subscription_status") == "subscribed":
                    st.success(f"Upgraded to {sel}.")
                    st.rerun()
                else:
                    st.error("Upgrade failed.")
    else:
        st.caption("You are on the highest plan; no upgrades available.")

    c1, c2, c3 = st.columns(3)
    if c1.button("Choose Feature"):
        st.session_state.current_page = "selection"; st.rerun()
    if c2.button("Refresh"):
        st.rerun()
    if c3.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.user_id = None
        st.session_state.current_page = "welcome"; st.rerun()

def page_selection():
    if not st.session_state.logged_in:
        st.session_state.current_page = "login"; st.rerun()
    user = st.session_state.user or {}
    uid = current_user_id()
    st.title("Select a feature")
    choice = st.radio("Feature", options=["image","report"], index=0, horizontal=True)
    if st.button("Use selected feature"):
        if not uid:
            st.error("Missing user id; please re-login."); return
        out = graph.invoke({
            "start_at": "user_selection",
            "flag": "yes",
            "selection": choice,
            "user_id": uid
        })
        ok = out.get("task") in ("image_done","report_done")
        if ok:
            st.success("Feature used.")
            st.session_state.last_selection = choice
        else:
            st.error("Failed to use feature.")
    if st.button("Back to Dashboard"):
        st.session_state.current_page = "dashboard"; st.rerun()

def main():
    st.set_page_config(page_title="LangGraph Auth UI", page_icon="🔐", layout="wide", initial_sidebar_state="collapsed")
    init_session()
    page = st.session_state.current_page
    if st.session_state.logged_in:
        page_selection() if page == "selection" else page_dashboard()
    else:
        routes = {
            "login": page_login,
            "register": page_register,
            "verify_account": page_verify_account,
            "forgot_password": page_forgot_password,
            "reset_password": page_verify_account,
        }
        routes.get(page, page_welcome)()

if __name__ == "__main__":
    main()
