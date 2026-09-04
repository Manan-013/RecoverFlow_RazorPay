import csv
import os
import random
import pandas as pd
from datetime import datetime, timedelta

# Import project configurations and modules
try:
    from config import (
        FAILED_TRANSACTIONS_CSV, 
        RECOVERY_LEDGER_CSV, 
        BASELINE_LEDGER_CSV, 
        RECOVERFLOW_FINAL_CSV,
        BASELINE_FINAL_CSV,
        RANDOM_SEED, 
        MAX_RETRIES,
        COOLING_OFF_HOURS
    )
    from compliance import check_compliance, transition_state, diagnose_failure, audit_compliance_ledger
    from recovery_agent import generate_outreach
except ImportError:
    FAILED_TRANSACTIONS_CSV = "failed_transactions.csv"
    RECOVERY_LEDGER_CSV = "recovery_ledger.csv"
    BASELINE_LEDGER_CSV = "baseline_ledger.csv"
    RECOVERFLOW_FINAL_CSV = "recoverflow_final_states.csv"
    BASELINE_FINAL_CSV = "baseline_final_states.csv"
    RANDOM_SEED = 42
    MAX_RETRIES = 3
    COOLING_OFF_HOURS = 24

# Seeded stochastic probabilities as defined in the spec
STOCHASTIC_RULES = {
    "INSUFFICIENT_FUNDS": {"p_nudge1": 0.45, "p_nudge2": 0.20, "p_opt_out": 0.15},
    "CARD_EXPIRED":        {"p_nudge1": 0.35, "p_nudge2": 0.15, "p_opt_out": 0.20},
    "NETWORK_TIMEOUT":    {"p_nudge1": 0.70, "p_nudge2": 0.00, "p_opt_out": 0.05},
    "BANK_DECLINE_RISK":  {"p_nudge1": 0.25, "p_nudge2": 0.10, "p_opt_out": 0.25},
    "MANDATE_REVOKED":    {"p_nudge1": 0.15, "p_nudge2": 0.05, "p_opt_out": 0.40},
    "INVALID_VPA":       {"p_nudge1": 0.30, "p_nudge2": 0.20, "p_opt_out": 0.10},
    "CHECKOUT_ABANDONED":  {"p_nudge1": 0.55, "p_nudge2": 0.25, "p_opt_out": 0.10}
}

class LedgerLogger:
    def __init__(self):
        self.entries = []
        
    def log(self, pay_id, timestamp, event_type, failure_code, diagnosis, action, retry_count, compliance_check, reasoning, resulting_state):
        self.entries.append({
            "payment_id": pay_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "failure_code": failure_code,
            "diagnosis": diagnosis,
            "action_taken": action,
            "retry_count": retry_count,
            "compliance_check_result": compliance_check,
            "llm_reasoning": reasoning,
            "resulting_state": resulting_state
        })

    def write_to_csv(self, file_path):
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "payment_id", "timestamp", "event_type", "failure_code", "diagnosis", 
                "action_taken", "retry_count", "compliance_check_result", "llm_reasoning", "resulting_state"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.entries)

