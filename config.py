import os

# Try to load from environment variables first, then Streamlit secrets, then .env
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Streamlit Community Cloud secrets fallback
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        if not GEMINI_API_KEY and "GEMINI_API_KEY" in st.secrets:
            GEMINI_API_KEY = str(st.secrets["GEMINI_API_KEY"])
except Exception:
    pass

# Auto-load Gemini API key from .env if present
env_file = os.path.join(BASE_DIR, ".env")
if not GEMINI_API_KEY and os.path.exists(env_file):
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    GEMINI_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("AI_API_KEY="):
                    GEMINI_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass

# Simulation configurations
RANDOM_SEED = 42
MAX_RETRIES = 3
COOLING_OFF_HOURS = 24  # Enforced for bank-side transient failures

# Local file storage configurations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAILED_TRANSACTIONS_CSV = os.path.join(BASE_DIR, "failed_transactions.csv")
RECOVERY_LEDGER_CSV = os.path.join(BASE_DIR, "recovery_ledger.csv")
BASELINE_LEDGER_CSV = os.path.join(BASE_DIR, "baseline_ledger.csv")
RECOVERFLOW_FINAL_CSV = os.path.join(BASE_DIR, "recoverflow_final_states.csv")
BASELINE_FINAL_CSV = os.path.join(BASE_DIR, "baseline_final_states.csv")

# Razorpay API and Webhook Credentials
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "webhook_secret_secure123")

try:
    import streamlit as st
    if hasattr(st, "secrets"):
        if not RAZORPAY_KEY_ID and "RAZORPAY_KEY_ID" in st.secrets:
            RAZORPAY_KEY_ID = str(st.secrets["RAZORPAY_KEY_ID"])
        if not RAZORPAY_KEY_SECRET and "RAZORPAY_KEY_SECRET" in st.secrets:
            RAZORPAY_KEY_SECRET = str(st.secrets["RAZORPAY_KEY_SECRET"])
        if "RAZORPAY_WEBHOOK_SECRET" in st.secrets:
            RAZORPAY_WEBHOOK_SECRET = str(st.secrets["RAZORPAY_WEBHOOK_SECRET"])
except Exception:
    pass

# Razorpay keys start blank by default unless provided via environment variables or UI
# (Auto-load from CSV disabled)

