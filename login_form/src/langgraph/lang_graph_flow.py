from typing import Dict
from langgraph.graph import StateGraph, END

def logfile(message: str):
    """Simple logger utility"""
    print(message)


# ---------------------
# NODES
# ---------------------

def sign_up(state: Dict) -> Dict:
    """ Node1: sign_up - New user registration via MCP. """
    #step1: Collect user details via MCP
    #step2: Validate input fields
    #step3: Create new account in system
    try:
        logfile("SIGN_UP: Registration completed via MCP")
        return {"status": "registered", "flag": "yes"}
    except Exception as e:
        logfile(f"SIGN_UP: Failed - {str(e)}")
        return {"status": "failed", "flag": "no"}


def user_registration(state: Dict) -> Dict:
    """ Node2: user_registration - Confirm user registration. """
    #step1: Send verification request via MCP
    #step2: Validate OTP or email response
    #step3: Mark user as verified
    if state.get("flag") != "yes":
        logfile("USER_REGISTRATION: Skipped due to previous failure")
        return {"registration_status": "skipped", "flag": "no"}
    try:
        logfile("USER_REGISTRATION: Verification successful")
        return {"registration_status": "verified", "flag": "yes"}
    except Exception as e:
        logfile(f"USER_REGISTRATION: Failed - {str(e)}")
        return {"registration_status": "failed", "flag": "no"}


def sign_in(state: Dict) -> Dict:
    """ Node3: sign_in - Existing user login via MCP. """
    #step1: Collect credentials from user
    #step2: Validate credentials via MCP
    #step3: Log authentication status
    try:
        logfile("SIGN_IN: Login successful via MCP")
        return {"login_status": "success", "flag": "yes"}
    except Exception as e:
        logfile(f"SIGN_IN: Failed - {str(e)}")
        return {"login_status": "failed", "flag": "no"}


def forgot_password(state: Dict) -> Dict:
    """ Node4: forgot_password - Reset password using MCP. """
    #step1: Collect email for reset
    #step2: Send reset link or OTP
    #step3: Confirm new password setup
    try:
        logfile("FORGOT_PASSWORD: Password reset completed via MCP")
        return {"password_reset": "done", "flag": "yes"}
    except Exception as e:
        logfile(f"FORGOT_PASSWORD: Failed - {str(e)}")
        return {"password_reset": "failed", "flag": "no"}


def user_login_validation(state: Dict) -> Dict:
    """ Node5: user_login_validation - Validate login and session. """
    #step1: Verify user credentials
    #step2: Check if account is active
    #step3: Start user session
    if state.get("flag") != "yes":
        logfile("USER_LOGIN_VALIDATION: Skipped due to previous failure")
        return {"session": "inactive", "flag": "no"}
    try:
        logfile("USER_LOGIN_VALIDATION: Session started successfully")
        return {"session": "active", "flag": "yes"}
    except Exception as e:
        logfile(f"USER_LOGIN_VALIDATION: Failed - {str(e)}")
        return {"session": "failed", "flag": "no"}


def subscription_status(state: Dict) -> Dict:
    """ Node6: subscription_status - Check subscription via MCP. """
    #step1: Fetch subscription details
    #step2: Determine current status
    #step3: Log subscription state
    if state.get("flag") != "yes":
        logfile("SUBSCRIPTION_STATUS: Skipped due to previous failure")
        return {"subscription": "unknown", "flag": "no"}
    try:
        subscription = state.get("subscription")
        logfile(f"SUBSCRIPTION_STATUS: {subscription}")
        return {"subscription": subscription, "flag": "yes"}
    except Exception as e:
        logfile(f"SUBSCRIPTION_STATUS: Failed - {str(e)}")
        return {"subscription": "failed", "flag": "no"}


def subscription_plan(state: Dict) -> Dict:
    """ Node7: subscription_plan - Handle plan purchase/renewal. """
    #step1: Present available subscription plans
    #step2: Capture user selection
    #step3: Process subscription payment
    if state.get("flag") != "yes":
        logfile("SUBSCRIPTION_PLAN: Skipped due to previous failure")
        return {"subscription_status": "not_subscribed", "flag": "no"}
    try:
        logfile("SUBSCRIPTION_PLAN: Subscription purchased successfully")
        return {"subscription_status": "subscribed", "flag": "yes"}
    except Exception as e:
        logfile(f"SUBSCRIPTION_PLAN: Failed - {str(e)}")
        return {"subscription_status": "failed", "flag": "no"}


def subscribed(state: Dict) -> Dict:
    """ Node8: subscribed - Confirm subscription active. """
    #step1: Confirm subscription status via MCP
    #step2: Update user privileges
    #step3: Grant access to services
    if state.get("flag") != "yes":
        logfile("SUBSCRIBED: Skipped due to previous failure")
        return {"access": "denied", "flag": "no"}
    try:
        logfile("SUBSCRIBED: Access granted")
        return {"access": "granted", "flag": "yes"}
    except Exception as e:
        logfile(f"SUBSCRIBED: Failed - {str(e)}")
        return {"access": "failed", "flag": "no"}


def user_selection(state: Dict) -> Dict:
    """ Node9: user_selection - Select service option. """
    #step1: Present choices (Image Processing, Report Processing)
    #step2: Capture user choice
    #step3: Route to selected workflow
    if state.get("flag") != "yes":
        logfile("USER_SELECTION: Skipped due to previous failure")
        return {"selection": None, "flag": "no"}
    try:
        choice = state.get("selection")
        logfile(f"USER_SELECTION: User selected {choice}")
        return {"selection": choice, "flag": "yes"}
    except Exception as e:
        logfile(f"USER_SELECTION: Failed - {str(e)}")
        return {"selection": None, "flag": "no"}


# ---------------------
# GRAPH
# ---------------------

workflow = StateGraph(dict)

workflow.add_node("sign_up", sign_up)
workflow.add_node("user_registration", user_registration)
workflow.add_node("sign_in", sign_in)
workflow.add_node("forgot_password", forgot_password)
workflow.add_node("user_login_validation", user_login_validation)
workflow.add_node("subscription_status", subscription_status)
workflow.add_node("subscription_plan", subscription_plan)
workflow.add_node("subscribed", subscribed)
workflow.add_node("user_selection", user_selection)

# Edges
workflow.add_edge("sign_up", "user_registration")
workflow.add_edge("user_registration", "user_login_validation")

workflow.add_edge("sign_in", "user_login_validation")
workflow.add_edge("forgot_password", "user_login_validation")

workflow.add_edge("user_login_validation", "subscription_status")

workflow.add_conditional_edges(
    "subscription_status",
    lambda x: x["subscription"],
    {
        "active": "subscribed",
        "expired": "subscription_plan",
        "none": "subscription_plan"
    },
)

workflow.add_edge("subscription_plan", "subscribed")
workflow.add_edge("subscribed", "user_selection")
workflow.add_edge("user_selection", END)

graph = workflow.compile()
