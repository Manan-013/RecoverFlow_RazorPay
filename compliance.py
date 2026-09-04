import os
from datetime import datetime, timedelta

# Import configuration limits
try:
    from config import MAX_RETRIES, COOLING_OFF_HOURS
except ImportError:
    MAX_RETRIES = 3
    COOLING_OFF_HOURS = 24

# Failure Taxonomy & Action Mapping
TAXONOMY = {
    "INSUFFICIENT_FUNDS": {
        "cause": "Customer's bank account has insufficient balance.",
        "default_action": "Wait for salary/funding (or schedule retry in 48h) + offer instant UPI payment link."
    },
    "CARD_EXPIRED": {
        "cause": "The billing credit/debit card has expired.",
        "default_action": "Do not attempt automated retries. Immediately request updated payment details from the customer."
    },
    "BANK_DECLINE_RISK": {
        "cause": "Bank network flagged transaction as high risk or temporarily blocked recurring debits.",
        "default_action": "Wait 24h cooling-off period, attempt 1 automated retry, then escalate if failed again."
    },
    "NETWORK_TIMEOUT": {
        "cause": "Transient gateway network timeout or bank API error.",
        "default_action": "Attempt 1 immediate retry. If fails again, wait 24h before next retry."
    },
    "MANDATE_REVOKED": {
        "cause": "Customer has revoked the authorization mandate directly with their bank.",
        "default_action": "Halt all automatic billing. Notify the customer and offer a secure link to register a new mandate."
    },
    "INVALID_VPA": {
        "cause": "The UPI Virtual Payment Address is invalid or inactive.",
        "default_action": "Halt retries. Send outreach request for updated VPA details."
    },
    "CHECKOUT_ABANDONED": {
        "cause": "Customer exited checkout funnel before completing payment (drop-off).",
        "default_action": "Halt automated bank retries. Immediately trigger cart-rescue outreach with secure cart restoration link."
    }
}

def diagnose_failure(failure_code):
    """
    Returns the mapped taxonomy details for a specific failure code.
    """
    return TAXONOMY.get(failure_code, {
        "cause": "Unknown failure code.",
        "default_action": "Halt automated action. Escalate to manual review."
    })

def check_compliance(record, last_action_time_str=None, current_time=None):
    """
    Evaluates a transaction record against RBI/NPCI-style compliance rules.
    Returns: (is_compliant: bool, reason: str, recommended_state: str)
    """
    # 1. Consent check (Opt-Out rule)
    consent = str(record.get("consent_status", "True")).strip().lower() == "true"
    if not consent or record.get("current_state") == "ESCALATED":
        return False, "BLOCK_OPT_OUT: Customer has revoked communication consent", "ESCALATED"
        
    # 1.5. NPCI Quiet Hours check (no outreach between 8 PM and 8 AM)
    if not current_time:
        current_time = datetime.now()
    current_hour = current_time.hour
    if current_hour < 8 or current_hour >= 20:
        return False, "BLOCK_QUIET_HOURS: Outreach blocked during quiet hours (8:00 PM - 8:00 AM)", record.get("current_state")
        
    # 2. Retry limits check (RBI/NPCI Cap rule)
    try:
        retries = int(record.get("retry_count", 0))
    except ValueError:
        retries = 0
        
    if retries >= MAX_RETRIES:
        return False, f"BLOCK_RETRY_LIMIT: Maximum retry limit of {MAX_RETRIES} attempts exhausted", "EXHAUSTED"
        
    # 3. Cooling-off rules (Transient bank decline cooling-off window)
    failure_code = record.get("failure_code", "")
    
    if failure_code == "BANK_DECLINE_RISK" and last_action_time_str and retries > 0:
        if not current_time:
            current_time = datetime.now()
        try:
            last_action_time = datetime.strptime(last_action_time_str, "%Y-%m-%d %H:%M:%S")
            time_diff = current_time - last_action_time
            required_delta = timedelta(hours=COOLING_OFF_HOURS)
            
            if time_diff < required_delta:
                hours_left = (required_delta - time_diff).total_seconds() / 3600
                return False, f"BLOCK_COOLING_OFF: Bank decline lock active. Must wait {hours_left:.1f} more hours.", record.get("current_state")
        except ValueError:
            pass # fallback to pass if timestamp is malformed
            
    return True, "PASS: Transaction complies with all regulatory limits", record.get("current_state")

