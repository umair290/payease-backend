import re
import html

# ─────────────────────────────────────────────
# PAYEASE INPUT SANITIZATION UTILITIES
# ─────────────────────────────────────────────

# ── Strip dangerous characters from any string ──
def clean(value, max_length=255):
    """
    Core sanitizer — applies to ALL text inputs.
    - Strips null bytes (injection attacks)
    - Strips HTML/JS tags (XSS)
    - Collapses excess whitespace
    - Enforces max length
    """
    if value is None:
        return ''
    value = str(value)
    value = value.replace('\x00', '')                          # null bytes
    value = re.sub(r'<[^>]+>', '', value)                      # strip HTML tags
    value = re.sub(r'[^\S ]+', ' ', value)                     # collapse whitespace
    value = value.strip()
    value = value[:max_length]
    return value

# ── Name: letters, spaces, hyphens, apostrophes only ──
def clean_name(value, max_length=100):
    value = clean(value, max_length)
    # Allow: letters (any language), spaces, hyphens, apostrophes
    value = re.sub(r"[^a-zA-Z\s\-']", '', value)
    value = re.sub(r'\s+', ' ', value).strip()
    return value

# ── Email: lowercase + basic format ──
def clean_email(value):
    value = clean(value, 120).lower()
    return value

# ── Phone: digits only, strip formatting ──
def clean_phone(value):
    value = clean(value, 20)
    value = re.sub(r'[\s\-\(\)\+]', '', value)   # strip +, spaces, dashes, brackets
    return value

# ── PIN: exactly 4 digits ──
def clean_pin(value):
    value = clean(str(value), 4)
    value = re.sub(r'\D', '', value)             # digits only
    return value

# ── Password: strip null bytes + limit length only ──
def clean_password(value):
    if not value:
        return ''
    value = str(value).replace('\x00', '')
    return value[:128]

# ── Wallet number: alphanumeric only ──
def clean_wallet_number(value):
    value = clean(value, 20)
    value = re.sub(r'[^a-zA-Z0-9]', '', value)
    return value

# ── CNIC: digits only, 13 chars ──
def clean_cnic(value):
    value = clean(value, 15)
    value = re.sub(r'[\s\-]', '', value)         # strip spaces and dashes
    return value

# ── Amount: must be a positive number ──
def clean_amount(value):
    try:
        amount = float(value)
        if amount <= 0:
            return None
        # Round to 2 decimal places to prevent floating point tricks
        return round(amount, 2)
    except (TypeError, ValueError):
        return None

# ── Description/notes: general text, no HTML ──
def clean_description(value, max_length=255):
    return clean(value, max_length)

# ── OTP: digits only, 6 chars ──
def clean_otp(value):
    value = clean(str(value), 6)
    return re.sub(r'\D', '', value)

# ── Purpose field: whitelist only ──
VALID_PURPOSES = {'change_password', 'change_pin', 'update_profile', 'forgot_password'}
def clean_purpose(value):
    value = clean(value, 30)
    return value if value in VALID_PURPOSES else ''

# ── Date string: safe format check ──
def clean_date(value):
    value = clean(value, 20)
    # Allow: digits, dashes, slashes only
    return re.sub(r'[^0-9\-/]', '', value)

# ── Reason/message: general text, moderate length ──
def clean_reason(value, max_length=500):
    return clean(value, max_length)

# ─────────────────────────────────────────────
# VALIDATION HELPERS (return error string or None)
# ─────────────────────────────────────────────

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

def validate_email(email):
    if not email:
        return 'Email is required'
    if len(email) > 120:
        return 'Email is too long'
    if not EMAIL_REGEX.match(email):
        return 'Invalid email format'
    return None

def validate_password(password):
    if not password:
        return 'Password is required'
    if len(password) < 6:
        return 'Password must be at least 6 characters'
    if len(password) > 128:
        return 'Password is too long'
    return None

def validate_pin(pin):
    if not pin:
        return 'PIN is required'
    if len(pin) != 4 or not pin.isdigit():
        return 'PIN must be exactly 4 digits'
    return None

def validate_phone(phone):
    if not phone:
        return 'Phone number is required'
    if not phone.isdigit():
        return 'Phone number must contain digits only'
    if not (10 <= len(phone) <= 13):
        return 'Phone number must be 10-13 digits'
    return None

def validate_name(name):
    if not name:
        return 'Name is required'
    if len(name) < 2:
        return 'Name is too short'
    if len(name) > 100:
        return 'Name is too long'
    return None

def validate_amount(amount):
    if amount is None:
        return 'Amount is required'
    if amount <= 0:
        return 'Amount must be greater than zero'
    if amount > 50000:
        return 'Amount exceeds maximum transfer limit of PKR 50,000'
    return None

def validate_cnic(cnic):
    if not cnic:
        return 'CNIC number is required'
    if len(cnic) != 13 or not cnic.isdigit():
        return 'CNIC must be exactly 13 digits (no dashes)'
    return None

def validate_wallet_number(wallet_number):
    if not wallet_number:
        return 'Wallet number is required'
    if not re.match(r'^PK\d{10}$', wallet_number):
        return 'Invalid wallet number format'
    return None

def validate_otp(otp):
    if not otp:
        return 'OTP is required'
    if len(otp) != 6 or not otp.isdigit():
        return 'OTP must be exactly 6 digits'
    return None