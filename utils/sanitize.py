# Add to otp.py imports:
from utils.sanitize import (
    clean, clean_email, clean_otp, clean_name, clean_phone,
    normalize_phone, clean_password, clean_pin, clean_reason,
    clean_purpose, VALID_PURPOSES, validate_email, validate_password,
    validate_pin, validate_name, validate_phone, validate_otp
)

# In update_profile(), change:
phone = clean_phone(data.get('phone', ''))
# TO:
phone = normalize_phone(data.get('phone', ''))