def load_transactions():
    transactions = []
    if not os.path.exists(FAILED_TRANSACTIONS_CSV):
        raise FileNotFoundError(f"Source file {FAILED_TRANSACTIONS_CSV} not found. Run generate_data.py first.")
    with open(FAILED_TRANSACTIONS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["retry_count"] = int(row["retry_count"])
            transactions.append(row)
    return transactions
def save_final_states(transactions, output_path):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "payment_id", "subscription_id", "invoice_id", "name", "email", "phone", 
            "amount", "failure_code", "retry_count", "consent_status", "current_state", "timestamp"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(transactions)

def run_baseline_engine():
    """
    Executes a naive 'single blind retry, no diagnosis' baseline strategy.
    It retries transient network/bank errors once. Other errors are ignored.
    """
    random.seed(RANDOM_SEED)
    transactions = load_transactions()
    logger = LedgerLogger()
    
    recovered_amount = 0
    total_at_risk = 0
    
    for tx in transactions:
        pay_id = tx["payment_id"]
        amount = int(tx["amount"])
        code = tx["failure_code"]
        timestamp = datetime.strptime(tx["timestamp"], "%Y-%m-%d %H:%M:%S")
        total_at_risk += amount
        
        # Log Ingestion
        logger.log(pay_id, tx["timestamp"], "INGESTION", code, "None", "Ingested failed payment record", 0, "PASS", "", "PENDING")
        
        # Transient check
        if code in ["NETWORK_TIMEOUT", "BANK_DECLINE_RISK"]:
            # Perform naive retry attempt immediately
            retry_time = timestamp + timedelta(minutes=1)
            # Roll for success (naive retry has a low 15% success rate for bank, 45% for network)
            success_chance = 0.45 if code == "NETWORK_TIMEOUT" else 0.15
            roll = random.random()
            
            if roll < success_chance:
                tx["retry_count"] = 1
                tx["current_state"] = "RECOVERED"
                recovered_amount += amount
                logger.log(
                    pay_id, retry_time.strftime("%Y-%m-%d %H:%M:%S"), "MOCK_PAYMENT_ATTEMPT", 
                    code, "Naive Retry", "Triggered automated retry on gateway", 1, "PASS", 
                    "Naive blind retry succeeded", "RECOVERED"
                )
            else:
                tx["retry_count"] = 1
                tx["current_state"] = "EXHAUSTED"
                logger.log(
                    pay_id, retry_time.strftime("%Y-%m-%d %H:%M:%S"), "MOCK_PAYMENT_ATTEMPT", 
                    code, "Naive Retry", "Triggered automated retry on gateway", 1, "PASS", 
                    "Naive blind retry failed. Giving up.", "EXHAUSTED"
                )
        else:
            # Non-transient decline. Naive baseline does not attempt recovery.
            tx["current_state"] = "EXHAUSTED"
            logger.log(
                pay_id, tx["timestamp"], "EXHAUSTED", code, "Decline Check", 
                "No retry attempted for non-transient decline code", 0, "PASS", 
                "Naive engine ignored this error class", "EXHAUSTED"
            )
            
    logger.write_to_csv(BASELINE_LEDGER_CSV)
    save_final_states(transactions, BASELINE_FINAL_CSV)
    
    recovered_count = sum(1 for t in transactions if t["current_state"] == "RECOVERED")
    return {
        "recovered_amount": recovered_amount,
        "total_at_risk": total_at_risk,
        "recovery_rate": (recovered_count / len(transactions)) * 100,
        "recovered_count": recovered_count,
        "total_count": len(transactions)
    }

def run_recoverflow_engine(api_key_override=None):
    """
    Runs the advanced RecoverFlow AI pipeline with failure diagnosis, NPCI compliant gates,
    and conversational Hinglish outreach with stochastic customer responses.
    """
    # Force offline Mock Mode for batch simulation to prevent API rate limits and network delays
    api_key_override = None
    random.seed(RANDOM_SEED)
    transactions = load_transactions()
    logger = LedgerLogger()
    
    recovered_amount = 0
    total_at_risk = 0
    compliance_violations = 0
    
    for tx in transactions:
        pay_id = tx["payment_id"]
        name = tx["name"]
        amount = int(tx["amount"])
        code = tx["failure_code"]
        total_at_risk += amount
        
        # Parse failure taxonomy
        diag = diagnose_failure(code)
        diagnosis_str = f"Cause: {diag['cause']} | Plan: {diag['default_action']}"
        
        # Log Ingestion & Diagnosis
        tx["current_state"] = "PENDING"
        curr_time = datetime.strptime(tx["timestamp"], "%Y-%m-%d %H:%M:%S")
        logger.log(
            pay_id, curr_time.strftime("%Y-%m-%d %H:%M:%S"), "INGESTION", code, 
            diagnosis_str, "Ingested and diagnosed failed record", tx["retry_count"], 
            "PASS", "Diagnostic Engine parsed failure code", "PENDING"
        )
        
        # Get stochastic probabilities
        probs = STOCHASTIC_RULES.get(code, {"p_nudge1": 0.3, "p_nudge2": 0.1, "p_opt_out": 0.1})
        
        nudge_count = 0
        last_action_time = curr_time
        last_payment_attempt_time = curr_time
        loop_guard = 0
        
        # Core agentic recovery loop (max 3 conversations/nudge steps)
        while tx["current_state"] not in ["RECOVERED", "EXHAUSTED", "ESCALATED"] and loop_guard < 10:
            loop_guard += 1
            
            # Determine proposed outreach time (scheduled 2-6 hours after last action)
            proposed_outreach_time = last_action_time + timedelta(hours=random.randint(2, 6))
            
            # Evaluate compliance check AT the proposed outreach time
            last_time_str = last_payment_attempt_time.strftime("%Y-%m-%d %H:%M:%S") if tx["retry_count"] > 0 else None
            is_compliant, comp_reason, rec_state = check_compliance(tx, last_time_str, proposed_outreach_time)
            
            if not is_compliant:
                if "BLOCK_COOLING_OFF" in comp_reason:
                    # Soft block: advance the baseline clock by cooling off hours and reschedule
                    last_action_time += timedelta(hours=COOLING_OFF_HOURS)
                    continue
                elif "BLOCK_QUIET_HOURS" in comp_reason:
                    # Soft block: advance the baseline clock to 8:00 AM and reschedule
                    if proposed_outreach_time.hour >= 20:
                        target_day = proposed_outreach_time + timedelta(days=1)
                        last_action_time = datetime(target_day.year, target_day.month, target_day.day, 8, 0, 0)
                    else:
                        last_action_time = datetime(proposed_outreach_time.year, proposed_outreach_time.month, proposed_outreach_time.day, 8, 0, 0)
                    continue
                else:
                    # Hard block (Opt-Out or Retry Limit exceeded) -> transition state to recommended terminal state
                    tx["current_state"] = rec_state
                    logger.log(
                        pay_id, proposed_outreach_time.strftime("%Y-%m-%d %H:%M:%S"), "COMPLIANCE_BLOCKED", 
                        code, diagnosis_str, f"Action blocked: {comp_reason}", tx["retry_count"], 
                        "BLOCK", f"Compliance Gate rejected next action. Shifting state to {rec_state}.", rec_state
                    )
                    if "violation" in comp_reason.lower():
                        compliance_violations += 1
                    break
                
            # If we've hit max retries, mark as exhausted and end
            if tx["retry_count"] >= MAX_RETRIES:
                tx["current_state"] = "EXHAUSTED"
                logger.log(
                    pay_id, proposed_outreach_time.strftime("%Y-%m-%d %H:%M:%S"), "EXHAUSTED",
                    code, diagnosis_str, "Terminating: retry limit reached", tx["retry_count"],
                    "PASS", "Cap logic enforced", "EXHAUSTED"
                )
                break
                
            # If we pass compliance checks, proposed_outreach_time becomes our actual outreach_time
            outreach_time = proposed_outreach_time
            
            # Generate AI outreach template
            payment_link = f"https://rzp.io/i/mock_pay_{pay_id}"
            outreach = generate_outreach(name, amount, code, payment_link, api_key_override, is_followup=(nudge_count > 0))
            
            nudge_count += 1
            transition_state(tx, "OUTBOUND_NUDGE")
            
            logger.log(
                pay_id, outreach_time.strftime("%Y-%m-%d %H:%M:%S"), f"OUTBOUND_NUDGE_{nudge_count}", 
                code, diagnosis_str, f"Sent nudge #{nudge_count} ({outreach['tone']})", tx["retry_count"], 
                "PASS", f"AI Decision: {outreach['reasoning']}", tx["current_state"]
            )
            
            # 2. Simulate Customer Response (Seeded Random Roll)
            response_time = outreach_time + timedelta(minutes=random.randint(15, 120))
            roll = random.random()
            
            # Evaluate outcomes
            p_pay = probs["p_nudge1"] if nudge_count == 1 else probs["p_nudge2"]
            p_opt = probs["p_opt_out"]
            
            if roll < p_pay:
                # Customer responds positively -> executes payment
                payment_time = response_time + timedelta(minutes=5)
                transition_state(tx, "MOCK_PAYMENT_ATTEMPT", {"success": True})
                recovered_amount += amount
                
                logger.log(
                    pay_id, payment_time.strftime("%Y-%m-%d %H:%M:%S"), "MOCK_PAYMENT_ATTEMPT", 
                    code, diagnosis_str, "Processed payment authorization via link", tx["retry_count"], 
                    "PASS", "Customer clicked payment link and authorized transaction. Success.", "RECOVERED"
                )
                
            elif roll < (p_pay + p_opt):
                # Customer opts out (demands stoppage)
                transition_state(tx, "OPT_OUT")
                logger.log(
                    pay_id, response_time.strftime("%Y-%m-%d %H:%M:%S"), "CUSTOMER_REPLY", 
                    code, diagnosis_str, "Customer replied: 'Stop messages / Unsubscribe'", tx["retry_count"], 
                    "PASS", "User revoked consent. Immediate stop rule active.", "ESCALATED"
                )
                
            else:
                # Customer responds with an objection (e.g. Promise to pay or transient delay)
                # Roll again: 40% chance of Promise to Pay if balance-related, else no response
                ptp_roll = random.random()
                if ptp_roll < 0.40 and code in ["INSUFFICIENT_FUNDS", "BANK_DECLINE_RISK"]:
                    transition_state(tx, "PROMISE_TO_PAY")
                    ptp_date = response_time + timedelta(days=2) # schedule 48h later
                    
                    logger.log(
                        pay_id, response_time.strftime("%Y-%m-%d %H:%M:%S"), "CUSTOMER_REPLY", 
                        code, diagnosis_str, f"Customer promised to pay on {ptp_date.strftime('%Y-%m-%d')}", tx["retry_count"], 
                        "PASS", "Customer promised payment on salary day. Paused retries and rescheduled.", "PROMISE_TO_PAY"
                    )
                    
                    # Execute retry on the scheduled promised date (consumes 1 retry slot)
                    execution_time = ptp_date + timedelta(hours=9) # retry morning of promised date
                    
                    # 75% chance the promised payment retry succeeds (since customer funds updated)
                    ptp_success_roll = random.random()
                    if ptp_success_roll < 0.75:
                        transition_state(tx, "MOCK_PAYMENT_ATTEMPT", {"success": True})
                        recovered_amount += amount
                        
                        logger.log(
                            pay_id, execution_time.strftime("%Y-%m-%d %H:%M:%S"), "MOCK_PAYMENT_ATTEMPT", 
                            code, diagnosis_str, "Retried payment execution on promised date", tx["retry_count"], 
                            "PASS", "Scheduled Promise-to-Pay retry executed. Success.", "RECOVERED"
                        )
                    else:
                        transition_state(tx, "MOCK_PAYMENT_ATTEMPT", {"success": False})
                        last_payment_attempt_time = execution_time
                        logger.log(
                            pay_id, execution_time.strftime("%Y-%m-%d %H:%M:%S"), "MOCK_PAYMENT_ATTEMPT", 
                            code, diagnosis_str, "Retried payment execution on promised date", tx["retry_count"], 
                            "PASS", "Scheduled Promise-to-Pay retry executed. Failed.", tx["current_state"]
                        )
                        last_action_time = execution_time
                else:
                    # No response / Silent ignore
                    logger.log(
                        pay_id, response_time.strftime("%Y-%m-%d %H:%M:%S"), "NO_RESPONSE", 
                        code, diagnosis_str, "No reply detected from customer within window", tx["retry_count"], 
                        "PASS", f"Nudge #{nudge_count} ignored by customer", tx["current_state"]
                    )
                    # If this was nudge 2 and we haven't recovered, force a compliance gate trigger or automated retry if allowed
                    if nudge_count >= 2:
                        # Attempt one final blind gateway retry before exhausting
                        retry_attempt_time = response_time + timedelta(hours=24)
                        transition_state(tx, "MOCK_PAYMENT_ATTEMPT", {"success": False}) # failed retry
                        last_payment_attempt_time = retry_attempt_time
                        
                        logger.log(
                            pay_id, retry_attempt_time.strftime("%Y-%m-%d %H:%M:%S"), "MOCK_PAYMENT_ATTEMPT", 
                            code, diagnosis_str, "Automated retry triggered (final attempt)", tx["retry_count"], 
                            "PASS", "Automated system retry failed. Retry limit reached.", tx["current_state"]
                        )
                        last_action_time = retry_attempt_time
                    else:
                        last_action_time = response_time
                        
            # Prevent infinite loop safety check
            if nudge_count >= 3 and tx["current_state"] not in ["RECOVERED", "ESCALATED"]:
                tx["current_state"] = "EXHAUSTED"
                logger.log(
                    pay_id, last_action_time.strftime("%Y-%m-%d %H:%M:%S"), "EXHAUSTED", 
                    code, diagnosis_str, "Loop safety limit reached", tx["retry_count"], 
                    "PASS", "Max communication cycle reached without customer payment.", "EXHAUSTED"
                )
                
    logger.write_to_csv(RECOVERY_LEDGER_CSV)
    save_final_states(transactions, RECOVERFLOW_FINAL_CSV)
    
    # Self-check guard
    for tx in transactions:
        if tx["current_state"] not in ["RECOVERED", "ESCALATED", "EXHAUSTED"]:
            print(f"[WARNING] Transaction {tx['payment_id']} left in non-terminal state: {tx['current_state']}")
            
    # Compute actual compliance violations from ledger
    df_ledger = pd.DataFrame(logger.entries)
    violations = audit_compliance_ledger(df_ledger)
    compliance_violations = sum(violations.values())
    
    recovered_count = sum(1 for t in transactions if t["current_state"] == "RECOVERED")
    escalated_count = sum(1 for t in transactions if t["current_state"] == "ESCALATED")
    exhausted_count = sum(1 for t in transactions if t["current_state"] == "EXHAUSTED")
    
    return {
        "recovered_amount": recovered_amount,
        "total_at_risk": total_at_risk,
        "recovery_rate": (recovered_count / len(transactions)) * 100,
        "recovered_count": recovered_count,
        "escalated_count": escalated_count,
        "exhausted_count": exhausted_count,
        "total_count": len(transactions),
        "compliance_violations": compliance_violations
    }

if __name__ == "__main__":
    print("Running Baseline Engine...")
    base_res = run_baseline_engine()
    print(f"Baseline Done! Recovery Rate: {base_res['recovery_rate']:.2f}% | Amount: INR {base_res['recovered_amount']}")
    
    print("\nRunning RecoverFlow Engine (Mock Mode)...")
    flow_res = run_recoverflow_engine()
    print(f"RecoverFlow Done! Recovery Rate: {flow_res['recovery_rate']:.2f}% | Amount: INR {flow_res['recovered_amount']}")
    print(f"Lift over Baseline: +{flow_res['recovery_rate'] - base_res['recovery_rate']:.2f}%")
    print(f"Compliance Violations: {flow_res['compliance_violations']}")
