import json
import os

try:
    from google import genai
    from google.genai import types
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False

# Load key from config
try:
    from config import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = ""

# Predefined high-quality fallbacks for Mock mode
# Predefined high-quality fallbacks for Mock mode - Starting message is ALWAYS in clean, professional English
MOCK_TEMPLATES = {
    "INSUFFICIENT_FUNDS": {
        "reasoning": "Balance issue detected. Professional English outreach notifying customer of auto-debit failure with multi-method payment link.",
        "tone": "Professional English",
        "script": "Hi {name}, quick update: your monthly subscription payment could not be processed due to insufficient funds. You can complete your payment via UPI (Google Pay, PhonePe), Netbanking, or another card here: {link}"
    },
    "CARD_EXPIRED": {
        "reasoning": "Hard failure. Card is expired. Informing customer directly in professional English to securely link their new card.",
        "tone": "Professional English",
        "script": "Hi {name}, our records show that your card on file for your subscription has expired. Auto-billing is temporarily paused. To continue your subscription uninterrupted, please update your card details here: {link}"
    },
    "BANK_DECLINE_RISK": {
        "reasoning": "Bank decline. Informing customer in professional English and offering an alternate payment retry link.",
        "tone": "Professional English",
        "script": "Hi {name}, your monthly subscription payment was declined by your issuing bank's security filters. You can complete the transaction securely or use an alternate payment method here: {link}"
    },
    "NETWORK_TIMEOUT": {
        "reasoning": "Transient network timeout. Reassuring customer in professional English with manual backup link.",
        "tone": "Helpful English",
        "script": "Hi {name}, we encountered a temporary network timeout trying to process your subscription charge. We are retrying automatically, but you can also complete it manually here: {link}"
    },
    "MANDATE_REVOKED": {
        "reasoning": "Mandate cancelled. Informing customer in professional English and providing instant reactivation link.",
        "tone": "Respectful English",
        "script": "Hi {name}, we received a cancellation notice for your subscription mandate. Your service will pause at the end of the billing cycle. If you wish to reactivate, you can do so here: {link}"
    },
    "INVALID_VPA": {
        "reasoning": "Wrong UPI handle. Guiding customer in professional English to verify and update UPI VPA.",
        "tone": "Polite English",
        "script": "Hi {name}, the UPI ID linked to your subscription could not be charged. Please click here to verify your UPI details or choose an alternate payment option: {link}"
    },
    "CHECKOUT_ABANDONED": {
        "reasoning": "Customer dropped off at checkout. Friendly cart recovery reminder in professional English.",
        "tone": "Professional English",
        "script": "Hi {name}, we noticed your checkout session was left incomplete. Click here to securely restore your checkout and complete your order: {link}"
    }
}

# Predefined high-quality followup fallbacks for Mock mode / API fallback
MOCK_FOLLOWUP_TEMPLATES = {
    "INSUFFICIENT_FUNDS": {
        "reasoning": "Mock mode follow-up. Customer responded with general balance query/delay.",
        "tone": "Polite Hinglish",
        "script": "Understood, {name}. Koi baat nahi, aap aaram se pay kar sakte hain. Jab aap ready ho, niche diye link par click karke direct pay kar dena: {link}"
    },
    "CARD_EXPIRED": {
        "reasoning": "Mock mode follow-up. Customer responding about expired card.",
        "tone": "Polite English",
        "script": "Got it, {name}. Please click the link to securely add your new card so we can reactivate your account: {link}"
    },
    "BANK_DECLINE_RISK": {
        "reasoning": "Mock mode follow-up. Customer responding to bank decline issue.",
        "tone": "Helpful Hinglish",
        "script": "Understood, {name}. Aap bank se baat kar sakte hain ya tab tak is alternate link se secure payment kar sakte hain: {link}"
    },
    "NETWORK_TIMEOUT": {
        "reasoning": "Mock mode follow-up. Customer responding to timeout.",
        "tone": "Polite English",
        "script": "Sorry for the network issue, {name}. Please complete the payment manually here when you can: {link}"
    },
    "MANDATE_REVOKED": {
        "reasoning": "Mock mode follow-up. Customer responding to mandate cancellation.",
        "tone": "Polite English",
        "script": "Understood. If you wish to reactivate or setup a new mandate, click here: {link}"
    },
    "INVALID_VPA": {
        "reasoning": "Mock mode follow-up. Customer responding to invalid VPA.",
        "tone": "Polite English",
        "script": "Please use this link to enter your correct UPI VPA details to clear the pending invoice: {link}"
    },
    "CHECKOUT_ABANDONED": {
        "reasoning": "Mock mode follow-up. Customer responding to abandoned checkout.",
        "tone": "Polite English",
        "script": "No problem, {name}. Click here anytime to securely complete your pending order: {link}"
    }
}

def detect_language_flavor(text):
    """
    Detects whether the customer message is:
    - 'hindi' (Devanagari script)
    - 'hinglish' (Romanized Hindi words like 'kal', 'pese', 'nahi', 'karo', 'karunga', etc.)
    - 'english' (Standard English)
    """
    if not text:
        return "english"
        
    # 1. Check for Devanagari Unicode characters (Hindi script: U+0900 to U+097F)
    for char in text:
        if '\u0900' <= char <= '\u097f':
            return "hindi"
            
    # 2. Check for Hinglish keywords/tokens (strictly non-English Romanized Hindi tokens)
    import re
    tokens = set(re.findall(r'\b[a-z]+\b', text.lower()))
    
    hinglish_markers = {
        "kal", "aane", "karunga", "karungi", "karega", "karenge",
        "kardo", "karo", "dunga", "dungi", "dena", "nahi", "nhi", "nahin", "pese",
        "paise", "paisa", "rupaye", "rupiya", "kat", "gaya", "gaye", "gayi", "mera",
        "meri", "mere", "aap", "aapka", "aapki", "aapke", "tum", "tumhara", "hum",
        "humne", "hume", "hai", "hain", "tha", "thi", "hoga", "hogi",
        "baad", "mein", "parso", "subah", "shaam", "raat", "abhi", "kuch",
        "bhai", "yaar", "kyun", "kyu", "kya", "kaise", "kisko", "kahan", "bhejo",
        "bhejna", "dekh", "dekho", "chahiye", "mat", "roko", "band", "khatam",
        "kharida", "maine", "mujhe", "mujhko", "bolo", "batao", "batana", "baat", "karao",
        "pareshan", "faltu", "bakwas", "chup", "saale", "saala", "bc", "mc", "chutiya", "chutiye",
        "harami", "nikal", "bhag", "aaram", "tangi", "kangaal", "gareeb", "garib",
        "khud", "krunga", "kr", "krte", "kare", "kripya", "dhanyawad", "namaste", "shukriya"
    }
    
    if tokens.intersection(hinglish_markers):
        return "hinglish"
        
    return "english"

