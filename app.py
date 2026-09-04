import streamlit as st
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import json
import random
import hmac
import hashlib
from datetime import datetime

# Import backend modules
try:
    from config import (
        FAILED_TRANSACTIONS_CSV, 
        RECOVERY_LEDGER_CSV, 
        BASELINE_LEDGER_CSV,
        GEMINI_API_KEY,
        RAZORPAY_KEY_ID,
        RAZORPAY_KEY_SECRET
    )
    from batch_engine import run_baseline_engine, run_recoverflow_engine
    from compliance import check_compliance, transition_state, diagnose_failure, audit_compliance_ledger, verify_webhook_signature
    from recovery_agent import generate_outreach, classify_customer_intent, get_outreach_payment_link, process_customer_turn, process_customer_voice_turn
except ImportError:
    FAILED_TRANSACTIONS_CSV = "failed_transactions.csv"
    RECOVERY_LEDGER_CSV = "recovery_ledger.csv"
    BASELINE_LEDGER_CSV = "baseline_ledger.csv"
    GEMINI_API_KEY = ""
    RAZORPAY_KEY_ID = ""
    RAZORPAY_KEY_SECRET = ""

# Page config & Custom Charcoal dark styling
st.set_page_config(page_title="RecoverFlow AI — Revenue Recovery Dashboard", layout="wide")

# Handle Razorpay browser redirect callback parameter (localhost support)
query_params = st.query_params
if "status" in query_params:
    status = query_params["status"]
    if status == "success":
        # Check if we have an active record to update
        if "sandbox_record" in st.session_state and st.session_state.sandbox_record:
            rec = st.session_state.sandbox_record
            if rec["current_state"] not in ["RECOVERED", "EXHAUSTED", "ESCALATED"]:
                transition_state(rec, "MOCK_PAYMENT_ATTEMPT", {"success": True})
                st.session_state.chat_history.append({
                    "sender": "AI",
                    "text": "Payment Verified: Mandate Reactivated (Detected via Razorpay Browser Redirect).",
                    "reasoning": "Customer was redirected back to the merchant dashboard with status=success parameter."
                })
        st.toast("Redirect Received: Payment Successful!")
        # Clear URL query parameters so it doesn't loop/repeat on refresh
        st.query_params.clear()

