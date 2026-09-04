import unittest
from datetime import datetime

# Import modules from our project
from compliance import check_compliance, transition_state, diagnose_failure

class TestRecoverFlowCompliance(unittest.TestCase):

    def setUp(self):
        # A template transaction record
        self.record = {
            "payment_id": "pay_test",
            "subscription_id": "sub_test",
            "invoice_id": "inv_test",
            "name": "Test Customer",
            "amount": 1000,
            "failure_code": "INSUFFICIENT_FUNDS",
            "retry_count": 0,
            "consent_status": "True",
            "current_state": "PENDING"
        }
        self.daytime = datetime(2026, 8, 27, 12, 0, 0) # Daylight hour (Noon)

    def test_rbi_retry_cap(self):
        """
        Verify that the compliance gate blocks outreach and retries once the count is >= 3.
        """
        self.record["retry_count"] = 3
        is_compliant, reason, state = check_compliance(self.record, current_time=self.daytime)
        
        # Must fail compliance checks
        self.assertFalse(is_compliant)
        self.assertIn("BLOCK_RETRY_LIMIT", reason)
        self.assertEqual(state, "EXHAUSTED")

    def test_opt_out_consent(self):
        """
        Verify that customer opt-out triggers immediate escalation and blocks all actions.
        """
        # Trigger customer opt-out event
        transition_state(self.record, "OPT_OUT")
        
        # Verify state machine values changed correctly
        self.assertEqual(self.record["consent_status"], "False")
        self.assertEqual(self.record["current_state"], "ESCALATED")
        
        # Verify compliance engine blocks any further retry
        is_compliant, reason, state = check_compliance(self.record, current_time=self.daytime)
        self.assertFalse(is_compliant)
        self.assertIn("BLOCK_OPT_OUT", reason)
        self.assertEqual(state, "ESCALATED")

    def test_promise_to_pay_retry_consumption(self):
        """
        Verify that scheduling a Promise-to-Pay does NOT consume a retry,
        but executing the payment retry on the promised date DOES consume it.
        """
        self.record["current_state"] = "ENGAGEMENT_STARTED"
        
        # Customer says 'will pay tomorrow' (Promise-to-Pay event)
        transition_state(self.record, "PROMISE_TO_PAY")
        
        # Assert retry count remains 0 (PTP is a communication schedule, not a payment attempt)
        self.assertEqual(self.record["current_state"], "PROMISE_TO_PAY")
        self.assertEqual(self.record["retry_count"], 0)
        
        # Now simulate executing the payment attempt on the promised date
        transition_state(self.record, "MOCK_PAYMENT_ATTEMPT", {"success": True})
        
        # Assert state transitions to recovered and retry count incremented by 1
        self.assertEqual(self.record["current_state"], "RECOVERED")
        self.assertEqual(self.record["retry_count"], 1)

    def test_full_simulation_compliance(self):
        """
        Runs the full batch recovery simulation engine and asserts that 
        audit_compliance_ledger reports exactly zero total violations.
        """
        from batch_engine import run_recoverflow_engine
        
        # Execute batch engine (forces mock mode in batch runs)
        results = run_recoverflow_engine()
        
        # We expect 0 compliance violations
        self.assertEqual(results["compliance_violations"], 0)

if __name__ == "__main__":
    unittest.main()
