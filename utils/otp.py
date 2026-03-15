import random
import string
from datetime import datetime, timedelta

# Temporary storage for OTPs
# In production this would be Redis or a database
otp_store = {}


def generate_otp():
    return "".join(random.choices(string.digits, k=6))


def send_otp(phone, purpose="verification"):
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=5)

    # Store OTP with expiry
    otp_store[phone] = {
        "otp":     otp,
        "expiry":  expiry,
        "purpose": purpose,
        "used":    False
    }

    # In development we print it
    # In production this sends real SMS via Twilio
    print(f"\n{'='*40}")
    print(f"OTP for {phone}: {otp}")
    print(f"Purpose: {purpose}")
    print(f"Expires in 5 minutes")
    print(f"{'='*40}\n")

    return True


def verify_otp(phone, otp):
    record = otp_store.get(phone)

    if not record:
        return False, "OTP not found"

    if record["used"]:
        return False, "OTP already used"

    if datetime.utcnow() > record["expiry"]:
        return False, "OTP expired"

    if record["otp"] != otp:
        return False, "Invalid OTP"

    # Mark as used
    otp_store[phone]["used"] = True
    return True, "OTP verified successfully"