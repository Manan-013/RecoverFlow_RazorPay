import csv
import os
import random
from datetime import datetime, timedelta

# Import config paths
try:
    from config import FAILED_TRANSACTIONS_CSV, RANDOM_SEED
except ImportError:
    FAILED_TRANSACTIONS_CSV = "failed_transactions.csv"
    RANDOM_SEED = 42

def generate_synthetic_data(output_path):
    random.seed(RANDOM_SEED)
    
    # Predefined list of realistic Indian customer names
    first_names = [
        "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Suresh", "Meera", 
        "Rohan", "Deepa", "Arjun", "Kiran", "Aditya", "Pooja", "Manish", "Divya",
        "Sanjay", "Neha", "Vijay", "Swati", "Rajesh", "Kavita", "Abhishek", "Ritu",
        "Gaurav", "Nisha", "Sunil", "Aparna", "Harish", "Jyoti", "Alok", "Preeti"
    ]
    last_names = [
        "Sharma", "Verma", "Patel", "Nair", "Singh", "Joshi", "Gupta", "Rao", 
        "Kumar", "Mehta", "Reddy", "Iyer", "Choudhury", "Das", "Sen", "Pillai",
        "Mishra", "Pandey", "Saxena", "Trivedi", "Banerjee", "Bose", "Menon", "Desai"
    ]
    
    # 7 failure/drop-off codes and their target counts (including Checkout Abandonment)
    failure_distribution = {
        "INSUFFICIENT_FUNDS": 15,
        "CARD_EXPIRED": 10,
        "BANK_DECLINE_RISK": 10,
        "NETWORK_TIMEOUT": 10,
        "MANDATE_REVOKED": 10,
        "INVALID_VPA": 5,
        "CHECKOUT_ABANDONED": 10
    }
    
    # Flatten error codes to a list
    failure_codes = []
    for code, count in failure_distribution.items():
        failure_codes.extend([code] * count)
    
    # Shuffle codes to mix transaction types
    random.shuffle(failure_codes)
    
    # Base timestamp (August 2026)
    base_date = datetime(2026, 8, 1, 9, 0, 0)
    
    transactions = []
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    
    for i in range(70):
        # Generate Razorpay-style alphanumeric IDs
        pay_id = "pay_" + "".join(random.choice(chars) for _ in range(14))
        sub_id = "sub_" + "".join(random.choice(chars) for _ in range(14))
        inv_id = "inv_" + "".join(random.choice(chars) for _ in range(14))
        
        # Build customer details
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        name = f"{fname} {lname}"
        email = f"{fname.lower()}.{lname.lower()}{random.randint(10, 99)}@example.com"
        phone = f"+91{random.randint(7000000000, 9999999999)}"
        
        # Subscription values (common price tiers in INR)
        amount = random.choice([499, 999, 1499, 1999, 2999, 4999])
        
        failure_code = failure_codes[i]
        
        # Spread timestamps over the month of August
        offset_days = random.randint(0, 25)
        offset_hours = random.randint(0, 12)
        offset_minutes = random.randint(0, 59)
        tx_date = base_date + timedelta(days=offset_days, hours=offset_hours, minutes=offset_minutes)
        
        transactions.append({
            "payment_id": pay_id,
            "subscription_id": sub_id,
            "invoice_id": inv_id,
            "name": name,
            "email": email,
            "phone": phone,
            "amount": amount,
            "failure_code": failure_code,
            "retry_count": 0,
            "consent_status": "True",
            "current_state": "PENDING",
            "timestamp": tx_date.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    # Write to CSV
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "payment_id", "subscription_id", "invoice_id", "name", "email", "phone", "amount", 
            "failure_code", "retry_count", "consent_status", "current_state", "timestamp"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(transactions)
        
    print(f"Generated 70 synthetic records in {output_path}")

if __name__ == "__main__":
    generate_synthetic_data(FAILED_TRANSACTIONS_CSV)
