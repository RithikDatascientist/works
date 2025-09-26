# config/settings.py
import os
import logging
from datetime import datetime

# Environment
FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))

USERS_MONGODB_URI = os.getenv("USERS_MONGODB_URI", "mongodb://localhost:27017")
SUBS_MONGODB_URI = os.getenv("SUBS_MONGODB_URI", "mongodb://localhost:27017")
USERS_DB_NAME = os.getenv("USERS_DB_NAME", "users_db")
SUBS_DB_NAME = os.getenv("SUBS_DB_NAME", "subs_db")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def init_logger(component: str) -> logging.Logger:
    ts = datetime.now().strftime("%Y%m%d")
    logger = logging.getLogger(component)
    logger.setLevel(logging.INFO)
    # avoid duplicate handlers during reload
    if not logger.handlers:
        fh = logging.FileHandler(f"{LOG_DIR}/{component}_{ts}.log")
        ch = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        fh.setFormatter(fmt); ch.setFormatter(fmt)
        logger.addHandler(fh); logger.addHandler(ch)
    return logger
