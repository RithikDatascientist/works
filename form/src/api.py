# src/api.py
from __future__ import annotations

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

from utils.functions import (
    log, bootstrap_databases, list_all_plans, register_user, verify_account,
    login_user, forgot_password, reset_password, get_user_subscription,
    get_user_usage, upgrade_plan, use_feature
)

from typing_extensions import Annotated
from pydantic import BaseModel, EmailStr, StringConstraints

NameStr     = Annotated[str, StringConstraints(min_length=2,  max_length=20, strip_whitespace=True)]
PhoneStr    = Annotated[str, StringConstraints(min_length=6,  max_length=20,  strip_whitespace=True)]
PasswordStr = Annotated[str, StringConstraints(min_length=8,  max_length=20)]
PlanID      = Annotated[str, StringConstraints(min_length=3,  max_length=20,  strip_whitespace=True)]
OTPCode     = Annotated[str, StringConstraints(min_length=4,  max_length=30, strip_whitespace=True)]
LoginID     = Annotated[str, StringConstraints(min_length=3,  max_length=25, strip_whitespace=True)]
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


app = FastAPI(title="Auth/Subs API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

bootstrap_databases()

@app.get("/plans")
def plans():
    log.info("NODE-07: subscription_plan -> list_plans")
    return list_all_plans()

@app.post("/auth/register")
def api_register(req: RegisterReq):
    return register_user(req.name, req.email, req.phone, req.password, req.plan_id)

@app.post("/auth/verify")
def api_verify(req: VerifyReq):
    return verify_account(req.email, req.otp_code)

@app.post("/auth/login")
def api_login(req: LoginReq):
    return login_user(req.email_or_phone, req.password)

@app.post("/auth/forgot-password")
def api_forgot(req: ForgotReq):
    return forgot_password(req.email, req.phone)

@app.post("/reset-password")
def api_reset(req: ResetReq):
    return reset_password(req.email, req.reset_token, req.new_password)

@app.post("/auth/logout")
def api_logout(payload: dict = Body(default={})):
    log.info("NODE-08: subscribed -> logout user_id=%s", payload.get("user_id"))
    return {"status": "success", "message": "Logged out."}

@app.get("/user/{user_id}/subscription")
def api_user_subscription(user_id: str):
    log.info("NODE-06/08: subscription_validation/subscribed -> get sub for %s", user_id)
    return get_user_subscription(user_id)

@app.get("/user/{user_id}/usage")
def api_user_usage(user_id: str):
    log.info("NODE-09: user_selection -> usage for %s", user_id)
    return get_user_usage(user_id)


@app.post("/user/{user_id}/use-feature")
def api_use_feature(user_id: str, req: UseFeatureReq):
    return use_feature(user_id, req.feature)


@app.post("/auth/upgrade")
def api_upgrade(req: UpgradeReq):
    return upgrade_plan(req.user_id, req.new_plan_id)
