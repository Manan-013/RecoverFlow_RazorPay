# RecoverFlow AI - 5-Minute Pitch Presentation Guide

This guide provides a slide structure and a slide-by-slide script for your pitch video.

---

## Slide 1: Title & The Core Problem (60 Seconds)
* **Slide Title:** RecoverFlow AI: Rescuing Failed Subscriptions Compliantly
* **Key Bullet Points:**
  - Automated subscription auto-debits (UPI Autopay, e-Mandates) fail frequently due to bank errors, expired cards, or low balances.
  - **The Dilemma:** Merchants either do nothing (leak revenue) or blindly retry charges (violating RBI caps of 3 attempts, causing customer complaints).
* **Pitch Script:**
  > *"Hi everyone, I'm Manan Ramani. Today I'm presenting RecoverFlow AI. In subscription businesses, payment failure is a silent revenue killer. Up to 15-20% of auto-debits fail. Merchants are caught in a trap: if they don't retry, they lose the customer. If they retry blindly, they violate strict RBI and e-mandate guidelines which cap attempts at 3. RecoverFlow AI bridges this gap. It detects revenue at risk, diagnoses the root cause, and executes a fully compliant recovery sequence using context-aware AI."*

---

## Slide 2: The Solution Architecture (60 Seconds)
* **Slide Title:** Bounded FSM & The Compliance Gate
* **Key Visual/Concept:**
  - **Diagnostic Engine:** Instantly parses failure codes (e.g. `BANK_DECLINE_RISK` vs `INSUFFICIENT_FUNDS`).
  - **State Machine:** Moves transactions through bounded states (`PENDING` -> `NUDGED` -> `PTP` -> `RECOVERED`/`EXHAUSTED`/`ESCALATED`).
  - **Compliance Gate:** Enforces maximum 3 retries, mandatory 24h cooling-off window on declines, and immediate stop checks on opt-out.
* **Pitch Script:**
  > *"RecoverFlow AI works in three steps. First, our Diagnostic Engine classifies the failure. A bank server timeout is handled differently from an expired card. Second, our compliance gate enforces strict stopping rules: we cap retries at 3 and wait a full 24 hours on bank decline risks. Third, we manage a state machine. When a customer tells us 'dont message', the system instantly revokes consent and escalates the record to support, ensuring complete regulatory compliance."*

---

## Slide 3: The Promise-to-Pay Advantage (60 Seconds)
* **Slide Title:** Intelligent Conversational Workflows
* **Key Bullet Points:**
  - Rescheduling a follow-up via Promise-to-Pay (PTP) does *not* consume a gateway retry slot.
  - Conversational Hinglish agents engage users naturally, offering instant UPI payment links or salary-day scheduling.
* **Pitch Script:**
  > *"A unique innovation in RecoverFlow AI is our Promise-to-Pay handler. Under auto-debit rules, you cannot repeatedly hit the bank card gateway. However, if a customer tells us 'salary will come tomorrow', we schedule a Promise-to-Pay follow-up. This scheduling does NOT count against their retry cap. We only trigger the actual card charge on the gateway on their promised date. This keeps the user compliant while dramatically increasing recovery probability."*

---

## Slide 4: Measured Business Lift (60 Seconds)
* **Slide Title:** Batch Simulation Results (+38.57% Net Lift)
* **Key Visual/Concept:**
  - Total At Risk: **INR 142,930** across a batch of 70 transactions (60 subscription failures + 10 checkout abandonments).
  - Control Group (Naive single-blind retry): **11.43% Recovery Rate** (INR 28,492 recovered).
  - Test Group (RecoverFlow AI): **50.00% Recovery Rate** (INR 71,465 recovered).
  - Net Conversion Lift: **+38.57%** with **0 Compliance Violations**.
* **Pitch Script:**
  > *"We benchmarked RecoverFlow AI against a standard 'naive retry' baseline using a deterministic simulation on a batch of 70 failed records. The results are clear. The naive engine recovered only 11.43% of transactions. RecoverFlow AI achieved a 50.00% recovery rate, generating a net lift of +38.57% and winning back an extra ₹42,973 from the same batch. Most importantly, our audit ledger verified that exactly 0 regulatory compliance violations occurred."*

---

## Slide 5: Interactive Live Demo (60 Seconds)
* **Action:** Open your browser and show Tab 3 (Interactive Sandbox).
  - **Step 1 & 2:** Select a failed record (e.g., `pay_3gyrDO1xlkxwnQr` - Amit Reddy | `CARD_EXPIRED`). Show the raw Razorpay webhook payload and click **"Verify Signature & Ingest Webhook"** (cryptographic HMAC-SHA256 verification).
  - **Conversational Outreach:** Show the empathetic, localized Hinglish message with the real Razorpay payment link.
  - **Hinglish IVR Call:** Switch to **Voice Call (IVR)** and click **"Answer Call"** — the browser will audibly speak the Hinglish script through the computer speakers!
  - **Consent Revocation:** Type *"stop"* or *"dont message"*. Show the compliance gate immediately locking conversational controls and transitioning to `ESCALATED`.
  - **Live Razorpay Checkout & Link Cancellation:** Show how clicking `🔄 Sync Payment Status` queries Razorpay's API to track attempts, auto-recovers on browser redirect, and permanently cancels the checkout link via `client.payment_link.cancel(pl_id)` after 3 failures to enforce the RBI cap.
* **Pitch Script:**
  > *"Let's see it in action on our live dashboard. In our interactive sandbox, we can ingest a real Razorpay webhook, verifying its signature with HMAC-SHA256. The AI reaches out in empathetic Hinglish. If we switch to Voice Call, it actually speaks to the customer using speech synthesis. If the customer opts out, our compliance gate immediately revokes consent and locks the chat. And with our official Razorpay API integration, if a payment fails 3 times, RecoverFlow automatically cancels the checkout link on Razorpay's servers, completely locking out further attempts. It's a complete, compliance-first revenue recovery system."*