def generate_contextual_fallback_reply(name, amount, failure_code, payment_link, customer_message, is_voice=False):
    """
    Comprehensive contextual recovery reply generator for offline/mock mode or API fallback.
    Strictly adapts to the customer's reply language:
    - English in -> English out (clean, professional, zero Hindi words)
    - Hinglish in -> Natural, polite Hinglish out
    - Hindi in -> Polite Hindi out
    Enforces compliance guardrails (zero links on opt-out/refusal/abuse).
    """
    msg_lower = (customer_message or "").lower().strip()
    lang = detect_language_flavor(customer_message)
    
    # 1. Profanity / Abusive Language / Cuss Words De-escalation (Hindi/English/Hinglish)
    profanity_keywords = [
        "fuck", "shit", "bitch", "bastard", "idiot", "asshole", "shut up", "get lost",
        "scamster", "chor", "thief", "bc", "mc", "bhenchod", "madarchod", "chutiya",
        "chutiye", "harami", "gandu", "kutta", "kutte", "saale", "saala", "bakwas",
        "bakwaas", "faltu", "chup kar", "chup chap", "kamine", "kamina"
    ]
    if any(k in msg_lower for k in profanity_keywords):
        if lang == "hindi":
            script = f"नमस्ते {name}, हम आपकी परेशानी समझते हैं और हुई असुविधा के लिए क्षमा चाहते हैं। आपके खाते के लिए सभी स्वचालित संदेश तुरंत रोक दिए गए हैं। आगे कोई संदेश नहीं भेजा जाएगा।"
            tone = "Polite Hindi De-escalation"
        elif lang == "hinglish":
            script = f"Hum aapki pareshani samajhte hain {name}, aur kisi bhi asuvidha ke liye maafi chahte hain. Humne aapke number ke liye saare automated messages turant band kar diye hain. Aage se koi message ya reminder nahi aayega."
            tone = "Polite Hinglish De-escalation"
        else:
            script = f"We understand your frustration, {name}, and apologize for any inconvenience. We maintain a strict respectful communication policy and have immediately stopped all automated messages for your account. No further reminders will be sent."
            tone = "Professional English De-escalation"
            
        return {
            "intent": "OPT_OUT",
            "reasoning": f"Profanity & Abuse De-escalation ({lang.capitalize()}): Detected hostile/abusive language. De-escalated respectfully with zero links.",
            "tone": tone,
            "script": script
        }

    # 2. Refusal to Pay ("pese nahi dunga", "wont pay", "nahi dena", "पैसे नहीं दूंगा")
    refusal_keywords = [
        "pese nahi dunga", "paise nahi dunga", "paisa nahi dunga", "mai nahi dunga",
        "main nahi dunga", "nahi dunga", "nahi dena", "wont pay", "won't pay",
        "will not pay", "refuse to pay", "not going to pay", "bhag yahan se", "nikal",
        "mera mood nahi hai", "nahi pay karunga", "nahi karunga", "payment nahi karunga",
        "bhool jao", "ek rupya nahi", "ek paisa nahi", "kuch nahi dunga",
        "पैसे नहीं दूंगा", "नहीं दूंगा", "नहीं देना", "पैसे नहीं", "पेमेंट नहीं करूंगा", "नहीं करूंगा"
    ]
    if any(k in msg_lower for k in refusal_keywords):
        if lang == "hindi":
            script = f"नमस्ते {name}, हम आपके निर्णय का सम्मान करते हैं। आपका लंबित भुगतान अनुरोध और सभी रिमाइंडर रद्द कर दिए गए हैं। आपका दिन शुभ हो!"
            tone = "Respectful Hindi"
        elif lang == "hinglish":
            script = f"Theek hai {name}, hum aapke decision ka samman karte hain. Aapki pending payment request aur saare reminders cancel kar diye gaye hain. Services temporarily pause ho sakti hain. Have a good day!"
            tone = "Respectful Hinglish"
        else:
            script = f"Understood, {name}. We respect your decision. Your pending payment request and all reminders have been cancelled. Please note that related account services may be paused. Have a good day!"
            tone = "Respectful English"
            
        return {
            "intent": "OPT_OUT",
            "reasoning": f"Refusal to Pay ({lang.capitalize()}): Customer explicitly refused payment. Respected choice and halted outreach with zero links.",
            "tone": tone,
            "script": script
        }

    # 3. Strict Opt-Out / DND Compliance (Zero Payment Links Allowed!)
    opt_out_keywords = [
        "stop", "unsubscribe", "dont message", "don't message", "dont send", "don't send",
        "optout", "opt-out", "halt", "no message", "no messages", "cancel", "band karo",
        "mat bhejo", "leave me alone", "don't call", "dont call", "remove me", "nahi chahiye", "block",
        "मत भेजो", "संदेश मत भेजो", "बंद करो", "रद्द करो", "मैसेज मत करो", "कॉल मत करो"
    ]
    if any(k in msg_lower for k in opt_out_keywords):
        if lang == "hindi":
            script = f"नमस्ते {name}, हमने आपका अनुरोध दर्ज कर लिया है और सभी भविष्य के रिमाइंडर रद्द कर दिए हैं। इस नंबर पर आगे कोई संदेश नहीं भेजा जाएगा। आपका दिन शुभ हो!"
            tone = "Respectful Hindi"
        elif lang == "hinglish":
            script = f"Theek hai {name}, humne aapki request note kar li hai aur future reminders cancel kar diye hain. Is number par aage se koi message nahi aayega. Have a good day!"
            tone = "Respectful Hinglish"
        else:
            script = f"Understood, {name}. We have cancelled all upcoming reminders and your pending transaction setup. No further messages will be sent to this number. Have a good day!"
            tone = "Respectful English"
            
        return {
            "intent": "OPT_OUT",
            "reasoning": f"Opt-Out Compliance ({lang.capitalize()}): Customer requested to stop messages. Terminated outreach with zero payment links.",
            "tone": tone,
            "script": script
        }

    # 4. Already Paid / Money Deducted ("paise kat gaye")
    already_paid_keywords = [
        "already paid", "already pay", "paise kat gaye", "kat gaya", "kat chuke",
        "paisa kat gaya", "deducted", "debited", "mera payment ho gaya", "ho gaya payment",
        "i paid", "already transferred", "done payment", "screenshot", "receipt hai"
    ]
    if any(k in msg_lower for k in already_paid_keywords):
        if lang == "hindi":
            script = f"सूचित करने के लिए धन्यवाद {name}। यदि आपके खाते से राशि कट चुकी है, तो बैंक सत्यापन में 15-30 मिनट का समय लग सकता है। हमने जांच शुरू कर दी है और रिमाइंडर रोक दिए हैं।"
            tone = "Reassuring Hindi"
        elif lang == "hinglish":
            script = f"Batane ke liye shukriya {name}. Agar aapke account se paise kat chuke hain, toh bank reconciliation mein 15-30 minute lag sakte hain. Humne sync check shuru kar diya hai aur reminders pause kar diye hain. Agar aapke paas UTR ya reference ID hai toh share karein."
            tone = "Reassuring Hinglish"
        else:
            script = f"Thank you for notifying us, {name}. If the amount has already been debited from your account, banks can take 15-30 minutes to reconcile. We have initiated a status sync check on our end and paused reminder messages. If you have a UTR or reference ID, reply here for instant verification."
            tone = "Reassuring English"
            
        return {
            "intent": "OTHER",
            "reasoning": f"Already Paid Claim ({lang.capitalize()}): Customer reported prior deduction. Paused reminders and initiated sync verification.",
            "tone": tone,
            "script": script
        }

    # 5. Financial Hardship / Inability to Pay ("paisa nahi hai")
    hardship_keywords = [
        "paisa nahi hai", "paise nahi hai", "no money", "broke", "job chali gayi",
        "lost my job", "kangaal", "paise khatam", "can't afford", "cant afford",
        "problem chal rahi hai", "tangi hai", "garib", "gareeb", "financial issue"
    ]
    if any(k in msg_lower for k in hardship_keywords):
        if lang == "hindi":
            link_ref = "मोबाइल पर भेजे गए सुरक्षित लिंक द्वारा" if is_voice else payment_link
            script = f"हम आपकी स्थिति समझते हैं {name}। हमने आपके सभी रिमाइंडर रोक दिए हैं ताकि आपको कोई परेशानी न हो। जब भी आप तैयार हों, आप इस सुरक्षित लिंक से ₹{amount} का भुगतान कर सकते हैं: {link_ref}"
            tone = "Empathetic Hindi"
        elif lang == "hinglish":
            link_ref = "mobile par bheje gaye secure payment link se" if is_voice else payment_link
            script = f"Hum aapki situation bilkul samajhte hain {name}. Humne aapke reminders pause kar diye hain taaki aapko pareshani na ho. Jab bhi aap comfortable hon, is secure link se pending ₹{amount} settle kar sakte hain: {link_ref}"
            tone = "Empathetic Hinglish"
        else:
            if is_voice:
                script = f"We completely understand your situation, {name}, and appreciate you informing us. We have paused all payment reminders on your account to give you breathing room. Whenever you are ready to settle the pending ₹{amount}, I have sent the link to your registered mobile number."
            else:
                script = f"We completely understand your situation, {name}, and appreciate you informing us. We have paused all payment reminders on your account to give you breathing room. Whenever you are ready to settle the pending ₹{amount}, you can access this secure link: {payment_link}"
            tone = "Empathetic English"
            
        return {
            "intent": "PROMISE_TO_PAY",
            "reasoning": f"Financial Hardship ({lang.capitalize()}): Acknowledged difficulty and granted cooling-off pause.",
            "tone": tone,
            "script": script
        }

    # 6. Promise to Pay / Delayed Payment ("kal salary aane par", "कल सुबह सैलरी")
    promise_keywords = [
        "kal", "tomorrow", "salary", "next week", "parso", "after", "time", "date",
        "shaam", "evening", "later", "baad me", "subah", "morning", "pay later",
        "pay tomorrow", "give me time", "thoda time", "kuch din", "aane par", "pay karunga", "kar dunga",
        "कल", "सैलरी", "परसों", "सुबह", "शाम", "बाद में", "पे करूंगा", "कर दूंगा", "समय दो"
    ]
    if any(k in msg_lower for k in promise_keywords):
        if lang == "hindi":
            link_ref = "मोबाइल पर भेजे गए सुरक्षित लिंक द्वारा" if is_voice else payment_link
            script = f"नोट कर लिया गया है {name}! हमने आपके रिमाइंडर रोक दिए हैं। जब भी आप तैयार हों, आप इस सुरक्षित लिंक के माध्यम से ₹{amount} का भुगतान कर सकते हैं: {link_ref}"
            tone = "Helpful Hindi"
        elif lang == "hinglish":
            link_ref = "mobile par bheje gaye secure payment link se" if is_voice else payment_link
            script = f"Bilkul {name}, humne aapka reminder pause kar diya hai! Jab aap convenient samjhein ya salary aa jaye, aap is secure link se pending ₹{amount} aaram se pay kar sakte hain: {link_ref}"
            tone = "Helpful Hinglish"
        else:
            if is_voice:
                script = f"Noted, {name}! We have paused payment reminders for you. Whenever you are ready to complete your transaction of ₹{amount}, I have sent the link to your registered mobile number."
            else:
                script = f"Noted, {name}! We have paused payment reminders for you. Whenever you are ready to complete your transaction of ₹{amount}, you can securely pay here: {payment_link}"
            tone = "Helpful English"
            
        return {
            "intent": "PROMISE_TO_PAY",
            "reasoning": f"Promise to Pay ({lang.capitalize()}): Customer specified payment delay. Reminders paused.",
            "tone": tone,
            "script": script
        }
        
    # 7. Dispute / Wrong Number / Unauthorized Transaction
    dispute_keywords = [
        "wrong person", "wrong number", "galat number", "ye mera nahi hai", "maine nahi kharida",
        "i didn't buy", "did not order", "did not buy", "fraud", "police", "consumer court",
        "fir karunga", "unauthorized", "cyber crime", "case karunga", "गलत नंबर", "मैंने नहीं खरीदा"
    ]
    if any(k in msg_lower for k in dispute_keywords):
        if lang == "hindi":
            script = f"असुविधा के लिए क्षमा चाहते हैं {name}। यदि आपने यह लेनदेन अधिकृत नहीं किया है, तो हमने इसे जांच के लिए भेज दिया है और सभी स्वचालित संदेश रोक दिए हैं।"
            tone = "Formal Apologetic Hindi"
        elif lang == "hinglish":
            script = f"Asuvidha ke liye maafi chahte hain {name}. Agar aapne yeh transaction nahi kiya hai, toh humne case dispute team ko flag kar diya hai aur automated messages turant band kar diye hain."
            tone = "Formal Apologetic Hinglish"
        else:
            script = f"We sincerely apologize for the inconvenience, {name}. If you did not authorize this transaction or received this message in error, please disregard it. We have flagged this transaction for dispute investigation and stopped all automated messages to this number."
            tone = "Formal Apologetic English"
            
        return {
            "intent": "OPT_OUT",
            "reasoning": f"Dispute & Wrong Entity ({lang.capitalize()}): Transaction disputed. Paused outreach and flagged for compliance.",
            "tone": tone,
            "script": script
        }

    # 8. Human Escalation / Customer Care Request
    human_keywords = [
        "human", "agent", "customer care", "representative", "call me", "talk to someone",
        "baat karao", "executive", "support number", "real person", "aadmi se baat", "बात कराओ", "कस्टमर केयर"
    ]
    if any(k in msg_lower for k in human_keywords):
        if lang == "hindi":
            script = f"समझ गया {name}। हमने आपका अनुरोध ग्राहक सहायता टीम को भेज दिया है। एक प्रतिनिधि जल्द ही आपसे संपर्क करेगा।"
            tone = "Helpful Hindi"
        elif lang == "hinglish":
            script = f"Theek hai {name}, humne aapki request customer support team ko escalate kar di hai. Hamare representative jald hi aapse call par connect karenge."
            tone = "Helpful Hinglish"
        else:
            script = f"Understood, {name}. I have escalated your request to our priority customer care team. A human representative will review your transaction details and connect with you shortly."
            tone = "Helpful English"
            
        return {
            "intent": "OTHER",
            "reasoning": f"Human Escalation ({lang.capitalize()}): Customer requested human agent. Escalated to support.",
            "tone": tone,
            "script": script
        }
    
    # 9. Explicit Link Request
    link_keywords = ["link", "bhejo", "send", "kahan pay", "where to pay", "लिंक", "भेजो", "भुगतान लिंक"]
    if any(k in msg_lower for k in link_keywords):
        if lang == "hindi":
            link_ref = "मोबाइल पर भेजे गए सुरक्षित लिंक द्वारा" if is_voice else payment_link
            script = f"नमस्ते {name}, ₹{amount} का भुगतान पूरा करने के लिए यह रहा आपका सुरक्षित लिंक: {link_ref}"
            tone = "Helpful Hindi"
        elif lang == "hinglish":
            link_ref = "mobile par bheje gaye secure payment link se" if is_voice else payment_link
            script = f"Hi {name}, ₹{amount} complete karne ke liye yeh raha aapka secure payment link: {link_ref}"
            tone = "Helpful Hinglish"
        else:
            if is_voice:
                script = f"Hi {name}, to complete the payment of ₹{amount}, I have sent the link to your registered mobile number."
            else:
                script = f"Hi {name}, here is your secure checkout link to complete the payment of ₹{amount}: {payment_link}"
            tone = "Helpful English"
            
        return {
            "intent": "REQUEST_PAYMENT_LINK",
            "reasoning": f"Payment Link Request ({lang.capitalize()}): Customer requested checkout link.",
            "tone": tone,
            "script": script
        }
        
    # 10. Payment Method / UPI / Alternate mode questions
    upi_keywords = ["upi", "gpay", "google pay", "phonepe", "paytm", "netbanking", "net banking", "card", "alternate", "dusra", "kisse pay", "how to pay", "options", "option"]
    if any(k in msg_lower for k in upi_keywords):
        if lang == "hindi":
            link_ref = "मोबाइल पर भेजे गए सुरक्षित लिंक द्वारा" if is_voice else payment_link
            script = f"नमस्ते {name}, जी हाँ! आप ₹{amount} का भुगतान UPI (Google Pay, PhonePe), नेटबैंकिंग या कार्ड द्वारा कर सकते हैं। इस लिंक पर जाएँ: {link_ref}"
            tone = "Helpful Hindi"
        elif lang == "hinglish":
            link_ref = "mobile par bheje gaye secure payment link se" if is_voice else payment_link
            script = f"Hi {name}, ji haan! Aap UPI (Google Pay, PhonePe, Paytm), Netbanking ya kisi doosre card se ₹{amount} pay kar sakte hain. Apna option choose karne ke liye yeh link kholein: {link_ref}"
            tone = "Helpful Hinglish"
        else:
            if is_voice:
                script = f"Hi {name}, yes! You can complete the ₹{amount} payment using UPI, Netbanking, or another active card. I have sent the link to your registered mobile number."
            else:
                script = f"Hi {name}, yes! You can complete the ₹{amount} payment using UPI (Google Pay, PhonePe, Paytm), Netbanking, or another active card. Simply open this secure checkout link to choose your preferred option: {payment_link}"
            tone = "Helpful English"
            
        return {
            "intent": "REQUEST_PAYMENT_LINK",
            "reasoning": f"Payment Methods Inquiry ({lang.capitalize()}): Guided to multi-method checkout options.",
            "tone": tone,
            "script": script
        }

    # 11. Security / Scam / Trust assurance
    trust_keywords = ["safe", "secure", "fraud", "scam", "real", "fake", "trust", "legit", "phishing"]
    if any(k in msg_lower for k in trust_keywords):
        if lang == "hindi":
            link_ref = "मोबाइल पर भेजे गए सुरक्षित लिंक द्वारा" if is_voice else payment_link
            script = f"निश्चिंत रहें {name}, यह रेज़रपे द्वारा संचालित ₹{amount} का 100% सुरक्षित और एन्क्रिप्टेड भुगतान लिंक है: {link_ref}"
            tone = "High-Trust Hindi"
        elif lang == "hinglish":
            link_ref = "mobile par bheje gaye secure payment link se" if is_voice else payment_link
            script = f"Aap bilkul nishchint rahein {name}, yeh Razorpay ka 100% official aur SSL encrypted secure link hai ₹{amount} ke transaction ke liye: {link_ref}"
            tone = "High-Trust Hinglish"
        else:
            if is_voice:
                script = f"Rest assured {name}, this is an official 128-bit SSL encrypted checkout powered directly by Razorpay for your transaction of ₹{amount}. I have sent the link to your registered mobile number."
            else:
                script = f"Rest assured {name}, this is an official 128-bit SSL encrypted checkout link powered directly by Razorpay for your transaction of ₹{amount}. You can securely complete it here: {payment_link}"
            tone = "High-Trust English"
            
        return {
            "intent": "OTHER",
            "reasoning": f"Trust & Security Assurance ({lang.capitalize()}): Addressed security hesitation with Razorpay verification.",
            "tone": tone,
            "script": script
        }

    # 12. Failure Reason / "Why did it fail?"
    why_keywords = ["why", "kyun", "kya hua", "reason", "decline", "problem", "issue", "dikkat", "fail"]
    if any(k in msg_lower for k in why_keywords):
        reasons_en = {
            "CARD_EXPIRED": "your card on file has expired and could not be billed",
            "INSUFFICIENT_FUNDS": "your bank declined the auto-debit due to insufficient funds",
            "BANK_DECLINE_RISK": "your issuing bank temporarily declined the automatic charge",
            "NETWORK_TIMEOUT": "there was a transient communication timeout with your bank",
            "MANDATE_REVOKED": "the previous mandate was cancelled or revoked",
            "INVALID_VPA": "the linked UPI VPA was reported as inactive or invalid",
            "CHECKOUT_ABANDONED": "the checkout session was not completed"
        }
        reasons_hi = {
            "CARD_EXPIRED": "aapka card expire ho chuka hai",
            "INSUFFICIENT_FUNDS": "account mein insufficient balance tha",
            "BANK_DECLINE_RISK": "bank security filters ne charge decline kar diya",
            "NETWORK_TIMEOUT": "bank server ke saath network timeout ho gaya tha",
            "MANDATE_REVOKED": "mandate cancel ho chuka tha",
            "INVALID_VPA": "UPI ID inactive ya invalid thi",
            "CHECKOUT_ABANDONED": "checkout complete nahi hua tha"
        }
        reasons_dev = {
            "CARD_EXPIRED": "आपका कार्ड समाप्त हो चुका है",
            "INSUFFICIENT_FUNDS": "खाते में पर्याप्त शेष राशि नहीं थी",
            "BANK_DECLINE_RISK": "बैंक ने लेनदेन अस्वीकार कर दिया",
            "NETWORK_TIMEOUT": "बैंक नेटवर्क में अस्थायी समस्या थी",
            "MANDATE_REVOKED": "आदेश रद्द कर दिया गया था",
            "INVALID_VPA": "UPI आईडी अमान्य थी",
            "CHECKOUT_ABANDONED": "चेकआउट पूरा नहीं हुआ था"
        }
        
        if lang == "hindi":
            link_ref = "मोबाइल पर भेजे गए सुरक्षित लिंक द्वारा" if is_voice else payment_link
            expl = reasons_dev.get(failure_code, "तकनीकी समस्या के कारण लेनदेन नहीं हो सका")
            script = f"नमस्ते {name}, ₹{amount} का भुगतान विफल हुआ क्योंकि {expl}। सेवाएं जारी रखने के लिए कृपया यहाँ क्लिक करें: {link_ref}"
            tone = "Informative Hindi"
        elif lang == "hinglish":
            link_ref = "mobile par bheje gaye secure payment link se" if is_voice else payment_link
            expl = reasons_hi.get(failure_code, "technical issue ki wajah se charge nahi ho paya")
            script = f"Hi {name}, aapka ₹{amount} ka payment isliye fail hua kyunki {expl}. Services bina rukawat continue rakhne ke liye yahan se pay karein: {link_ref}"
            tone = "Informative Hinglish"
        else:
            expl = reasons_en.get(failure_code, "your transaction could not be processed automatically")
            if is_voice:
                script = f"Hi {name}, your transaction of ₹{amount} failed because {expl}. To resolve this quickly without service interruption, I have sent the link to your registered mobile number."
            else:
                script = f"Hi {name}, your transaction of ₹{amount} failed because {expl}. To resolve this quickly without service interruption, please click here: {payment_link}"
            tone = "Informative English"
            
        return {
            "intent": "OTHER",
            "reasoning": f"Diagnostic Explanation ({lang.capitalize()}): Explained root cause of failure ({failure_code}).",
            "tone": tone,
            "script": script
        }
        
    # 13. Domain Check: Is the message actually related to billing/payment/account?
    billing_indicators = [
        "pay", "bill", "card", "bank", "subscri", "mandate", "money", "rupee", "inr", 
        "paisa", "paise", "link", "debit", "credit", "amount", "charge", "refund", "utr", 
        "invoice", "fee", "penalty", "account", "fail", "decline", "service", "shulk", "bhugtan",
        "भुगतान", "बिल", "पैसे", "रुपये", "कार्ड", "खाता", "लिंक", "शुल्क"
    ]
    is_billing = any(w in msg_lower for w in billing_indicators)
    
    if is_billing:
        # Legitimate general billing inquiry
        if lang == "hindi":
            link_ref = "मोबाइल पर भेजे गए सुरक्षित लिंक द्वारा" if is_voice else payment_link
            script = f"नमस्ते {name}, संपर्क करने के लिए धन्यवाद। अपनी सदस्यता जारी रखने और लंबित ₹{amount} का भुगतान करने के लिए इस लिंक पर जाएँ: {link_ref}"
            tone = "Polite Hindi"
        elif lang == "hinglish":
            link_ref = "mobile par bheje gaye secure payment link se" if is_voice else payment_link
            script = f"Hi {name}, contact karne ke liye shukriya. Subscription bina rukawat continue rakhne aur pending ₹{amount} clear karne ke liye is secure link par click karein: {link_ref}"
            tone = "Polite Hinglish"
        else:
            if is_voice:
                script = f"Hi {name}, thank you for your message. To ensure uninterrupted access to your subscription and clear the pending ₹{amount}, I have sent the link to your registered mobile number."
            else:
                script = f"Hi {name}, thank you for your message. To ensure uninterrupted access to your subscription and clear the pending ₹{amount}, please view and complete your payment here: {payment_link}"
            tone = "Polite English"
            
        return {
            "intent": "OTHER",
            "reasoning": f"Billing Inquiry Guidance ({lang.capitalize()}): Addressed general billing query with checkout link.",
            "tone": tone,
            "script": script
        }
    else:
        # NON-BILLING / OFF-TOPIC QUERY (e.g. "how is my dress", "how am i looking", "weather", etc.)
        # Strictly enforce Scope Guardrail with dynamic language adaptation!
        clean_msg = (customer_message or "").strip().replace('"', "'")
        if lang == "hindi":
            link_ref = "मोबाइल पर भेजे गए सुरक्षित लिंक द्वारा" if is_voice else payment_link
            script = f"नमस्ते {name}, मैं एक स्वचालित बिलिंग सहायक हूँ और केवल सदस्यता भुगतान में सहायता कर सकता हूँ। बिलिंग से इतर प्रश्नों के लिए (जैसे '{clean_msg}'), कृपया स्टोर सपोर्ट से संपर्क करें। ₹{amount} के भुगतान के लिए लिंक: {link_ref}"
            tone = "Polite Guardrail (Hindi)"
        elif lang == "hinglish":
            link_ref = "mobile par bheje gaye secure payment link se" if is_voice else payment_link
            script = f"Hi {name}, main automated billing assistant hoon aur sirf subscription billing assist kar sakta hoon. Billing ke alawa doosre queries ke liye (jaise '{clean_msg}'), please store support se contact karein. Pending ₹{amount} clear karke account reactivate karne ke liye yahan click karein: {link_ref}"
            tone = "Polite Guardrail (Hinglish)"
        else:
            if is_voice:
                script = f"Hi {name}, I am an automated billing assistant strictly helping with your subscription recovery. For queries unrelated to billing or payments (like '{clean_msg}'), please contact store support. To reactivate your account and settle the pending ₹{amount}, I have sent the link to your registered mobile number."
            else:
                script = f"Hi {name}, I am an automated billing assistant strictly helping with your subscription recovery. For queries unrelated to billing or payments (like '{clean_msg}'), please contact store support. To reactivate your account and settle the pending ₹{amount}, please update your payment details here: {payment_link}"
            tone = "Polite Guardrail (English)"
            
        return {
            "intent": "OTHER",
            "reasoning": f"Scope Guardrail ({lang.capitalize()}): Customer asked an off-topic query ('{clean_msg}'). Politely redirected to billing in {lang}.",
            "tone": tone,
            "script": script
        }




