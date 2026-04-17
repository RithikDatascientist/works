# src/api/app.py

# Optional path shim: keep at TOP so early imports work if running this file directly.
# Preferred: run from project root with "uvicorn src.api.app:app --reload" and remove this block.
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from typing_extensions import Annotated
from pydantic import BaseModel, EmailStr, StringConstraints

from config.settings import init_logger
from src.auth.service import (
    bootstrap_databases, register_user, verify_account, login_user, forgot_password,
    reset_password, list_all_plans, get_user_subscription, get_user_usage, upgrade_plan, use_feature
)

# ------------------------------------------------------------------------------
# Pydantic request models (Annotated + StringConstraints; no "constr" usage)
# ------------------------------------------------------------------------------

NameStr     = Annotated[str, StringConstraints(min_length=2,  max_length=100, strip_whitespace=True)]
PhoneStr    = Annotated[str, StringConstraints(min_length=6,  max_length=20,  strip_whitespace=True)]
PasswordStr = Annotated[str, StringConstraints(min_length=8,  max_length=128)]
PlanID      = Annotated[str, StringConstraints(min_length=3,  max_length=20,  strip_whitespace=True)]
OTPCode     = Annotated[str, StringConstraints(min_length=4,  max_length=64,  strip_whitespace=True)]
LoginID     = Annotated[str, StringConstraints(min_length=3,  max_length=100, strip_whitespace=True)]
FeatureID   = Annotated[str, StringConstraints(min_length=3,  max_length=32,  strip_whitespace=True)]

class RegisterReq(BaseModel):
    name: NameStr
    email: EmailStr
    phone: PhoneStr
    password: PasswordStr
    plan_id: PlanID = "free"

class VerifyReq(BaseModel):
    email: EmailStr
    otp_code: OTPCode

class LoginReq(BaseModel):
    email_or_phone: LoginID
    password: PasswordStr

class ForgotReq(BaseModel):
    email: EmailStr
    phone: PhoneStr

class ResetReq(BaseModel):
    email: EmailStr
    reset_token: OTPCode
    new_password: PasswordStr

class UpgradeReq(BaseModel):
    user_id: str
    new_plan_id: PlanID

class UseFeatureReq(BaseModel):
    feature: FeatureID

# ------------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------------

log = init_logger("fastapi_api")
app = FastAPI(title="Auth/Subs API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bootstrap_databases()

# ------------------------------------------------------------------------------
# Routes 
# ------------------------------------------------------------------------------

@app.get("/plans")
def plans():
    log.info("NODE-07: subscription_plan -> list_plans")
    return list_all_plans()

@app.post("/auth/register")
def register(req: RegisterReq):
    log.info("NODE-01: sign_up -> request for %s", req.email)
    return register_user(req.name, req.email, req.phone, req.password, req.plan_id)

@app.post("/auth/verify")
def verify(req: VerifyReq):
    log.info("NODE-02: user_registration -> verify %s", req.email)
    return verify_account(req.email, req.otp_code)

@app.post("/auth/login")
def login(req: LoginReq):
    log.info("NODE-03/05: sign_in/user_login_validation -> login attempt %s", req.email_or_phone)
    return login_user(req.email_or_phone, req.password)

@app.post("/auth/forgot-password")
def forgot(req: ForgotReq):
    log.info("NODE-04: forgot_password -> request %s", req.email)
    return forgot_password(req.email, req.phone)

@app.post("/reset-password")
def reset(req: ResetReq):
    log.info("NODE-04: forgot_password -> reset %s", req.email)
    return reset_password(req.email, req.reset_token, req.new_password)

@app.post("/auth/logout")
def logout(payload: dict):
    # stateless for now; client clears session
    log.info("NODE-08: subscribed -> logout user_id=%s", payload.get("user_id"))
    return {"status": "success", "message": "Logged out."}

@app.get("/user/{user_id}/subscription")
def user_subscription(user_id: str):
    log.info("NODE-06/08: subscription_validation/subscribed -> get sub for %s", user_id)
    return get_user_subscription(user_id)

@app.get("/user/{user_id}/usage")
def user_usage(user_id: str):
    log.info("NODE-09: user_selection -> usage for %s", user_id)
    return get_user_usage(user_id)

@app.post("/user/{user_id}/use-feature")
def user_use_feature(user_id: str, req: UseFeatureReq):
    log.info("NODE-10/11: feature -> %s for %s", req.feature, user_id)
    return use_feature(user_id, req.feature)

@app.post("/auth/upgrade")
def upgrade(req: UpgradeReq):
    log.info("NODE-07: subscription_plan -> upgrade user=%s plan=%s", req.user_id, req.new_plan_id)
    return upgrade_plan(req.user_id, req.new_plan_id)
