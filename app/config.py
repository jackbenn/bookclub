from dotenv import load_dotenv
import os

load_dotenv()

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "bookclub@mail.bennetto.com")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
BASE_URL = os.environ.get("BASE_URL", "https://bookclub.bennetto.com")
# Token lifetime in minutes
MAGIC_LINK_EXPIRE_MINUTES = 30
SESSION_COOKIE_NAME = "bc_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