def get_best_groq_model(api_key):
    """
    Dynamically queries Groq's model list and selects the best available model.
    Falls back to Llama 3.1 8B if the list request fails or is empty.
    """
    try:
        import requests
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        res = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=3)
        if res.status_code == 200:
            models_data = res.json()
            model_ids = [m["id"] for m in models_data.get("data", [])]
            
            # Prioritized list of active text models supporting JSON mode
            priority_list = [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "meta-llama/llama-4-scout-17b-16e-instruct",
                "qwen/qwen3.6-27b",
                "qwen/qwen3-32b",
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b"
            ]
            for p_model in priority_list:
                if p_model in model_ids:
                    return p_model
            
            # Fallback 1: Any text llama model (excluding guard/moderator/audio/whisper)
            for m_id in model_ids:
                m_lower = m_id.lower()
                if "llama" in m_lower and "vision" not in m_lower and "guard" not in m_lower and "moderator" not in m_lower:
                    return m_id
            
            # Fallback 2: Any text/chat model ID (excluding non-chat ones)
            chat_models = [m for m in model_ids if not any(x in m.lower() for x in ["guard", "moderator", "whisper", "audio", "embed"])]
            if chat_models:
                return chat_models[0]
            elif model_ids:
                return model_ids[0]
    except Exception:
        pass
    return "llama-3.1-8b-instant"

