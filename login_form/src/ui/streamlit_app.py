# Streamlit UI for auth flows; each page is annotated with the node number and purpose

from __future__ import annotations
import os
from typing import Dict, Any, Optional
import requests
import streamlit as st

# Base URL for FastAPI backend (override via FASTAPI_BASE_URL if needed)
API_BASE = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

# [Utility] Not a node: small HTTP helpers
def api_get(path: str) -> Dict[str, Any]:
    r = requests.get(f"{API_BASE}{path}", timeout=15)
    return r.json() if r.headers.get("content-type","").startswith("application/json") else {"status":"error","message":r.text}

def api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{API_BASE}{path}", json=payload, timeout=20)
    return r.json() if r.headers.get("content-type","").startswith("application/json") else {"status":"error","message":r.text}

# [Utility] Not a node: session bootstrap
def init_session():
    if "current_page" not in st.session_state: st.session_state.current_page = "welcome"
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    if "user" not in st.session_state: st.session_state.user = None
    if "notice" not in st.session_state: st.session_state.notice = None
    if "error" not in st.session_state: st.session_state.error = None

# Node3: sign_in — Collect credentials and initiate login request
# Node5: user_login_validation — Validate response and transition to an authenticated session
def page_login():
    st.title("Login")
    if st.session_state.error: st.error(st.session_state.error); st.session_state.error = None
    if st.session_state.notice: st.success(st.session_state.notice); st.session_state.notice = None

    with st.form("login_form"):
        identifier = st.text_input("Email or Phone")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if not identifier or not password:
            st.session_state.error = "Please fill in all fields."
            st.rerun()
        resp = api_post("/auth/login", {"email_or_phone": identifier, "password": password})
        if resp.get("status") == "success":
            st.session_state.logged_in = True
            st.session_state.user = resp.get("user", {})
            st.session_state.notice = resp.get("message", "Login successful.")
            st.session_state.current_page = "dashboard"
            st.rerun()
        else:
            st.session_state.error = resp.get("message", "Login failed.")
            st.rerun()

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Back"):
            st.session_state.current_page = "welcome"; st.rerun()
    with c2:
        if st.button("Register"):
            st.session_state.current_page = "register"; st.rerun()
    with c3:
        if st.button("Forgot password"):
            st.session_state.current_page = "forgot_password"; st.rerun()

