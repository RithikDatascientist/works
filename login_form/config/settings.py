# config/settings.py
import os
import logging
from datetime import datetime

# Server
FASTAPI_HOST = "0.0.0.0"
FASTAPI_PORT = 8000

# MongoDB
USERS_MONGODB_URI = os.getenv("USERS_MONGODB_URI", "mongodb://localhost:27017")
SUBS_MONGODB_URI = os.getenv("SUBS_MONGODB_URI", "mongodb://localhost:27017")
USERS_DB_NAME = "users_db"
SUBS_DB_NAME = "subs_db"

# SMTP (hardcoded)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "rithik2k2003@gmail.com"
SMTP_PASS = "kdnfzjvqckcdpjxe"

# Logging
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def init_logger(component: str) -> logging.Logger:
    ts = datetime.now().strftime("%Y%m%d")
    logger = logging.getLogger(component)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(f"{LOG_DIR}/{component}_{ts}.log")
        ch = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        fh.setFormatter(fmt); ch.setFormatter(fmt)
        logger.addHandler(fh); logger.addHandler(ch)
    return logger