_WORKING_GEMINI_MODEL = "gemini-3.6-flash"

def extract_json_from_llm(raw_text):
    """Robustly extracts JSON from raw LLM output, handling fences, preamble text, or formatting."""
    if not raw_text:
        return None
    text = str(raw_text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    import re
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
    return None

def call_fast_gemini(client, prompt):
    """
    Invokes Google GenAI with fast, active Flash models.
    Uses gemini-3.6-flash as recommended by the Google GenAI API with token budget limits for speed.
    """
    global _WORKING_GEMINI_MODEL
    candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash", "gemini-2.5-flash"]
    if _WORKING_GEMINI_MODEL in candidate_models:
        candidate_models = [_WORKING_GEMINI_MODEL] + [m for m in candidate_models if m != _WORKING_GEMINI_MODEL]

    last_err = None
    for m in candidate_models:
        try:
            cfg = types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=1024,
                temperature=0.3
            )
            try:
                cfg.thinking_config = types.ThinkingConfig(thinking_budget=0)
            except Exception:
                pass

            response = client.models.generate_content(
                model=m,
                contents=prompt,
                config=cfg
            )

            text = response.text
            if not text and hasattr(response, "candidates") and response.candidates:
                cand = response.candidates[0]
                if hasattr(cand, "content") and cand.content and hasattr(cand.content, "parts"):
                    for p in cand.content.parts:
                        if hasattr(p, "text") and p.text:
                            text = p.text
                            break
            if not text or not str(text).strip():
                raise ValueError(f"Model {m} returned empty response content.")
            _WORKING_GEMINI_MODEL = m
            return str(text).strip()
        except Exception as e:
            last_err = e
            err_msg = str(e).lower()
            if "not found" in err_msg or "404" in err_msg or "unsupported" in err_msg or "invalid_argument" in err_msg:
                continue
            raise e
    if last_err:
        raise last_err