# Node1: sign_up — Create a new account with plan choice
# Node2: user_registration — Complete verification/confirmation and route to login
def page_register():
    st.title("Register")
    st.subheader("Choose a Plan")
    plans = api_get("/plans").get("plans", [])
    options = [p["plan_id"] for p in plans] if plans else ["free","basic","pro"]
    selected = st.selectbox(
        "Plan",
        options=options,
        format_func=lambda pid: next((f"{p['name']} - ${p['price']}/month ({p['usage_limit']} daily logins)"
                                      for p in plans if p.get("plan_id")==pid), pid)
    )

    st.divider()
    with st.form("register_form"):
        name = st.text_input("Full name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        pw = st.text_input("Password", type="password")
        cpw = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account")

    if submitted:
        if not all([name, email, phone, pw, cpw]):
            st.error("Please fill in all fields."); return
        if pw != cpw:
            st.error("Passwords do not match."); return
        if len(pw) < 6:
            st.error("Password must be at least 6 characters."); return
        resp = api_post("/auth/register", {
            "name": name, "email": email, "phone": phone, "password": pw, "plan_id": selected
        })
        if resp.get("status") == "success":
            st.session_state.notice = resp.get("message", "Registration successful, please login.")
            st.session_state.current_page = "login"
            st.rerun()
        else:
            st.error(resp.get("message", "Registration failed."))

    st.divider()
    if st.button("Back to Login"): st.session_state.current_page = "login"; st.rerun()

# Node4: forgot_password — Initiate password reset by sending a reset token to the user
def page_forgot_password():
    st.title("Forgot password")
    with st.form("forgot_form"):
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        submitted = st.form_submit_button("Send reset link")
    if submitted:
        if not email or not phone:
            st.error("Please enter both email and phone."); return
        resp = api_post("/auth/forgot-password", {"email": email, "phone": phone})
        if resp.get("status") == "success":
            st.session_state.notice = resp.get("message", "Reset link sent, check your inbox.")
            st.session_state.current_page = "reset_password"
            st.rerun()
        else:
            st.error(resp.get("message", "Failed to send reset link."))
    st.divider()
    if st.button("Back to Login"): st.session_state.current_page = "login"; st.rerun()

# Node4: forgot_password (completion) — Verify token and set a new password
def page_reset_password():
    st.title("Reset password")
    with st.form("reset_form"):
        email = st.text_input("Email")
        token = st.text_input("Reset token")
        new_pw = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Reset password")
    if submitted:
        if not all([email, token, new_pw, confirm]):
            st.error("Please fill in all fields."); return
        if new_pw != confirm:
            st.error("Passwords do not match."); return
        if len(new_pw) < 6:
            st.error("Password must be at least 6 characters."); return
        resp = api_post("/reset-password", {"email": email, "reset_token": token, "new_password": new_pw})
        if resp.get("status") == "success":
            st.session_state.notice = "Password reset successful, please login."
            st.session_state.current_page = "login"
            st.rerun()
        else:
            st.error(resp.get("message", "Password reset failed."))

# Node6: subscription_validation — Display current plan and usage gating
# Node8: subscribed — Confirm active subscription
# Node9: user_selection — Navigate to features (selection page)
def page_dashboard():
    if not st.session_state.logged_in:
        st.session_state.error = "Please login to access the dashboard."
        st.session_state.current_page = "login"
        st.rerun()
    user = st.session_state.user or {}
    st.title(f"Dashboard — Welcome {user.get('name','User')}")
    if st.button("Logout"):
        api_post("/auth/logout", {"user_id": user.get("id")})
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.notice = "Logged out."
        st.session_state.current_page = "welcome"
        st.rerun()

    sub = api_get(f"/user/{user.get('id')}/subscription").get("subscription", {})
    usage = api_get(f"/user/{user.get('id')}/usage").get("usage", {})
    limit_ = sub.get("usage_limit", 0); used = usage.get("current_usage", 0)
    remaining = max(0, limit_ - used)

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Plan", sub.get("plan_name","Unknown"), f"${sub.get('price',0)}/month" if sub.get("price",0) else "Free")
    with c2: st.metric("Daily Remaining", f"{remaining}/{limit_}", f"{used} used today")
    with c3:
        pct = (used/limit_ * 100) if limit_ else 0
        st.metric("Usage Today", f"{pct:.1f}%", "of daily limit")
    if limit_: st.progress(min(1.0, used/limit_))
    if remaining <= 1: st.warning(f"Low remaining logins today: {remaining}.")
    if remaining <= 0: st.error("Daily login limit reached.")

    st.divider()
    c4, c5, c6 = st.columns(3)
    with c4:
        if st.button("Upgrade Plan"):
            st.session_state.current_page = "upgrade"; st.rerun()
    with c5:
        if st.button("Usage Details"):
            st.session_state.current_page = "usage_details"; st.rerun()
    with c6:
        if st.button("Choose Feature"):
            st.session_state.current_page = "user_selection"; st.rerun()

# Node7: subscription_plan — Present higher tiers and process upgrade to complete Node8
def page_upgrade():
    if not st.session_state.logged_in:
        st.session_state.error = "Please login first."
        st.session_state.current_page = "login"; st.rerun()
    user = st.session_state.user or {}
    st.title("Upgrade plan")
    current = api_get(f"/user/{user.get('id')}/subscription").get("subscription", {})
    st.info(f"Current plan: {current.get('plan_name','Unknown')}")
    plans = api_get("/plans").get("plans", [])
    rank = {"free":0,"basic":1,"pro":2}
    cur_level = rank.get(current.get("plan_id","free"),0)
    upgrades = [p for p in plans if rank.get(p["plan_id"],0) > cur_level]
    if not upgrades:
        st.success("Already on the highest plan.")
        if st.button("Back to Dashboard"):
            st.session_state.current_page = "dashboard"; st.rerun()
        return
    for p in upgrades:
        with st.container():
            c1, c2 = st.columns([3,1])
            with c1:
                st.subheader(p["name"])
                st.write(f"Price: ${p['price']}/month")
                st.write(f"Daily Logins: {p['usage_limit']}")
                if p.get("features"): st.write("Features: " + ", ".join([f.replace('_',' ').title() for f in p["features"]]))
            with c2:
                if st.button(f"Upgrade to {p['name']}", key=f"u_{p['plan_id']}"):
                    resp = api_post("/auth/upgrade", {"user_id": user.get("id"), "new_plan_id": p["plan_id"]})
                    if resp.get("status") == "success":
                        if resp.get("subscription"): st.session_state.user["subscription"] = resp["subscription"]
                        st.session_state.notice = resp.get("message","Plan upgraded.")
                        st.session_state.current_page = "dashboard"; st.rerun()
                    else:
                        st.error(resp.get("message","Upgrade failed."))
    st.divider()
    if st.button("Back to Dashboard"): st.session_state.current_page = "dashboard"; st.rerun()

# Node9: user_selection — Present choices and route to Node10/Node11
def page_user_selection():
    if not st.session_state.logged_in:
        st.session_state.error = "Please login first."
        st.session_state.current_page = "login"; st.rerun()
    st.title("Choose a Feature")
    choice = st.radio("Select a workflow", ["Image Processing", "Report Processing"])
    go = st.button("Continue")
    if go:
        if choice.startswith("Image"):
            st.session_state.current_page = "image_processing"; st.rerun()
        else:
            st.session_state.current_page = "report_processing"; st.rerun()
    if st.button("Back to Dashboard"): st.session_state.current_page = "dashboard"; st.rerun()

# Node10: image_processing — Handle image workflow UI (placeholder processing + usage record)
def page_image_processing():
    if not st.session_state.logged_in:
        st.session_state.error = "Please login first."
        st.session_state.current_page = "login"; st.rerun()
    user = st.session_state.user or {}
    st.title("Image Processing")
    file = st.file_uploader("Upload an image", type=["png","jpg","jpeg"])
    if file is not None:
        st.image(file, caption="Preview", use_column_width=True)
    run = st.button("Run Image Workflow")
    if run:
        # Optional: call a future processing endpoint here
        api_post(f"/user/{user.get('id')}/use-feature", {"feature": "image"})
        st.success("Image processing completed (demo).")
    st.divider()
    if st.button("Back to Selection"): st.session_state.current_page = "user_selection"; st.rerun()

# Node11: report_processing — Handle report workflow UI (placeholder processing + usage record)
def page_report_processing():
    if not st.session_state.logged_in:
        st.session_state.error = "Please login first."
        st.session_state.current_page = "login"; st.rerun()
    user = st.session_state.user or {}
    st.title("Report Processing")
    doc = st.file_uploader("Upload a report (PDF/TXT)", type=["pdf","txt"])
    if doc is not None:
        st.info(f"Loaded file: {doc.name}")
    run = st.button("Run Report Workflow")
    if run:
        # Optional: call a future processing endpoint here
        api_post(f"/user/{user.get('id')}/use-feature", {"feature": "report"})
        st.success("Report processing completed (demo).")
    st.divider()
    if st.button("Back to Selection"): st.session_state.current_page = "user_selection"; st.rerun()

# Node9: user_selection — Detailed usage page as a post‑login selection
def page_usage_details():
    if not st.session_state.logged_in:
        st.session_state.error = "Please login first."
        st.session_state.current_page = "login"; st.rerun()
    user = st.session_state.user or {}
    st.title("Usage details")
    usage = api_get(f"/user/{user.get('id')}/usage").get("usage", {})
    c1, c2 = st.columns(2)
    with c1: st.metric("Today's Logins", usage.get("current_usage", 0))
    with c2: st.metric("Period", usage.get("period","Today"))
    acts = usage.get("recent_activities", [])
    if acts:
        st.subheader("Recent Activities")
        for a in acts[:10]:
            st.write(f"- {a.get('feature','login').title()} at {a.get('timestamp','')}")
    else:
        st.info("No recent activities found.")
    st.divider()
    if st.button("Back to Dashboard"): st.session_state.current_page = "dashboard"; st.rerun()

# [Utility] Not a node: welcome and router
def page_welcome():
    st.title("Welcome")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Login"): st.session_state.current_page = "login"; st.rerun()
    with c2:
        if st.button("Register"): st.session_state.current_page = "register"; st.rerun()
    with c3:
        if st.button("Forgot password"): st.session_state.current_page = "forgot_password"; st.rerun()

def main():
    st.set_page_config(page_title="Auth UI", page_icon="🔐", layout="wide", initial_sidebar_state="collapsed")
    init_session()
    page = st.session_state.current_page
    if st.session_state.logged_in:
        if page == "upgrade": page_upgrade()
        elif page == "usage_details": page_usage_details()
        elif page == "user_selection": page_user_selection()
        elif page == "image_processing": page_image_processing()
        elif page == "report_processing": page_report_processing()
        else: page_dashboard()
    else:
        if page == "login": page_login()
        elif page == "register": page_register()
        elif page == "forgot_password": page_forgot_password()
        elif page == "reset_password": page_reset_password()
        else: page_welcome()

if __name__ == "__main__":
    main()