# Custom Dark Charcoal CSS injection (Enforcing Manan's UI rules & Razorpay brand style)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Main Background & Fonts */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #0d0c10 !important;
        color: #ffffff !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Headings font family override */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'TASA Orbiter', 'Inter', sans-serif !important;
        font-weight: 600 !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #0d0c10 !important;
        border-right: 1px solid rgba(13, 148, 251, 0.15) !important;
    }
    
    /* Input widgets and buttons */
    div.stButton > button {
        background-color: #0d0c10 !important;
        color: #ffffff !important;
        border: 1px solid rgba(13, 148, 251, 0.2) !important;
        border-radius: 4px !important;
        padding: 8px 16px !important;
        font-weight: 500 !important;
    }
    div.stButton > button:hover {
        border-color: #0D94FB !important;
        color: #0D94FB !important;
    }
    
    /* Tabs custom styling */
    [data-testid="stTab"] {
        color: #8e8e93 !important;
        border-bottom: 2px solid rgba(13, 148, 251, 0.15) !important;
        font-weight: 500 !important;
        background-color: transparent !important;
    }
    [data-testid="stTab"]:hover {
        color: #0D94FB !important;
    }
    [data-testid="stTab"][aria-selected="true"] {
        color: #0D94FB !important;
        border-bottom: 2px solid #0D94FB !important;
    }
    
    /* Cards, containers & borders */
    div[data-testid="stMetricContainer"] {
        background-color: #0d0c10 !important;
        border: 1px solid rgba(13, 148, 251, 0.15) !important;
        border-radius: 8px !important;
        padding: 16px !important;
    }
    
    /* Phone simulator layout styling */
    .phone-container {
        border: 1px solid rgba(13, 148, 251, 0.15);
        background-color: #0d0c10;
        border-radius: 16px;
        padding: 20px;
        max-width: 380px;
        margin: 0 auto;
        min-height: 480px;
        box-shadow: 0px 4px 20px rgba(0, 0, 0, 0.5);
    }
    .chat-bubble-ai {
        background-color: rgba(13, 148, 251, 0.08);
        color: #ffffff;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        text-align: left;
        max-width: 85%;
        float: left;
        clear: both;
        font-size: 0.9rem;
        border: 1px solid rgba(13, 148, 251, 0.15);
        line-height: 1.4;
    }
    .chat-bubble-customer {
        background-color: #ffffff;
        color: #0d0c10;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        text-align: left;
        max-width: 85%;
        float: right;
        clear: both;
        font-size: 0.9rem;
        line-height: 1.4;
    }
    .phone-header {
        text-align: center;
        border-bottom: 1px solid rgba(13, 148, 251, 0.15);
        padding-bottom: 8px;
        margin-bottom: 12px;
        color: #8e8e93;
        font-size: 0.85rem;
    }
    
    /* SMS bubble styles */
    .chat-bubble-sms-ai {
        background-color: rgba(13, 148, 251, 0.12) !important;
        color: #ffffff !important;
        border-radius: 12px !important;
        padding: 10px 14px !important;
        margin: 6px 0 !important;
        text-align: left !important;
        max-width: 80% !important;
        float: left !important;
        clear: both !important;
        font-size: 0.9rem !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    .chat-bubble-sms-customer {
        background-color: #2c2c2e !important;
        color: #ffffff !important;
        border-radius: 12px !important;
        padding: 10px 14px !important;
        margin: 6px 0 !important;
        text-align: left !important;
        max-width: 80% !important;
        float: right !important;
        clear: both !important;
        font-size: 0.9rem !important;
    }
    
    /* Clickable links inside chat bubbles and transcripts */
    .chat-bubble-ai a, .chat-bubble-customer a, .chat-bubble-sms-ai a, .chat-bubble-sms-customer a, .call-screen a {
        color: #0D94FB !important;
        text-decoration: underline !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        word-break: break-all !important;
        transition: color 0.15s ease-in-out !important;
    }
    .chat-bubble-ai a:hover, .chat-bubble-customer a:hover, .chat-bubble-sms-ai a:hover, .chat-bubble-sms-customer a:hover, .call-screen a:hover {
        color: #5bb4ff !important;
        text-decoration: underline !important;
    }
    
    /* Call screen styling */
    .call-screen {
        background-color: #0d0c10 !important;
        color: #ffffff !important;
        border-radius: 16px !important;
        padding: 24px !important;
        text-align: center !important;
        max-width: 380px !important;
        margin: 0 auto !important;
        min-height: 440px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        border: 1px solid rgba(13, 148, 251, 0.15) !important;
        box-shadow: 0px 4px 20px rgba(0, 0, 0, 0.5) !important;
    }
    .call-avatar {
        width: 100px !important;
        height: 100px !important;
        border-radius: 50% !important;
        background-color: rgba(13, 148, 251, 0.1) !important;
        border: 1px solid rgba(13, 148, 251, 0.3) !important;
        margin: 20px auto !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 2.5rem !important;
        color: #0D94FB !important;
    }
    .call-status {
        color: #8e8e93 !important;
        font-size: 0.9rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        margin-bottom: 10px !important;
    }
    .call-number {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        margin-bottom: 30px !important;
    }
    .call-wave {
        display: inline-block !important;
        width: 8px !important;
        height: 8px !important;
        border-radius: 50% !important;
        background-color: #0D94FB !important;
        margin: 0 4px !important;
        animation: wave-anim 1.2s infinite ease-in-out !important;
    }
    @keyframes wave-anim {
        0%, 100% { transform: scale(1); opacity: 0.5; }
        50% { transform: scale(1.6); opacity: 1; }
    }
    @keyframes pulse {
        0% { opacity: 0.3; transform: scale(0.9); }
        50% { opacity: 1; transform: scale(1.2); }
        100% { opacity: 0.3; transform: scale(0.9); }
    }
</style>
""", unsafe_allow_html=True)

def format_clickable_links(text):
    """Converts raw URLs into clickable HTML hyperlinks and converts newlines into <br> tags."""
    if not text:
        return ""
    import re
    url_pattern = re.compile(r'(https?://[^\s<>"]+)')
    
    def _replace(match):
        raw_url = match.group(1)
        trailing = ""
        while raw_url and raw_url[-1] in ".,!?;:)":
            trailing = raw_url[-1] + trailing
            raw_url = raw_url[:-1]
        return f'<a href="{raw_url}" target="_blank" rel="noopener noreferrer">{raw_url}</a>{trailing}'
        
    formatted = url_pattern.sub(_replace, str(text))
    formatted = formatted.replace('\n', '<br>')
    return formatted

# ----------------- SESSION STATE SETUP -----------------
if "run_executed" not in st.session_state:
    st.session_state.run_executed = False
if "baseline_data" not in st.session_state:
    st.session_state.baseline_data = None
if "recoverflow_data" not in st.session_state:
    st.session_state.recoverflow_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "sandbox_record" not in st.session_state:
    st.session_state.sandbox_record = None
if "voice_connected" not in st.session_state:
    st.session_state.voice_connected = False
if "active_payment_link_id" not in st.session_state:
    st.session_state.active_payment_link_id = None
if "active_payment_url" not in st.session_state:
    st.session_state.active_payment_url = None

# Sidebar Configuration
st.sidebar.title("RecoverFlow AI")
st.sidebar.markdown("---")

api_key_input = st.sidebar.text_input(
    "Gemini API Key", 
    value=GEMINI_API_KEY, 
    type="password",
    help="Paste your Google Gemini API key here. If left empty, local mock templates run."
)

if api_key_input and api_key_input.strip():
    st.sidebar.success("**Live AI Active**: `Google Gemini 3.6 Flash`")
else:
    st.sidebar.warning("**Offline/Mock Mode**: Paste Gemini key above for live AI.")


rzp_key_id = st.sidebar.text_input(
    "Razorpay Key ID (Optional)",
    value="",
    type="password",
    help="Enter your Razorpay Test/Live Key ID (e.g. rzp_test_...). If provided, real checkout payment links are generated."
)

rzp_key_secret = st.sidebar.text_input(
    "Razorpay Key Secret (Optional)",
    value="",
    type="password",
    help="Enter your Razorpay Key Secret."
)

def check_and_sync_razorpay(key_id, key_secret, retries=1, sleep_interval=0.7):
    """
    Polls Razorpay's API in real-time to detect payment link completion or decline attempts.
    Uses throttling and fast status checks to keep Streamlit responsive.
    """
    if not (key_id and key_secret and st.session_state.get("active_payment_link_id")):
        return False
        
    pl_id = str(st.session_state.active_payment_link_id).strip()
    if not pl_id.startswith("plink_"):
        return False
        
    active_rec = st.session_state.get("sandbox_record")
    if not active_rec or active_rec.get("current_state") in ["RECOVERED", "EXHAUSTED", "ESCALATED"]:
        return False
        
    import time
    import razorpay
    
    # Throttle sync calls during background auto-polling to avoid saturating network threads
    now = time.time()
    last_sync = st.session_state.get("_last_rzp_sync_ts", 0)
    if retries == 1 and (now - last_sync) < 3.0:
        return False
    st.session_state["_last_rzp_sync_ts"] = now
    
    for attempt_idx in range(retries):
        try:
            client = razorpay.Client(auth=(key_id.strip(), key_secret.strip()))
            
            # 1. Fetch link info (check if fully paid)
            pl_info = client.payment_link.fetch(pl_id)
            
            # Fast check: if link status is already 'paid', complete immediately without fetching all payments
            if pl_info.get("status") == "paid":
                transition_state(active_rec, "MOCK_PAYMENT_ATTEMPT", {"success": True})
                st.session_state.chat_history.append({
                    "sender": "AI",
                    "text": "Payment Completed: Mandate Reactivated (Detected automatically via Razorpay Live Test API).",
                    "reasoning": f"Razorpay Payment Link {pl_id} status changed to 'paid'."
                })
                st.session_state.active_payment_link_id = None
                return True
            
            # 2. Fetch recent payments (query top 10 for maximum speed)
            payments_data = client.payment.all({"count": 10})
            all_payments = payments_data.get("items", []) if isinstance(payments_data, dict) else payments_data
            pl_order_id = pl_info.get("order_id")
            payments_list = [p for p in all_payments if (pl_order_id and p.get("order_id") == pl_order_id)]
            
            failed_count = sum(1 for p in payments_list if p.get("status") == "failed")
            success_detected = any(p.get("status") in ["captured", "authorized"] for p in payments_list)
            
            current_retries = int(active_rec.get("retry_count", 0))
            
            if success_detected:
                transition_state(active_rec, "MOCK_PAYMENT_ATTEMPT", {"success": True})
                st.session_state.chat_history.append({
                    "sender": "AI",
                    "text": "Payment Completed: Mandate Reactivated (Detected automatically via Razorpay Live Test API).",
                    "reasoning": f"Razorpay Payment Link {pl_id} authorized/captured."
                })
                st.session_state.active_payment_link_id = None
                return True
                
            elif failed_count > current_retries:
                attempts_to_add = failed_count - current_retries
                for _ in range(attempts_to_add):
                    transition_state(active_rec, "MOCK_PAYMENT_ATTEMPT", {"success": False})
                    st.session_state.chat_history.append({
                        "sender": "AI",
                        "text": f"Payment attempt failed (Captured via Razorpay API). Attempt {active_rec['retry_count']} of 3.",
                        "reasoning": f"Live payment attempt failure detected for link {pl_id}."
                    })
                    if int(active_rec.get("retry_count", 0)) >= 3:
                        st.session_state.chat_history.append({
                            "sender": "AI",
                            "text": "Limit exhausted, try after 24 hrs.",
                            "reasoning": "Technical retry limit of 3 attempts reached. Enforcement of cooling-off terminal cooldown."
                        })
                        try:
                            client.payment_link.cancel(pl_id)
                            st.toast("Payment Link deactivated on Razorpay servers.")
                        except Exception:
                            pass
                return True
                
        except Exception:
            pass
            
        if attempt_idx < retries - 1:
            time.sleep(sleep_interval)
            
    return False

# Automatic Razorpay Payment Status Polling Check on Page Load
if check_and_sync_razorpay(rzp_key_id, rzp_key_secret, retries=1):
    st.rerun()

st.sidebar.markdown("### Control Center")
if st.sidebar.button("Run Batch Simulation", help="Simulate all transaction records through Naive Baseline vs RecoverFlow Engine"):
    with st.spinner("Processing synthetic transaction stream..."):
        # Force generate data if missing
        if not os.path.exists(FAILED_TRANSACTIONS_CSV):
            import generate_data
            generate_data.generate_synthetic_data(FAILED_TRANSACTIONS_CSV)
            
        # Execute engines
        st.session_state.baseline_data = run_baseline_engine()
        st.session_state.recoverflow_data = run_recoverflow_engine(api_key_input)
        st.session_state.run_executed = True
        total_recs = st.session_state.recoverflow_data.get("total_count", 70)
        st.sidebar.success(f"Simulation complete! {total_recs} records processed.")

# UI Title
st.title("RecoverFlow AI — Revenue Recovery Dashboard")
st.markdown("Automated Failed-Payment and Subscription Mandate Rescue Engine")
st.markdown("---")

# Main Page Tabs
tab_metrics, tab_ledger, tab_sandbox = st.tabs(["Batch Performance & Lift", "Audit Ledger", "Interactive Live Sandbox"])

# ----------------- TAB 1: BATCH METRICS -----------------
with tab_metrics:
    if not st.session_state.run_executed:
        st.info("Click 'Run Batch Simulation' in the sidebar to process the synthetic logs and view conversion metrics.")
    else:
        base = st.session_state.baseline_data
        flow = st.session_state.recoverflow_data
        lift = flow["recovery_rate"] - base["recovery_rate"]
        
        # 1. KPI Row
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Revenue at Risk", f"₹{flow['total_at_risk']:,}")
        col2.metric("Total Revenue Recovered", f"₹{flow['recovered_amount']:,}", f"Lift +{lift:.1f}%")
        col3.metric("RecoverFlow Recovery Rate", f"{flow['recovery_rate']:.1f}%")
        col4.metric("Baseline Naive Recovery", f"{base['recovery_rate']:.1f}%")
        
        st.markdown("---")
        
        # 2. Charts and comparison
        col_chart, col_excep = st.columns([1, 1])
        
        with col_chart:
            st.subheader("Conversion Rate Comparison (Baseline vs AI)")
            # Plot custom Matplotlib chart matching charcoal constraints
            fig, ax = plt.subplots(figsize=(6, 4))
            fig.patch.set_facecolor('#0d0c10')
            ax.set_facecolor('#0d0c10')
            
            categories = ['Baseline (Naive)', 'RecoverFlow AI']
            values = [base['recovery_rate'], flow['recovery_rate']]
            bars = ax.bar(categories, values, color=['#8e8e93', '#ffffff'], width=0.4, edgecolor=(1.0, 1.0, 1.0, 0.06))
            
            # Styling Matplotlib chart monochrome
            ax.set_ylabel('Recovery Rate (%)', color='#ffffff', fontsize=10)
            ax.set_title('Conversion Rate Lift', color='#ffffff', fontsize=12, pad=15)
            ax.tick_params(colors='#ffffff', labelsize=9)
            ax.spines['bottom'].set_color((1.0, 1.0, 1.0, 0.06))
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color((1.0, 1.0, 1.0, 0.06))
            
            for bar in bars:
                height = bar.get_height()
                ax.annotate(f'{height:.1f}%',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3),  
                            textcoords="offset points",
                            ha='center', va='bottom', color='#ffffff', fontsize=9)
            
            st.pyplot(fig)
            
        with col_excep:
            st.subheader("Exception List (Honest Report)")
            st.markdown("Records where recovery was explicitly stopped to comply with rules.")
            
            # Load transactions data to filter exceptions
            try:
                df_tx = pd.read_csv(FAILED_TRANSACTIONS_CSV)
                df_ledger = pd.read_csv(RECOVERY_LEDGER_CSV)
                
                # Fetch final status of each payment in batch run
                final_states = df_ledger.groupby("payment_id").last().reset_index()
                exceptions = final_states[final_states["resulting_state"].isin(["ESCALATED", "EXHAUSTED"])]
                
                # Merge names and amounts from original transactions
                ex_details = exceptions.merge(df_tx[["payment_id", "name", "amount"]], on="payment_id")
                
                # Style display table
                display_ex = ex_details[["payment_id", "name", "amount", "failure_code", "resulting_state", "action_taken"]].rename(columns={
                    "payment_id": "Payment ID",
                    "resulting_state": "Final Status",
                    "action_taken": "Reason For Stopping"
                })
                
                st.dataframe(display_ex, use_container_width=True)
            except Exception as e:
                st.warning("No exception ledger ready yet. Run simulation.")
                
        st.markdown("---")
        # 3. Compliance and Self-Audit Check
        st.subheader("Regulatory & Compliance Self-Audit Report")
        
        # Load ledger to audit
        violations = {"retry_cap_violations": 0, "cooling_off_violations": 0, "opt_out_violations": 0}
        if os.path.exists(RECOVERY_LEDGER_CSV):
            try:
                df_ledger_aud = pd.read_csv(RECOVERY_LEDGER_CSV)
                violations = audit_compliance_ledger(df_ledger_aud)
            except Exception:
                pass
                
        col_aud1, col_aud2, col_aud3, col_aud4 = st.columns(4)
        
        # 1. Retry Cap card
        col_aud1.markdown("**RBI Retry Cap Limit Audit:**")
        rc_v = violations.get("retry_cap_violations", 0)
        if rc_v == 0:
            col_aud1.markdown("**PASS: 0 violations detected.** Maximum retry attempts strictly capped at 3.")
        else:
            col_aud1.markdown(f"**FAIL: {rc_v} violations detected!** Maximum retry cap of 3 bypassed.")
            
        # 2. Cooling-off card
        col_aud2.markdown("**Cooling-Off Window Enforcement:**")
        co_v = violations.get("cooling_off_violations", 0)
        if co_v == 0:
            col_aud2.markdown("**PASS: 0 violations detected.** Mandatory 24h delays enforced on bank declines.")
        else:
            col_aud2.markdown(f"**FAIL: {co_v} violations detected!** Automated retries executed within the 24h cooling-off window.")
            
        # 3. Consent card
        col_aud3.markdown("**Customer Opt-Out Consent Audit:**")
        oo_v = violations.get("opt_out_violations", 0)
        if oo_v == 0:
            col_aud3.markdown("**PASS: 0 violations detected.** Communication halted immediately on customer 'stop'.")
        else:
            col_aud3.markdown(f"**FAIL: {oo_v} violations detected!** Contact attempt made after customer revoked consent.")
            
        # 4. Quiet Hours card
        col_aud4.markdown("**NPCI Quiet Hours Audit:**")
        qh_v = violations.get("quiet_hours_violations", 0)
        if qh_v == 0:
            col_aud4.markdown("**PASS: 0 violations detected.** Outreach strictly blocked between 8:00 PM and 8:00 AM.")
        else:
            col_aud4.markdown(f"**FAIL: {qh_v} violations detected!** Outreach sent during restricted quiet hours.")

# ----------------- TAB 2: AUDIT LEDGER -----------------
with tab_ledger:
    if not os.path.exists(RECOVERY_LEDGER_CSV):
        st.info("No audit ledger found. Complete the batch simulation first.")
    else:
        try:
            df_ledger = pd.read_csv(RECOVERY_LEDGER_CSV)
            st.subheader("Forensic Transaction Event Log")
            st.markdown("Row-by-row event traces logged during the recovery sequence.")
            
            # Filters
            search_tx = st.text_input("Filter by Payment ID (e.g. pay_LkrH5ZBZ5TbhPG)")
            if search_tx:
                filtered_df = df_ledger[df_ledger["payment_id"].str.lower() == search_tx.lower().strip()]
            else:
                filtered_df = df_ledger
                
            st.dataframe(filtered_df, use_container_width=True)
        except Exception as e:
            st.error(f"Error reading ledger: {e}")

# ----------------- TAB 3: LIVE SANDBOX -----------------
with tab_sandbox:
    st.subheader("Interactive Sandbox Simulation")
    st.markdown("*(Clearly Labeled: Illustrative Sandbox Mode — Not part of reproducible batch metrics)*")
    st.markdown("---")
    
    # Initialize sandbox record
    if os.path.exists(FAILED_TRANSACTIONS_CSV):
        try:
            df_tx = pd.read_csv(FAILED_TRANSACTIONS_CSV)
            
            # Compute compliance status globally for the sandbox
            is_compliant = True
            compliance_reason = ""
            if st.session_state.sandbox_record:
                is_compliant, compliance_reason, _ = check_compliance(st.session_state.sandbox_record)
            
            col_sel, col_box = st.columns([1, 1.2])
            
            with col_sel:
                st.markdown("#### Step 1: Select a Failed Record to Generate Webhook")
                selected_row = st.selectbox(
                    "Choose Customer Transaction",
                    options=df_tx.index,
                    format_func=lambda idx: f"{df_tx.loc[idx, 'payment_id']} | {df_tx.loc[idx, 'name']} | {df_tx.loc[idx, 'failure_code']} (₹{df_tx.loc[idx, 'amount']})"
                )
                
                # Fetch record details
                rec = df_tx.loc[selected_row].to_dict()
                rec["retry_count"] = int(rec["retry_count"])
                
                is_checkout_abandoned = rec["failure_code"] == "CHECKOUT_ABANDONED"
                event_name = "order.abandoned" if is_checkout_abandoned else "subscription.charge_failed"
                
                # Generate Razorpay-native webhook payload matching event type
                webhook_payload = {
                    "event": event_name,
                    "account_id": "acc_N1eK9vLzTbhPGe",
                    "contains": ["order", "payment"] if is_checkout_abandoned else ["subscription", "payment"],
                    "payload": {
                        "subscription": {
                            "entity": {
                                "id": rec["subscription_id"],
                                "entity": "subscription",
                                "plan_id": "plan_LkrH5ZBZ5TbhPG",
                                "status": "pending",
                                "current_start": 1787728593,
                                "current_end": 1790320593,
                                "total_count": 12,
                                "paid_count": 3
                            }
                        },
                        "payment": {
                            "entity": {
                                "id": rec["payment_id"],
                                "entity": "payment",
                                "amount": int(rec["amount"]) * 100,  # Razorpay amounts are in paise
                                "currency": "INR",
                                "status": "failed",
                                "method": "card" if rec["failure_code"] == "CARD_EXPIRED" else "upi",
                                "error_code": "payment_failed" if rec["failure_code"] != "BANK_DECLINE_RISK" else "payment_declined_by_bank",
                                "error_description": rec["failure_code"]
                            }
                        }
                    },
                    "created_at": 1787728593
                }
                
                st.markdown("#### Step 2: Simulated Webhook Payload")
                payload_str = json.dumps(webhook_payload, indent=2)
                editable_payload = st.text_area("JSON Body", value=payload_str, height=200)
                
                # Signature inputs
                col_key, col_sig = st.columns([1.2, 2.8])
                webhook_secret = col_key.text_input("Webhook Secret", value="webhook_secret_secure123", type="password")
                
                # Pre-calculate the correct signature so they don't have to manually calculate it
                expected_sig = hmac.new(
                    webhook_secret.encode('utf-8'),
                    editable_payload.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                webhook_sig = col_sig.text_input("x-razorpay-signature Header", value=expected_sig)
                
                if st.button("Verify Signature & Ingest Webhook"):
                    # Call signature verification matching Razorpay client utility SDK
                    if verify_webhook_signature(editable_payload, webhook_sig, webhook_secret):
                        st.success("Signature Verified: Webhook ingested successfully.")
                        st.session_state.sandbox_record = rec
                        st.session_state.chat_history = []
                        # Generate first outreach nudge
                        diag = diagnose_failure(rec["failure_code"])
                        payment_link = get_outreach_payment_link(rec, rzp_key_id, rzp_key_secret)
                        st.session_state.active_payment_url = payment_link
                        outreach = generate_outreach(rec["name"], rec["amount"], rec["failure_code"], payment_link, api_key_input)
                        
                        st.session_state.chat_history.append({
                            "sender": "AI",
                            "text": outreach["script"],
                            "reasoning": outreach["reasoning"]
                        })
                        transition_state(st.session_state.sandbox_record, "OUTBOUND_NUDGE")
                        st.rerun()
                    else:
                        st.error("Signature Verification Failed: Invalid secret or signature header.")
                        
                # Display Current Record State & Diagnostics
                if st.session_state.sandbox_record:
                    active_rec = st.session_state.sandbox_record
                    st.markdown("#### Transaction Diagnostics")
                    
                    # Run compliance check
                    is_compliant, reason, recommended = check_compliance(active_rec)
                    
                    st.markdown(f"**Current State:** `{active_rec['current_state']}`")
                    st.markdown(f"**Technical Retry Count:** `{active_rec['retry_count']} / 3`")
                    st.markdown(f"**Consent Status:** `{active_rec['consent_status']}`")
                    st.markdown(f"**Compliance Status:** {'PASS' if is_compliant else 'BLOCKED'}")
                    st.caption(f"Reason: {reason}")
                    
                    # Diagnostics panel
                    diag = diagnose_failure(active_rec["failure_code"])
                    st.info(f"**Cause:** {diag['cause']}\n\n**Action Plan:** {diag['default_action']}")
                    
            with col_box:
                if not st.session_state.sandbox_record or not st.session_state.chat_history:
                    st.info("Select a customer and click 'Initialize Customer Outreach' to open the smartphone chat mockup.")
                else:
                    active_rec = st.session_state.sandbox_record
                    
                    # Channel Selection radio
                    sandbox_channel = st.radio(
                        "Choose Outreach Channel", 
                        ["WhatsApp", "SMS", "Voice Call (IVR)"], 
                        horizontal=True,
                        help="Route payment recovery outreach through different mock channels."
                    )
                    
                    # Sync Live payment Status manual trigger & Direct checkout link
                    if st.session_state.get("active_payment_link_id") or st.session_state.get("active_payment_url"):
                        col_sync_btn, col_link_btn, col_sync_info = st.columns([1.5, 1.5, 2.0])
                        if col_sync_btn.button("Sync Payment Status", use_container_width=True, help="Fetch the latest transaction and payment attempt statuses from Razorpay's API"):
                            with st.spinner("Checking Razorpay API..."):
                                updated = check_and_sync_razorpay(rzp_key_id, rzp_key_secret, retries=3, sleep_interval=0.7)
                                if updated:
                                    st.toast("Updated from Razorpay API!")
                                    st.rerun()
                                else:
                                    st.toast("Synced with Razorpay. No new attempts recorded.")
                        active_url = st.session_state.get("active_payment_url")
                        if not active_url and st.session_state.get("active_payment_link_id"):
                            active_url = f"https://rzp.io/i/{st.session_state.active_payment_link_id}"
                        if active_url:
                            col_link_btn.link_button("Open Checkout Link", url=active_url, use_container_width=True)
                        col_sync_info.caption(f"Active Link ID: `{st.session_state.get('active_payment_link_id')}`")
                        
                        # Real-time Background Listener (auto-polls every 5 seconds without freezing UI!)
                        @st.fragment(run_every="5s")
                        def live_razorpay_heartbeat():
                            if (rzp_key_id and rzp_key_secret and 
                                st.session_state.get("active_payment_link_id") and 
                                st.session_state.get("sandbox_record") and 
                                st.session_state.sandbox_record.get("current_state") not in ["RECOVERED", "EXHAUSTED", "ESCALATED"]):
                                
                                pl_id = str(st.session_state.active_payment_link_id).strip()
                                if pl_id.startswith("plink_"):
                                    if check_and_sync_razorpay(rzp_key_id, rzp_key_secret, retries=1):
                                        st.rerun()
                                    else:
                                        st.markdown(
                                            "<div style='font-size: 0.78rem; color: #30d158; margin: 4px 0 8px 0; display: flex; align-items: center; gap: 6px;'>"
                                             "<span style='width: 8px; height: 8px; background-color: #30d158; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite;'></span>"
                                            "<strong>Live Auto-Sync Active:</strong> Listening for Razorpay payment pass/fail in real time</div>",
                                            unsafe_allow_html=True
                                        )

                        live_razorpay_heartbeat()
                        
                        # API Diagnostics for Sandbox
                        with st.expander("Razorpay API Diagnostics"):
                            pl_id = str(st.session_state.active_payment_link_id).strip()
                            if not pl_id.startswith("plink_"):
                                st.warning("Diagnostics are only available for live Razorpay payment links (starting with 'plink_').")
                            else:
                                try:
                                    import razorpay
                                    client = razorpay.Client(auth=(rzp_key_id.strip(), rzp_key_secret.strip()))
                                    pl_info = client.payment_link.fetch(pl_id)
                                    st.write("**Link Status:**", pl_info.get("status"))
                                    payments_data = client.payment.all({"count": 50})
                                    all_payments = payments_data.get("items", []) if isinstance(payments_data, dict) else payments_data
                                    pl_order_id = pl_info.get("order_id")
                                    payments_list = [p for p in all_payments if (pl_order_id and p.get("order_id") == pl_order_id)]
                                    st.write(f"**Found Payments Count:** {len(payments_list)}")
                                    for idx, p in enumerate(payments_list):
                                        st.write(f"- Payment #{idx+1} ID: `{p.get('id')}` | Status: `{p.get('status')}` | Error: `{p.get('error_description')}`")
                                except Exception as diag_e:
                                    st.error(f"Failed to fetch diagnostics: {diag_e}")
                    
                    if sandbox_channel == "WhatsApp":
                        st.markdown("#### Simulated WhatsApp Interface")
                        phone_html = f"""
                        <div class="phone-container">
                            <div class="phone-header">WhatsApp: {active_rec['name']} (+91-998877)</div>
                            <div id="chat-area-wa" style="height: 380px; overflow-y: auto; display: flex; flex-direction: column; scroll-behavior: smooth;">
                        """
                        for chat in st.session_state.chat_history:
                            msg_html = format_clickable_links(chat["text"])
                            if chat["sender"] == "AI":
                                phone_html += f'<div class="chat-bubble-ai">{msg_html}</div>'
                            else:
                                phone_html += f'<div class="chat-bubble-customer">{msg_html}</div>'
                        phone_html += """
                            </div>
                        </div>
                        <script>
                            setTimeout(function() {
                                var chatArea = document.getElementById("chat-area-wa");
                                if (chatArea) {
                                    chatArea.scrollTop = chatArea.scrollHeight;
                                }
                            }, 50);
                        </script>
                        """
                        st.markdown(phone_html, unsafe_allow_html=True)
                        
                    elif sandbox_channel == "SMS":
                        st.markdown("#### Simulated SMS Interface")
                        phone_html = f"""
                        <div class="phone-container">
                            <div class="phone-header">SMS: 140-RAZORPAY</div>
                            <div id="chat-area-sms" style="height: 380px; overflow-y: auto; display: flex; flex-direction: column; scroll-behavior: smooth;">
                        """
                        for chat in st.session_state.chat_history:
                            msg_html = format_clickable_links(chat["text"])
                            if chat["sender"] == "AI":
                                phone_html += f'<div class="chat-bubble-sms-ai">{msg_html}</div>'
                            else:
                                phone_html += f'<div class="chat-bubble-sms-customer">{msg_html}</div>'
                        phone_html += """
                            </div>
                        </div>
                        <script>
                            setTimeout(function() {
                                var chatArea = document.getElementById("chat-area-sms");
                                if (chatArea) {
                                    chatArea.scrollTop = chatArea.scrollHeight;
                                }
                            }, 50);
                        </script>
                        """
                        st.markdown(phone_html, unsafe_allow_html=True)
                        
                    elif sandbox_channel == "Voice Call (IVR)":
                        st.markdown("#### Simulated Hinglish IVR Outbound Recovery Call")
                        
                        if not st.session_state.voice_connected:
                            # Ringing screen
                            ringing_html = f"""
                            <div class="call-screen">
                                <div class="call-status">Outbound RecoverFlow Call</div>
                                <div class="call-avatar"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#0D94FB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg></div>
                                <div class="call-number">{active_rec['name']}</div>
                                <div style="color: #8e8e93; font-size: 0.85rem; margin-bottom: 20px;">
                                    Click "Answer Call" to simulate the interactive Hinglish voice synthesis.
                                </div>
                            </div>
                            """
                            st.markdown(ringing_html, unsafe_allow_html=True)
                            
                            c_btns = st.columns(2)
                            if c_btns[0].button("Answer Call", type="primary", use_container_width=True):
                                st.session_state.voice_connected = True
                                st.rerun()
                            if c_btns[1].button("Decline Call", use_container_width=True):
                                st.warning("Call declined. Shifting recovery state.")
                        else:
                            # In call screen
                            call_html = f"""
                            <div class="call-screen">
                                <div class="call-status">Connected <span class="call-wave"></span><span class="call-wave"></span><span class="call-wave"></span></div>
                                <div class="call-avatar"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#0D94FB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="22"></line></svg></div>
                                <div class="call-number">{active_rec['name']} (In-Call)</div>
                                <div style="height: 200px; overflow-y: auto; text-align: left; padding: 10px; background-color: rgba(255,255,255,0.03); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.85rem; line-height: 1.4;">
                                    <strong>Call Transcript:</strong><br><br>
                            """
                            for chat in st.session_state.chat_history:
                                sender_lbl = "AI Recovery Agent" if chat["sender"] == "AI" else f"{active_rec['name']} (Customer)"
                                msg_html = format_clickable_links(chat['text'])
                                call_html += f"<b>{sender_lbl}:</b> {msg_html}<br><br>"
                                
                            call_html += """
                                </div>
                            </div>
                            """
                            st.markdown(call_html, unsafe_allow_html=True)
                            
                            # Browser Speech Synthesis hook
                            last_ai_msg = next((c["text"] for c in reversed(st.session_state.chat_history) if c["sender"] == "AI"), "")
                            if last_ai_msg:
                                clean_msg = last_ai_msg.replace('"', '\\"').replace("'", "\\'").replace("\n", " ")
                                tts_html = f"""
                                <script>
                                if ('speechSynthesis' in window) {{
                                    var textToSpeak = "{clean_msg}";
                                    var isHindi = /[\\u0900-\\u097F]/.test(textToSpeak);
                                    var isHinglish = /\\b(aap|hum|paise|karein|karunga|kardo|bhejo|aaram|bhai|theek|gaye|nhi|nahi)\\b/i.test(textToSpeak);
                                    var linkRepl = "I have sent the link to your registered mobile number";
                                    if (isHindi) {{
                                        linkRepl = "मैंने आपके रजिस्टर्ड मोबाइल नंबर पर लिंक भेज दिया है";
                                    }} else if (isHinglish) {{
                                        linkRepl = "maine aapke registered mobile number par link bhej diya hai";
                                    }}
                                    textToSpeak = textToSpeak.replace(/[,;:]?\\s*(?:please\\s+)?(?:visit|use|access|click|complete it\\s+(?:at|here|using|via)?)\\s*(?:at|here|this link|the link|this secure link)?\\s*[:,-]?\\s*https?:\\/\\/\\S+/gi, ". " + linkRepl + ".");
                                    textToSpeak = textToSpeak.replace(/[,;:]?\\s*(?:here|link|at|via this link)\\s*[:,-]?\\s*https?:\\/\\/\\S+/gi, ". " + linkRepl + ".");
                                    textToSpeak = textToSpeak.replace(/[,;:]?\\s*https?:\\/\\/\\S+/gi, ". " + linkRepl + ".");
                                    textToSpeak = textToSpeak.replace(/[,;:]\\s*\\./g, ".");
                                    textToSpeak = textToSpeak.replace(/\\.\\s*\\./g, ".");
                                    textToSpeak = textToSpeak.replace(/\\s+/g, " ").trim();
                                    
                                    var utterance = new SpeechSynthesisUtterance(textToSpeak);
                                    var voices = window.speechSynthesis.getVoices();
                                    for(var i = 0; i < voices.length; i++) {{
                                        if(voices[i].lang.indexOf('IN') > -1 || voices[i].lang.indexOf('hi') > -1) {{
                                            utterance.voice = voices[i];
                                            break;
                                        }}
                                    }}
                                    window.speechSynthesis.cancel();
                                    window.speechSynthesis.speak(utterance);
                                }}
                                </script>
                                """
                                st.components.v1.html(tts_html, height=0)
                                
                            # Microphone Voice Input for In-Call Talking
                            st.markdown(
                                "<div style='font-size: 0.85rem; color: #30d158; font-weight: 600; margin: 12px 0 6px 0; display: flex; align-items: center; gap: 6px;'>"
                                "<span style='width: 8px; height: 8px; background-color: #30d158; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite;'></span>"
                                "<strong>Talk to Agent</strong> (Click mic to speak your query):</div>",
                                unsafe_allow_html=True
                            )
                            voice_input = st.audio_input("Speak your query", key="ivr_customer_voice", label_visibility="collapsed")
                            if voice_input:
                                audio_data = voice_input.read()
                                import hashlib
                                curr_hash = hashlib.md5(audio_data).hexdigest()
                                if st.session_state.get("last_voice_turn_hash") != curr_hash:
                                    st.session_state.last_voice_turn_hash = curr_hash
                                    with st.spinner("RecoverFlow AI is listening & processing your voice..."):
                                        payment_link = st.session_state.get("active_payment_url")
                                        if not payment_link:
                                            payment_link = get_outreach_payment_link(active_rec, rzp_key_id, rzp_key_secret)
                                            st.session_state.active_payment_url = payment_link
                                            
                                        voice_result = process_customer_voice_turn(
                                            name=active_rec["name"],
                                            amount=active_rec["amount"],
                                            failure_code=active_rec["failure_code"],
                                            payment_link=payment_link,
                                            audio_bytes=audio_data,
                                            mime_type=getattr(voice_input, "type", "audio/wav") or "audio/wav",
                                            api_key_override=api_key_input
                                        )
                                        
                                        transcript_text = voice_result.get("transcript", "Voice response")
                                        st.session_state.chat_history.append({
                                            "sender": "Customer",
                                            "text": f"*\"{transcript_text}\"*",
                                            "reasoning": ""
                                        })
                                        
                                        intent = voice_result.get("intent", "OTHER")
                                        script = voice_result["script"]
                                        reasoning = voice_result.get("reasoning", "")
                                        
                                        if intent == "OPT_OUT":
                                            transition_state(active_rec, "OPT_OUT")
                                        elif intent == "REQUEST_PAYMENT_LINK":
                                            transition_state(active_rec, "SEND_PAYMENT_LINK")
                                        elif intent == "PROMISE_TO_PAY":
                                            transition_state(active_rec, "PROMISE_TO_PAY")
                                            
                                        st.session_state.chat_history.append({
                                            "sender": "AI",
                                            "text": script,
                                            "reasoning": f"Intent: {intent}. {reasoning}"
                                        })
                                    st.rerun()
                                
                            if st.button("Hang Up Call", type="secondary", use_container_width=True):
                                st.session_state.voice_connected = False
                                st.rerun()
                    
                    # Display last AI reasoning card
                    last_chat = st.session_state.chat_history[-1]
                    if last_chat["sender"] == "AI" and last_chat.get("reasoning"):
                        reasoning_str = str(last_chat["reasoning"])
                        if "429" in reasoning_str or "quota" in reasoning_str.lower():
                            st.warning("**Gemini API Rate Limit (429) Hit:** You have exceeded the Free Tier rate limit (5 requests per minute). The system automatically fell back to the local mock template. Please wait 30 seconds before typing your next response to resume live AI mode.")
                        st.markdown(f"**AI Reasoning Audit:** *\"{reasoning_str}\"*")
                        
                    # Sandbox response input
                    if active_rec["current_state"] not in ["RECOVERED", "EXHAUSTED", "ESCALATED"]:
                        if not is_compliant:
                            st.warning(f"**Compliance Block Active:** {reason}. *(Illustrative Sandbox allows you to submit replies here to test conversational prompts, but in the background scheduling pipeline this outreach is delayed).*")
                        
                        # 1-Click Form submission: binds Enter key & Click atomically so single-click always succeeds!
                        with st.form("customer_chat_form", clear_on_submit=True):
                            col_input, col_send = st.columns([4.2, 1.2])
                            with col_input:
                                user_reply = st.text_input(
                                    "Customer Message",
                                    placeholder="Type customer reply (e.g. Kal pay karunga, cancel order, send link)...",
                                    label_visibility="collapsed"
                                )
                            with col_send:
                                submit_clicked = st.form_submit_button("Send", use_container_width=True, type="primary")
                        
                        if submit_clicked and user_reply.strip():
                            with st.spinner("RecoverFlow AI is responding..."):
                                # Append user reply to history
                                st.session_state.chat_history.append({
                                    "sender": "Customer",
                                    "text": user_reply.strip(),
                                    "reasoning": ""
                                })
                                
                                # Reuse active payment link to eliminate heavy Razorpay network calls
                                payment_link = st.session_state.get("active_payment_url")
                                if not payment_link:
                                    payment_link = get_outreach_payment_link(active_rec, rzp_key_id, rzp_key_secret)
                                    st.session_state.active_payment_url = payment_link
                                
                                # High-speed single-pass processing: intent + contextual response in 1 roundtrip!
                                turn_result = process_customer_turn(
                                    name=active_rec["name"],
                                    amount=active_rec["amount"],
                                    failure_code=active_rec["failure_code"],
                                    payment_link=payment_link,
                                    user_reply=user_reply.strip(),
                                    api_key_override=api_key_input,
                                    is_voice=(sandbox_channel == "Voice Call (IVR)")
                                )
                                
                                intent = turn_result.get("intent", "OTHER")
                                script = turn_result["script"]
                                reasoning = turn_result.get("reasoning", "")
                                
                                # State transitions
                                if intent == "OPT_OUT":
                                    transition_state(active_rec, "OPT_OUT")
                                elif intent == "REQUEST_PAYMENT_LINK":
                                    transition_state(active_rec, "SEND_PAYMENT_LINK")
                                elif intent == "PROMISE_TO_PAY":
                                    transition_state(active_rec, "PROMISE_TO_PAY")
                                    
                                st.session_state.chat_history.append({
                                    "sender": "AI",
                                    "text": script,
                                    "reasoning": f"Intent: {intent}. {reasoning}"
                                })
                            st.rerun()
                            
                        # Quick Simulation Actions
                        st.markdown("<div style='margin-top: 10px; font-size: 0.8rem; color: #8e8e93;'>Simulation Shortcuts:</div>", unsafe_allow_html=True)
                        col_sim = st.columns(2)
                        if col_sim[0].button("Simulate Payment Success", use_container_width=True):
                            transition_state(active_rec, "MOCK_PAYMENT_ATTEMPT", {"success": True})
                            st.session_state.chat_history.append({
                                "sender": "AI",
                                "text": "Payment Successful: Mandate Reactivated.",
                                "reasoning": "Webhook mock reports transaction execution completed. Recovery complete."
                            })
                            st.rerun()
                            
                        if col_sim[1].button("Simulate Payment Failure", use_container_width=True):
                            transition_state(active_rec, "MOCK_PAYMENT_ATTEMPT", {"success": False})
                            st.session_state.chat_history.append({
                                "sender": "AI",
                                "text": "Payment declined again by bank. Please check details.",
                                "reasoning": "Payment attempt failed. Decremented retry availability."
                            })
                            if int(active_rec.get("retry_count", 0)) >= 3:
                                st.session_state.chat_history.append({
                                    "sender": "AI",
                                    "text": "Limit exhausted, try after 24 hrs.",
                                    "reasoning": "Technical retry limit of 3 attempts reached. Enforcement of cooling-off terminal cooldown."
                                })
                                # Cancel live link if exists
                                pl_id = st.session_state.get("active_payment_link_id")
                                if pl_id and str(pl_id).startswith("plink_") and rzp_key_id and rzp_key_secret:
                                    try:
                                        import razorpay
                                        client = razorpay.Client(auth=(rzp_key_id.strip(), rzp_key_secret.strip()))
                                        client.payment_link.cancel(pl_id)
                                        st.toast("Payment Link deactivated on Razorpay servers.")
                                    except Exception:
                                        pass
                            st.rerun()
                    else:
                        st.success(f"Transaction recovery process finished with status: **{active_rec['current_state']}**")
        except Exception as e:
            st.error(f"Generate data to initiate sandbox: {e}")
    else:
        st.info("synthetic database not found. Please click 'Run Batch Simulation' in the sidebar.")