def call_fast_gemini_multimodal(client, contents):
    """
    Invokes Google GenAI with multimodal inputs (audio + prompt).
    Uses gemini-2.5-flash / gemini-3.6-flash which natively supports audio.
    """
    global _WORKING_GEMINI_MODEL
    candidate_models = ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.5-flash"]
    if _WORKING_GEMINI_MODEL in candidate_models:
        candidate_models = [_WORKING_GEMINI_MODEL] + [m for m in candidate_models if m != _WORKING_GEMINI_MODEL]

    last_err = None
    for m in candidate_models:
        try:
            cfg = types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=1024,
                temperature=0.3
            )
            try:
                cfg.thinking_config = types.ThinkingConfig(thinking_budget=0)
            except Exception:
                pass

            response = client.models.generate_content(
                model=m,
                contents=contents,
                config=cfg
            )

            text = response.text
            if not text and hasattr(response, "candidates") and response.candidates:
                cand = response.candidates[0]
                if hasattr(cand, "content") and cand.content and hasattr(cand.content, "parts"):
                    for p in cand.content.parts:
                        if hasattr(p, "text") and p.text:
                            text = p.text
                            break
            if not text or not str(text).strip():
                raise ValueError(f"Model {m} returned empty response content.")
            _WORKING_GEMINI_MODEL = m
            return str(text).strip()
        except Exception as e:
            last_err = e
            err_msg = str(e).lower()
            if "not found" in err_msg or "404" in err_msg or "unsupported" in err_msg or "invalid_argument" in err_msg:
                continue
            raise e
    if last_err:
        raise last_err


def get_outreach_payment_link(record, rzp_key_id=None, rzp_key_secret=None):
    """
    Generates a payment link for the customer.
    If real Razorpay test keys are provided, calls the official Razorpay API to generate a live sandbox checkout link.
    Otherwise, returns a simulated mock link.
    """
    pay_id = record.get("payment_id", "pay_default")
    name = record.get("name", "Customer")
    phone = str(record.get("phone", "+919999999999"))
    email = str(record.get("email", "customer@example.com")).strip()
    amount = float(record.get("amount", 1000))
    
    # Sanitize phone number for Razorpay (must be a clean 10-digit mobile number)
    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) > 10 and (clean_phone.startswith("91") or clean_phone.startswith("0")):
        clean_phone = clean_phone[-10:]
    if not clean_phone or len(clean_phone) < 10:
        clean_phone = "9999999999" # Default fallback
    
    if rzp_key_id and rzp_key_secret:
        key_id = rzp_key_id.strip()
        key_secret = rzp_key_secret.strip()
        try:
            import razorpay
            client = razorpay.Client(auth=(key_id, key_secret))
            # Amount expected in paise
            data = {
                "amount": int(amount * 100),
                "currency": "INR",
                "accept_partial": False,
                "description": f"RecoverFlow AI Rescue Link - Ref: {pay_id}",
                "customer": {
                    "name": name,
                    "contact": clean_phone,
                    "email": email
                },
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
                "callback_url": "http://localhost:8501/?status=success",
                "callback_method": "get",
                "notes": {
                    "recovery_id": pay_id,
                    "agent": "RecoverFlow AI"
                }
            }
            response = client.payment_link.create(data)
            try:
                import streamlit as st
                st.session_state.active_payment_link_id = response["id"]
                st.session_state.active_payment_url = response["short_url"]
            except Exception:
                pass
            return response["short_url"]
        except Exception as e:
            # If creation fails (e.g. Test mode limit of 30 reached for payment_link),
            # gracefully fetch an existing active 'created' link from this Razorpay test account!
            try:
                res = client.payment_link.all({'count': 50})
                pls = res.get('payment_links', [])
                active_links = [p for p in pls if p.get('status') == 'created']
                if active_links:
                    reusable_link = active_links[0]
                    try:
                        import streamlit as st
                        st.session_state.active_payment_link_id = reusable_link["id"]
                        st.session_state.active_payment_url = reusable_link["short_url"]
                    except Exception:
                        pass
                    return reusable_link["short_url"]
            except Exception:
                pass
            
            try:
                import streamlit as st
                st.session_state.active_payment_link_id = None
                st.session_state.active_payment_url = f"https://rzp.io/i/mock_pay_{pay_id}"
            except Exception:
                pass
            return f"https://rzp.io/i/mock_pay_{pay_id}"
            
    try:
        import streamlit as st
        st.session_state.active_payment_link_id = None
        st.session_state.active_payment_url = f"https://rzp.io/i/mock_pay_{pay_id}"
    except Exception:
        pass
    return f"https://rzp.io/i/mock_pay_{pay_id}"