def transition_state(record, event_type, details=None):
    """
    Processes state transitions inside our state machine.
    Modifies the record dictionary in-place.
    """
    current_state = record.get("current_state", "PENDING")
    
    # Force opt-out overrides
    if event_type == "OPT_OUT":
        record["consent_status"] = "False"
        record["current_state"] = "ESCALATED"
        return
        
    if event_type == "PAYMENT_SUCCESS":
        record["current_state"] = "RECOVERED"
        return
        
    # Standard states transition
    if current_state == "PENDING":
        if event_type == "OUTBOUND_NUDGE":
            record["current_state"] = "ENGAGEMENT_STARTED"
            
    elif current_state == "ENGAGEMENT_STARTED":
        if event_type == "PROMISE_TO_PAY":
            record["current_state"] = "PROMISE_TO_PAY"
            # Note: PTP transition does NOT increment retry count
        elif event_type == "SEND_PAYMENT_LINK":
            record["current_state"] = "LINK_GENERATED"
        elif event_type == "MOCK_PAYMENT_ATTEMPT":
            record["retry_count"] = int(record.get("retry_count", 0)) + 1
            if details and details.get("success"):
                record["current_state"] = "RECOVERED"
            else:
                if int(record["retry_count"]) >= MAX_RETRIES:
                    record["current_state"] = "EXHAUSTED"
            
    elif current_state == "PROMISE_TO_PAY":
        if event_type == "MOCK_PAYMENT_ATTEMPT":
            # Consuming a retry attempt on execution
            record["retry_count"] = int(record.get("retry_count", 0)) + 1
            if details and details.get("success"):
                record["current_state"] = "RECOVERED"
            else:
                # If failure is persistent and limits met
                if int(record["retry_count"]) >= MAX_RETRIES:
                    record["current_state"] = "EXHAUSTED"
                else:
                    record["current_state"] = "ENGAGEMENT_STARTED" # restart nudge loop
                    
    elif current_state == "LINK_GENERATED":
        if event_type == "MOCK_PAYMENT_ATTEMPT":
            record["retry_count"] = int(record.get("retry_count", 0)) + 1
            if details and details.get("success"):
                record["current_state"] = "RECOVERED"
            else:
                if int(record["retry_count"]) >= MAX_RETRIES:
                    record["current_state"] = "EXHAUSTED"
                else:
                    record["current_state"] = "ENGAGEMENT_STARTED"
                    
    # Ensure transition to EXHAUSTED if max retries reached at any point
    if int(record.get("retry_count", 0)) >= MAX_RETRIES and record["current_state"] not in ["RECOVERED", "ESCALATED"]:
        record["current_state"] = "EXHAUSTED"

def audit_compliance_ledger(df_ledger):
    """
    Scans the ledger event dataframe to compute actual compliance violations.
    Returns: dict of violation counts
    """
    violations = {
        "retry_cap_violations": 0,
        "cooling_off_violations": 0,
        "opt_out_violations": 0,
        "quiet_hours_violations": 0
    }
    
    if df_ledger.empty:
        return violations
        
    # Group by transaction_id to trace sequence
    for pay_id, group in df_ledger.groupby("payment_id"):
        # Ensure chronological order
        group_sorted = group.sort_values("timestamp")
        
        opt_out_active = False
        last_payment_time = None
        
        for _, row in group_sorted.iterrows():
            event = str(row["event_type"])
            retry_count = int(row["retry_count"])
            timestamp_str = str(row["timestamp"])
            
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
                
            # 1. Opt-out violation check
            if opt_out_active and "OUTBOUND_NUDGE" in event:
                violations["opt_out_violations"] += 1
            if row["resulting_state"] == "ESCALATED":
                opt_out_active = True
                
            # 2. Retry cap violation check
            if event == "MOCK_PAYMENT_ATTEMPT" and retry_count > 3:
                violations["retry_cap_violations"] += 1
                
            # 3. Cooling-off violation check
            if event == "MOCK_PAYMENT_ATTEMPT" and row["failure_code"] == "BANK_DECLINE_RISK":
                if last_payment_time:
                    time_diff = timestamp - last_payment_time
                    if time_diff < timedelta(hours=24):
                        violations["cooling_off_violations"] += 1
                last_payment_time = timestamp
                
            # 4. Quiet hours violation check
            if "OUTBOUND_NUDGE" in event:
                if timestamp.hour < 8 or timestamp.hour >= 20:
                    violations["quiet_hours_violations"] += 1
                
    return violations

def verify_webhook_signature(payload_body, signature, secret):
    """
    Simulates Razorpay's client.utility.verify_webhook_signature helper.
    Verifies that the HMAC-SHA256 signature of the payload body matches the provided signature.
    """
    if not secret:
        return True # Default to pass if no secret configured (local dev)
    try:
        import hmac
        import hashlib
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False