def generate_outreach(name, amount, failure_code, payment_link, api_key_override=None, is_followup=False, customer_message=None, preferred_lang=None, is_voice=False, is_cancellation=False):
    """
    Generates a professional, contextual outreach message supporting multiple Indian languages.
    Uses Gemini API if a key is available, else falls back to local templates.
    """
    api_key = api_key_override if api_key_override else GEMINI_API_KEY
    
    if not api_key:
        # --- MOCK MODE ---
        if is_cancellation:
            script_text = f"Understood, {name}. We have cancelled the pending transaction setup. No further messages will be sent to this number. Have a good day!"
            return {
                "reasoning": "Mock mode cancellation confirmation.",
                "tone": "Polite English",
                "script": script_text
            }
            
        if customer_message:
            fallback = generate_contextual_fallback_reply(name, amount, failure_code, payment_link, customer_message, is_voice)
            return {
                "reasoning": fallback["reasoning"] + " [Contextual Mode]",
                "tone": fallback["tone"],
                "script": fallback["script"]
            }
        elif is_followup:
            template = MOCK_FOLLOWUP_TEMPLATES.get(
                failure_code, 
                {
                    "reasoning": "Mock mode follow-up. Unknown error.",
                    "tone": "Polite English",
                    "script": f"Understood, {name}. You can complete your transaction of INR {amount} via this link whenever you are ready: {payment_link}"
                }
            )
        else:
            template = MOCK_TEMPLATES.get(
                failure_code, 
                {
                    "reasoning": "Unknown error. Defaulting to general support outreach.",
                    "tone": "Polite English",
                    "script": f"Hi {name}, your transaction of ₹{amount} could not be processed. Please complete it here: {payment_link}"
                }
            )
        # Format the template fields
        script_text = template["script"]
        if is_voice:
            script_text = script_text.replace("please click here to verify your UPI details or choose an alternate payment option: {link}", "To verify your UPI details or choose an alternate payment option, I have sent the link to your registered mobile number.")
            script_text = script_text.replace("Please click here to verify your UPI details or choose an alternate payment option: {link}", "To verify your UPI details or choose an alternate payment option, I have sent the link to your registered mobile number.")
            script_text = script_text.replace("complete it here: {link}", "complete it. I have sent the link to your registered mobile number.")
            script_text = script_text.replace("here: {link}", ". I have sent the link to your registered mobile number.")
            script_text = script_text.replace("via this link whenever you are ready: {link}", "whenever you are ready. I have sent the link to your registered mobile number.")
            script_text = script_text.replace("via this link: {link}", ". I have sent the link to your registered mobile number.")
            script_text = script_text.replace("via this link", "using the link")
            script_text = script_text.replace("{link}", "I have sent the link to your registered mobile number.")
            script_text = script_text.replace(" . ", ". ").replace("  ", " ").strip()
            
        result = {
            "reasoning": template["reasoning"] + " [Mock LLM Mode]",
            "tone": template["tone"],
            "script": script_text.format(name=name, link=payment_link)
        }
        return result

    # --- LLM MODES ---
    try:
        # Construct professional and multi-language prompt instructions
        prompt = f"""
        Generate a professional, polite, and reassuring payment recovery outreach message for customer {name}.
        Context: Failed payment of INR {amount} due to {failure_code}. Payment link: {payment_link}.
        
        INSTRUCTIONS:
        1. Empathize with the failed transaction ({failure_code}) and keep a high-trust, respectful brand voice (similar to Razorpay's tone). Do not sound overly informal.
        """
        if is_cancellation:
            prompt += f"""
        2. Outreach is a CANCELLATION/OPT-OUT confirmation: The customer has requested to cancel their order/subscription or opt out of messages. Generate a polite, respectful acknowledgment confirming that we have canceled the pending transaction setup, no further payments will be deducted, and we will stop messaging them. Do NOT include any payment links or call-to-actions to pay!"""
        else:
            prompt += f"""
        2. Do not ask for OTP, PIN, or CVV."""
        if is_voice:
            prompt += f"""
        3. Outreach Channel is VOICE CALL: Do NOT write or pronounce the actual raw HTTP/HTTPS URL '{payment_link}' or any link matching 'https://...' inside the speech script. Instead, say in the conversation: 'I have sent the link to your registered mobile number'. Keep it conversational, professional, and clear for a phone call."""
        else:
            prompt += f"""
        3. Outreach Channel is TEXT (WhatsApp/SMS): You MUST include the secure payment link: {payment_link} clearly in the message so they can click it."""
            
        prompt += """
        4. Language Handling:
           - Starting / Initial Outreach Message: The starting message MUST ALWAYS be written in 100% clean, professional, polite English. Do NOT use any Hindi or Hinglish words for the initial outreach.
        """
        
        if preferred_lang:
            prompt += f"\n           - Explicit Preference: The customer's preferred language is {preferred_lang}. Please write the message in {preferred_lang} (using either its native script or standard conversational Roman script as appropriate for WhatsApp)."
            
        if customer_message:
            prompt += f"""
           - Dynamic Language Match & Guardrail: The customer replied: "{customer_message}".
             - Language Adaptation: Detect the language of their reply. 
               - If they reply in standard English (e.g. "how is my dress", "can I pay with UPI", "don't message me"), you must respond strictly in clean, professional English. Do not use Hindi/Hinglish words.
               - If they reply in Hinglish (e.g. "kal subah salary aane par pay karunga", "pese nahi dunga", "mera paisa kat gaya"), respond in natural, polite Hinglish using Roman script.
               - If they reply in Hindi (Devanagari script or pure Hindi), respond in polite Hindi (Devanagari script).
             - Strict Scope Guardrail: If the customer's reply is unrelated to billing, subscription, payment, or their account (e.g. asking about shoes, clothes, dress, appearance, general knowledge, weather, jokes, etc.), do NOT answer or fulfill their query. Instead, politely state that you are an automated assistant only handling billing, and guide them back to resolving the transaction. (If they asked in English, explain the guardrail in English! If in Hinglish, explain in Hinglish!).
             - Directly address their query or objection politely (if it is billing-related), and guide them back to the transaction link: {payment_link}."""
            
        prompt += """
        
        Return JSON with:
        "reasoning": strategy explanation (1 sentence).
        "tone": tone description (e.g., "Professional Hinglish", "Polite Tamil").
        "script": message text.
        """
        
        if api_key.startswith("sk-") or api_key.startswith("gsk_"):
            # --- OPENAI / GROQ MODE ---
            from openai import OpenAI
            if api_key.startswith("gsk_"):
                client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=api_key
                )
                model_name = get_best_groq_model(api_key)
            else:
                client = OpenAI(api_key=api_key)
                model_name = "gpt-4o-mini"
                
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                raw_text = response.choices[0].message.content
            except Exception as json_err:
                if "json" in str(json_err).lower() or "support" in str(json_err).lower() or "format" in str(json_err).lower():
                    # Retry without response_format (Llama 3.2 support etc.)
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    raw_text = response.choices[0].message.content
                else:
                    raise json_err
        else:
            # --- GEMINI MODE (using new genai SDK with fast Flash model fallback) ---
            if not HAS_GOOGLE_GENAI:
                raise ImportError("google-genai package is not installed.")
            client = genai.Client(api_key=api_key)
            raw_text = call_fast_gemini(client, prompt)
            
        # Clean potential markdown block formatting from raw_text
        raw_text_clean = raw_text.strip()
        if raw_text_clean.startswith("```"):
            lines = raw_text_clean.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text_clean = "\n".join(lines).strip()
            
        parsed_response = json.loads(raw_text_clean)
        
        # Validation checks
        if "script" in parsed_response and "reasoning" in parsed_response:
            return parsed_response
        else:
            raise KeyError("Missing fields in LLM response JSON")
            
    except Exception as e:
        # Fallback to Mock Mode on any API failures
        if is_followup:
            template = MOCK_FOLLOWUP_TEMPLATES.get(
                failure_code,
                {
                    "reasoning": f"Fallback followup triggered due to Gemini error: {str(e)}",
                    "tone": "Polite English",
                    "script": f"Understood, {name}. You can complete your transaction of INR {amount} via this link whenever you are ready: {payment_link}"
                }
            )
        else:
            template = MOCK_TEMPLATES.get(
                failure_code, 
                {
                    "reasoning": f"Fallback triggered due to Gemini error: {str(e)}",
                    "tone": "Polite English",
                    "script": f"Hi {name}, your transaction of ₹{amount} could not be processed. Please complete it here: {payment_link}"
                }
            )
        script_out = template["script"]
        if is_voice:
            script_out = script_out.replace("please click here to verify your UPI details or choose an alternate payment option: {link}", "To verify your UPI details or choose an alternate payment option, I have sent the link to your registered mobile number.")
            script_out = script_out.replace("Please click here to verify your UPI details or choose an alternate payment option: {link}", "To verify your UPI details or choose an alternate payment option, I have sent the link to your registered mobile number.")
            script_out = script_out.replace("complete it here: {link}", "complete it. I have sent the link to your registered mobile number.")
            script_out = script_out.replace("here: {link}", ". I have sent the link to your registered mobile number.")
            script_out = script_out.replace("via this link whenever you are ready: {link}", "whenever you are ready. I have sent the link to your registered mobile number.")
            script_out = script_out.replace("via this link: {link}", ". I have sent the link to your registered mobile number.")
            script_out = script_out.replace("via this link", "using the link")
            script_out = script_out.replace("{link}", "I have sent the link to your registered mobile number.")
            script_out = script_out.replace(" . ", ". ").replace("  ", " ").strip()
            
        return {
            "reasoning": template["reasoning"] + f" [Gemini Fallback Mode: {str(e)}]",
            "tone": template["tone"],
            "script": script_out.format(name=name, link=payment_link)
        }

def classify_customer_intent(user_message, api_key_override=None):
    """
    Classifies the customer's intent from their text reply.
    Uses high-confidence fast-path keyword detection for sub-millisecond response,
    and falls back to LLM for ambiguous phrases when an API key is available.
    """
    reply_lower = user_message.lower().strip()
    
    # 1. High-confidence Opt-out / Refusal / Hostility keyword check
    opt_out_words = [
        "stop", "unsubscribe", "dont message", "don't message", "don't send", "dont send",
        "optout", "opt-out", "halt", "no message", "no messages", "cancel", "band karo",
        "mat bhejo", "leave me alone", "don't call", "dont call", "remove me", "nahi chahiye",
        "pese nahi dunga", "paise nahi dunga", "paisa nahi dunga", "mai nahi dunga",
        "nahi dunga", "nahi dena", "wont pay", "won't pay", "will not pay", "refuse to pay",
        "fuck", "chutiya", "bhenchod", "bastard", "idiot", "nikal", "bhag yahan se", "bhool jao"
    ]
    if any(w in reply_lower for w in opt_out_words):
        return {
            "intent": "OPT_OUT",
            "reasoning": "Fast-path: Customer requested cancellation, refusal to pay, or opt-out."
        }
        
    # 2. High-confidence Promise-to-Pay check (checked before general link keywords so 'kal pay karunga' is classified correctly)
    promise_words = ["kal", "tomorrow", "salary", "next week", "parso", "after", "time", "date", "shaam", "evening", "later", "baad me", "subah", "morning", "pay later"]
    if any(w in reply_lower for w in promise_words):
        return {
            "intent": "PROMISE_TO_PAY",
            "reasoning": "Fast-path: Customer promised to pay at a later time."
        }
        
    # 3. High-confidence Payment Link / UPI check
    link_words = ["link", "upi", "qr", "details", "bhugtan", "shulk", "bhejo", "send", "kahan pay", "how to pay", "pay now", "payment link"]
    if any(w in reply_lower for w in link_words):
        return {
            "intent": "REQUEST_PAYMENT_LINK",
            "reasoning": "Fast-path: Customer requested payment link or payment options."
        }
        
    fallback_intent = "OTHER"
    api_key = api_key_override if api_key_override else GEMINI_API_KEY
    if not api_key:
        return {
            "intent": fallback_intent,
            "reasoning": "General inquiry / discussion [Mock Mode]."
        }
        
    try:
        prompt = f"""
        Classify the customer message: "{user_message}".
        Options:
        - "OPT_OUT": Stop messages, cancel, spam.
        - "REQUEST_PAYMENT_LINK": How to pay, request payment link/UPI.
        - "PROMISE_TO_PAY": Pay later/tomorrow/salary day.
        - "OTHER": Questions, disputes, general text.
        Return JSON with:
        "intent": one of the 4 options above.
        "reasoning": 1-sentence classification reason.
        """
        
        if api_key.startswith("sk-") or api_key.startswith("gsk_"):
            # --- OPENAI / GROQ MODE ---
            from openai import OpenAI
            if api_key.startswith("gsk_"):
                client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=api_key
                )
                model_name = get_best_groq_model(api_key)
            else:
                client = OpenAI(api_key=api_key)
                model_name = "gpt-4o-mini"
                
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                raw_text = response.choices[0].message.content
            except Exception as json_err:
                if "json" in str(json_err).lower() or "support" in str(json_err).lower() or "format" in str(json_err).lower():
                    # Retry without response_format (Llama 3.2 support etc.)
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    raw_text = response.choices[0].message.content
                else:
                    raise json_err
        else:
            # --- GEMINI MODE (using new genai SDK with fast Flash model fallback) ---
            if not HAS_GOOGLE_GENAI:
                raise ImportError("google-genai package is not installed.")
            client = genai.Client(api_key=api_key)
            raw_text = call_fast_gemini(client, prompt)
            
        # Clean potential markdown block formatting from raw_text
        raw_text_clean = raw_text.strip()
        if raw_text_clean.startswith("```"):
            lines = raw_text_clean.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text_clean = "\n".join(lines).strip()
            
        parsed = json.loads(raw_text_clean)
        if "intent" in parsed and parsed["intent"] in ["OPT_OUT", "REQUEST_PAYMENT_LINK", "PROMISE_TO_PAY", "OTHER"]:
            return parsed
        else:
            raise ValueError("Invalid intent classified by LLM")
            
    except Exception as e:
        return {
            "intent": fallback_intent,
            "reasoning": f"LLM error: {str(e)}. Fallback to keyword matching."
        }

def process_customer_turn(name, amount, failure_code, payment_link, user_reply, api_key_override=None, preferred_lang=None, is_voice=False):
    """
    High-speed single-pass customer reply processing.
    Eliminates redundant sequential API calls by combining intent detection and outreach generation into ONE prompt,
    cutting response latency from ~6s to ~1.2s.
    """
    reply_lower = user_reply.lower().strip()
    
    api_key = api_key_override if api_key_override else GEMINI_API_KEY
    if not api_key:
        # Offline/mock mode: Hand off directly to the language-aware contextual engine
        fallback = generate_contextual_fallback_reply(name, amount, failure_code, payment_link, user_reply, is_voice)
        fallback["reasoning"] = f"[Offline Mock Engine] {fallback.get('reasoning', '')}"
        return fallback
        
    # Single-pass LLM Call: Both Intent Classification & Contextual Reply in 1 roundtrip!
    prompt = f"""
    You are RecoverFlow AI, an intelligent revenue recovery agent.
    Context: Customer {name} has a failed payment of INR {amount} ({failure_code}). Payment Link: {payment_link}.
    Channel: {"VOICE CALL (do NOT pronounce raw URL link, say 'I have sent the link to your registered mobile number')" if is_voice else "TEXT (WhatsApp/SMS, must include payment link)"}.
    Customer message: "{user_reply}"
    
    Tasks:
    1. Classify the customer's intent into EXACTLY ONE of:
       - "OPT_OUT": Wants to stop messages, unsubscribe, cancel, direct refusal to pay ("pese nahi dunga", "wont pay", "nahi dena"), hostility, or profanity/cuss words.
       - "REQUEST_PAYMENT_LINK": Asking how to pay, asking for payment link/UPI/QR/options.
       - "PROMISE_TO_PAY": Promising to pay later/tomorrow/salary date or financial hardship ("paisa nahi hai").
       - "OTHER": Questions, disputes, already paid ("paise kat gaye"), store inquiries, or general inquiries.
       
    2. Response Generation Guidelines (1-2 short sentences):
       - STRICT LANGUAGE ADAPTATION:
         The chatbot's initial greeting was in English. Now, you MUST detect the language and dialect of the customer's reply ("{user_reply}") and match it EXACTLY:
         a) If the customer replied in English (e.g. "how is my dress", "can I pay with UPI", "don't message me", "why did it fail"):
            -> Respond STRICTLY in 100% clean, professional English. Absolutely NO Hindi or Hinglish words (no 'bhai', 'ji', 'karo', etc.).
         b) If the customer replied in Hinglish (e.g. "kal subah salary aane par pay karunga", "pese nahi dunga", "mera paisa kat gaya", "mat bhejo"):
            -> Respond in natural, polite Hinglish using Roman script.
         c) If the customer replied in Hindi (Devanagari script or pure formal Hindi):
            -> Respond in polite Hindi using Devanagari script.
       - Refusal to Pay ("pese nahi dunga", "nahi dena", "won't pay"): Respect their refusal immediately. Acknowledge that the payment setup and reminders are cancelled. Do NOT argue, push, or include any payment links.
       - Profanity / Cuss Words / Abuse (Hindi/English e.g. bhenchod, chutiya, fuck, idiot): NEVER retaliate or swear back. De-escalate with extreme dignity: apologize for inconvenience, state that communications are stopped, and provide NO links.
       - Already Paid ("paise kat gaye"): Reassure them that banks take time to reconcile, confirm status check is initiated, and pause reminders.
       - Financial Hardship ("paisa nahi hai", "broke"): Show empathy, confirm reminders are paused until they are ready.
       - Wrong Number / Dispute: Apologize, confirm number will be removed and flagged.
       - Strict Scope Guardrail: If message is off-topic (merchandise, dress, shoes, weather, jokes, appearance, e.g. "how is my dress"), do NOT answer or fulfill their query! Politely state that you are an automated assistant only handling billing, and guide them back to resolving the transaction with the payment link {payment_link}. (If they asked in English, reply in English! If in Hinglish, reply in Hinglish!).
       - If OPT_OUT, confirm cancellation politely with ZERO links.
       
    Return JSON with:
    "intent": one of the 4 options above.
    "reasoning": 1 sentence describing strategic intent and response rationale.
    "tone": tone description (e.g. "Professional English", "Empathetic Hinglish", "Polite Hindi").
    "script": the response message text.
    """

    try:
        if api_key.startswith("sk-") or api_key.startswith("gsk_"):
            from openai import OpenAI
            if api_key.startswith("gsk_"):
                client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
                model_name = get_best_groq_model(api_key)
            else:
                client = OpenAI(api_key=api_key)
                model_name = "gpt-4o-mini"
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=800,
                temperature=0.3
            )
            raw_text = res.choices[0].message.content
            provider_tag = f"Live {model_name}"
        else:
            if not HAS_GOOGLE_GENAI:
                raise ImportError("google-genai package is not installed.")
            client = genai.Client(api_key=api_key)
            raw_text = call_fast_gemini(client, prompt)
            provider_tag = f"Live Gemini ({_WORKING_GEMINI_MODEL})"
            
        parsed = extract_json_from_llm(raw_text)
        if parsed and "script" in parsed and "intent" in parsed:
            parsed["reasoning"] = f"[{provider_tag}] {parsed.get('reasoning', '')}"
            return parsed
        raise KeyError(f"Missing fields or invalid JSON in LLM response: {str(raw_text)[:100]}")

    except Exception as e:
        import traceback
        print(f"[RECOVERY ERROR] Single-pass failed: {e}")
        traceback.print_exc()
        fallback = generate_contextual_fallback_reply(name, amount, failure_code, payment_link, user_reply, is_voice)
        fallback["reasoning"] = f"[Local Mock Fallback - API Error: {str(e)[:80]}] {fallback.get('reasoning', '')}"
        return fallback

def process_customer_voice_turn(name, amount, failure_code, payment_link, audio_bytes, mime_type="audio/wav", api_key_override=None):
    """
    Directly processes a spoken audio recording from the customer in Voice Call (IVR) mode.
    Natively transcribes the customer's speech, classifies intent, and generates a conversational voice reply.
    """
    api_key = api_key_override if api_key_override else GEMINI_API_KEY
    if not api_key:
        return {
            "transcript": "Spoken audio received",
            "intent": "OTHER",
            "reasoning": "Spoken audio received in offline/mock mode.",
            "tone": "Helpful English",
            "script": f"Hi {name}, I heard your voice message. To enable live speech transcription and voice AI, please enter your Gemini API key in the sidebar, or you can also type your reply below."
        }
        
    try:
        if not HAS_GOOGLE_GENAI:
            raise ImportError("google-genai package is not installed.")
            
        client = genai.Client(api_key=api_key)
        clean_mime = mime_type.split(";")[0].strip() if mime_type else "audio/wav"
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=clean_mime)
        
        prompt = f"""
        You are RecoverFlow AI on an interactive voice phone call with customer {name}.
        Context: Customer owes INR {amount} ({failure_code}). Payment Link: {payment_link}.
        Channel: VOICE CALL (IVR).
        
        Listen to the customer's spoken audio carefully.
        
        Tasks:
        1. Transcribe the customer's exact spoken words in field "transcript" (in English, Hindi, or Hinglish as spoken).
        2. Classify their intent into: "OPT_OUT", "REQUEST_PAYMENT_LINK", "PROMISE_TO_PAY", or "OTHER".
        3. Generate your spoken reply (1-2 short, natural conversational sentences suitable for a phone call):
           - Dynamic Language Match: If customer spoke in English, respond in clean English. If Hinglish, respond in polite Hinglish. If Hindi, respond in polite Hindi.
           - Voice Rule: Do NOT read raw URLs like 'https://...'. Say: "I have sent the link to your registered mobile number".
           - Refusal to Pay / Stop: Respect their refusal immediately, confirm reminders are stopped, with zero links.
           - Off-topic: State that you only handle billing, guide back to payment.
           
        Return JSON with:
        "transcript": the customer's exact spoken words.
        "intent": one of the 4 intents.
        "reasoning": 1 sentence strategic explanation.
        "tone": tone description.
        "script": the speech script to say to the customer.
        """
        
        raw_text = call_fast_gemini_multimodal(client, [audio_part, prompt])
        parsed = extract_json_from_llm(raw_text)
        if parsed and "script" in parsed:
            parsed["reasoning"] = f"[Live Gemini Voice AI] {parsed.get('reasoning', '')}"
            return parsed
        raise KeyError("Invalid JSON from voice comprehension")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "transcript": "Audio message received",
            "intent": "OTHER",
            "reasoning": f"Voice turn fallback: {str(e)[:80]}",
            "tone": "Helpful English",
            "script": f"Hi {name}, we received your voice message. To complete your transaction of ₹{amount}, I have sent the link to your registered mobile number."
        }

