import os
import random
import string
import resend
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User
from extensions import db
import bcrypt

otp_bp    = Blueprint('otp', __name__)
otp_store = {}

resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL', 'support@payease.space')


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


# ──────────────────────────────────────────
# EMAIL HELPERS
# ──────────────────────────────────────────

def send_otp_email(email, otp, purpose):
    labels = {
        'change_password':  'Change Password',
        'change_pin':       'Change PIN',
        'forgot_password':  'Password Reset',
        'update_profile':   'Profile Update',
    }
    label = labels.get(purpose, 'Verification')
    now   = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')

    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

<tr><td style="background:linear-gradient(135deg,#1A73E8,#0052CC);padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;letter-spacing:-0.5px;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Digital Wallet and Payment Services</p>
</td></tr>

<tr><td style="padding:32px;">
<h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 8px 0;">{label} Request</h2>
<p style="color:#6B7280;font-size:14px;margin:0 0 24px 0;line-height:1.6;">
A {label.lower()} request was made for your PayEase account. Use the verification code below to proceed.
</p>

<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="background:#F0F4FF;border:2px dashed #1A73E8;border-radius:16px;padding:28px;text-align:center;">
<p style="color:#6B7280;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 14px 0;">Verification Code</p>
<p style="color:#1A73E8;font-size:48px;font-weight:bold;letter-spacing:14px;margin:0;font-family:monospace;">{otp}</p>
<p style="color:#DC2626;font-size:12px;font-weight:600;margin:14px 0 0 0;">Expires in 10 minutes</p>
</td></tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;">
<tr><td style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:16px;">
<p style="color:#92400E;font-size:12px;font-weight:700;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:0.5px;">Security Notice</p>
<p style="color:#78350F;font-size:13px;margin:0;line-height:1.6;">
Never share this code with anyone. PayEase will never ask for your OTP via phone or chat.
If you did not make this request, please secure your account immediately.
</p>
</td></tr>
</table>
</td></tr>

<tr><td style="background:#F9FAFB;border-top:1px solid #E5E7EB;padding:20px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#9CA3AF;font-size:11px;margin:0;">payease.space &nbsp;|&nbsp; support@payease.space</p>
<p style="color:#9CA3AF;font-size:10px;margin:6px 0 0 0;">This is an automated message. Please do not reply to this email.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''

    try:
        resend.Emails.send({
            "from":    f"PayEase <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": f"PayEase — {label} Verification Code",
            "html":    html,
        })
        return True
    except Exception as e:
        print(f"OTP email failed: {e}")
        return False


def send_confirmation_email(email, full_name, action, extra_info=''):
    """Send confirmation email after a sensitive action is completed"""
    now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')

    action_config = {
        'password_changed': {
            'title':   'Password Changed Successfully',
            'message': 'Your PayEase account password has been updated successfully.',
            'warning': 'If you did not make this change, please reset your password immediately and contact support.',
            'color':   '#1A73E8',
            'grad':    'linear-gradient(135deg,#1A73E8,#0052CC)',
        },
        'pin_changed': {
            'title':   'Transaction PIN Changed Successfully',
            'message': 'Your 4-digit transaction PIN has been updated successfully.',
            'warning': 'If you did not make this change, please change your PIN immediately and contact support.',
            'color':   '#16A34A',
            'grad':    'linear-gradient(135deg,#16A34A,#15803D)',
        },
        'profile_updated': {
            'title':   'Profile Updated Successfully',
            'message': f'Your PayEase profile information has been updated successfully.{" " + extra_info if extra_info else ""}',
            'warning': 'If you did not make this change, please contact support immediately.',
            'color':   '#7C3AED',
            'grad':    'linear-gradient(135deg,#7C3AED,#5B21B6)',
        },
        'kyc_approved': {
            'title':   'KYC Verification Approved',
            'message': 'Your identity verification has been approved. You now have full access to all PayEase features including money transfers.',
            'warning': '',
            'color':   '#16A34A',
            'grad':    'linear-gradient(135deg,#16A34A,#15803D)',
        },
        'kyc_rejected': {
            'title':   'KYC Verification Rejected',
            'message': f'Your identity verification was not approved.{" Reason: " + extra_info if extra_info else ""} Please resubmit your KYC with clear and valid documents.',
            'warning': 'If you believe this is an error, please contact our support team.',
            'color':   '#DC2626',
            'grad':    'linear-gradient(135deg,#DC2626,#B91C1C)',
        },
    }

    cfg = action_config.get(action, {
        'title':   'Account Update',
        'message': 'Your PayEase account has been updated.',
        'warning': '',
        'color':   '#1A73E8',
        'grad':    'linear-gradient(135deg,#1A73E8,#0052CC)',
    })

    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

<tr><td style="background:{cfg["grad"]};padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;letter-spacing:-0.5px;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Account Notification</p>
</td></tr>

<tr><td style="padding:32px;">
<div style="text-align:center;margin-bottom:24px;">
  <div style="width:64px;height:64px;border-radius:50%;background:{"#DCFCE7" if "approved" in action or "changed" in action or "updated" in action else "#FEE2E2"};margin:0 auto 14px auto;text-align:center;line-height:64px;font-size:28px;color:{cfg["color"]};">
    {"&#10003;" if "approved" in action or "changed" in action or "updated" in action else "&#10007;"}
  </div>
  <h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 6px 0;">{cfg["title"]}</h2>
  <p style="color:#6B7280;font-size:13px;margin:0;">Account: {full_name}</p>
</div>

<table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;border-radius:14px;overflow:hidden;border:1px solid #E5E7EB;margin-bottom:20px;">
<tr style="background:#F3F4F6;">
  <td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Activity Details</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Action</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{cfg["title"]}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Account</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{full_name}</td>
</tr>
<tr>
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Date and Time</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{now}</td>
</tr>
</table>

<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:16px;margin-bottom:{"16px" if cfg["warning"] else "0"};">
<p style="color:#15803D;font-size:13px;line-height:1.7;margin:0;">{cfg["message"]}</p>
</div>

{"<div style='background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:16px;margin-top:16px;'><p style='color:#92400E;font-size:12px;font-weight:700;margin:0 0 4px 0;text-transform:uppercase;letter-spacing:0.5px;'>Security Notice</p><p style='color:#78350F;font-size:13px;margin:0;line-height:1.6;'>" + cfg["warning"] + "</p></div>" if cfg["warning"] else ""}

</td></tr>

<tr><td style="background:#F9FAFB;border-top:1px solid #E5E7EB;padding:20px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#9CA3AF;font-size:11px;margin:0;">payease.space &nbsp;|&nbsp; support@payease.space</p>
<p style="color:#9CA3AF;font-size:10px;margin:6px 0 0 0;">This is an automated message. Please do not reply to this email.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''

    try:
        subjects = {
            'password_changed': 'Password Changed — PayEase Account Security',
            'pin_changed':      'Transaction PIN Changed — PayEase Account Security',
            'profile_updated':  'Profile Information Updated — PayEase',
            'kyc_approved':     'KYC Verification Approved — PayEase',
            'kyc_rejected':     'KYC Verification Rejected — PayEase',
        }
        resend.Emails.send({
            "from":    f"PayEase <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": subjects.get(action, 'Account Update — PayEase'),
            "html":    html,
        })
        print(f"Confirmation email sent to {email} for {action}")
        return True
    except Exception as e:
        print(f"Confirmation email failed: {e}")
        return False


# ──────────────────────────────────────────
# OTP ROUTES
# ──────────────────────────────────────────

@otp_bp.route('/send', methods=['POST'])
@jwt_required()
def send_otp():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    data    = request.get_json()
    purpose = data.get('purpose')

    if not purpose:
        return jsonify({'error': 'Purpose is required'}), 400
    if not user:
        return jsonify({'error': 'User not found'}), 404

    valid_purposes = ['change_password', 'change_pin', 'update_profile']
    if purpose not in valid_purposes:
        return jsonify({'error': 'Invalid purpose'}), 400

    otp = generate_otp()
    otp_store[f"{user_id}_{purpose}"] = {
        'otp':     otp,
        'expires': datetime.utcnow() + timedelta(minutes=10)
    }

    email_sent = send_otp_email(user.email, otp, purpose)
    return jsonify({
        'message':    'Verification code sent',
        'email':      user.email,
        'email_sent': email_sent
    }), 200


@otp_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    user_id      = get_jwt_identity()
    user         = User.query.get(user_id)
    data         = request.get_json()
    new_password = data.get('new_password')
    otp          = data.get('otp')

    if not new_password or not otp:
        return jsonify({'error': 'Password and OTP required'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    key    = f"{user_id}_change_password"
    stored = otp_store.get(key)
    if not stored:
        return jsonify({'error': 'OTP not found. Please request a new code.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP has expired. Please request a new code.'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP. Please try again.'}), 400

    del otp_store[key]
    user.password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.session.commit()

    # Send confirmation email
    try:
        send_confirmation_email(user.email, user.full_name, 'password_changed')
    except Exception as e:
        print(f"Confirmation email error: {e}")

    return jsonify({'message': 'Password changed successfully'}), 200


@otp_bp.route('/change-pin', methods=['POST'])
@jwt_required()
def change_pin():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    data    = request.get_json()
    new_pin = data.get('new_pin')
    otp     = data.get('otp')

    if not new_pin or not otp:
        return jsonify({'error': 'PIN and OTP required'}), 400
    if len(str(new_pin)) != 4 or not str(new_pin).isdigit():
        return jsonify({'error': 'PIN must be exactly 4 digits'}), 400

    key    = f"{user_id}_change_pin"
    stored = otp_store.get(key)
    if not stored:
        return jsonify({'error': 'OTP not found. Please request a new code.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP has expired. Please request a new code.'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP. Please try again.'}), 400

    del otp_store[key]
    user.pin = bcrypt.hashpw(str(new_pin).encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.session.commit()

    # Send confirmation email
    try:
        send_confirmation_email(user.email, user.full_name, 'pin_changed')
    except Exception as e:
        print(f"Confirmation email error: {e}")

    return jsonify({'message': 'PIN changed successfully'}), 200


@otp_bp.route('/update-profile', methods=['POST'])
@jwt_required()
def update_profile():
    user_id   = get_jwt_identity()
    user      = User.query.get(user_id)
    data      = request.get_json()
    otp       = data.get('otp', '').strip()
    full_name = data.get('full_name', '').strip()
    phone     = data.get('phone', '').strip()

    if not otp:
        return jsonify({'error': 'OTP is required'}), 400
    if not full_name:
        return jsonify({'error': 'Full name is required'}), 400
    if not phone:
        return jsonify({'error': 'Phone number is required'}), 400

    # Validate full name — only letters and spaces
    if not all(c.isalpha() or c.isspace() for c in full_name):
        return jsonify({'error': 'Full name must contain only letters and spaces'}), 400

    # Validate phone — digits only, 10-13 chars
    clean_phone = phone.replace(' ', '').replace('-', '')
    if not clean_phone.isdigit() or not (10 <= len(clean_phone) <= 13):
        return jsonify({'error': 'Enter a valid phone number (10-13 digits)'}), 400

    # Check phone not already taken by someone else
    existing = User.query.filter_by(phone=clean_phone).first()
    if existing and existing.id != int(user_id):
        return jsonify({'error': 'This phone number is already registered to another account'}), 409

    # Verify OTP
    key    = f"{user_id}_update_profile"
    stored = otp_store.get(key)
    if not stored:
        return jsonify({'error': 'OTP not found. Please request a new code.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP has expired. Please request a new code.'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP. Please try again.'}), 400

    del otp_store[key]

    # Save changes
    old_name  = user.full_name
    old_phone = user.phone
    user.full_name = full_name
    user.phone     = clean_phone

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    # Send confirmation email
    try:
        changes = []
        if old_name != full_name:
            changes.append(f'Name changed from "{old_name}" to "{full_name}"')
        if old_phone != clean_phone:
            changes.append(f'Phone changed from "{old_phone}" to "{clean_phone}"')
        extra = '. '.join(changes) if changes else ''
        send_confirmation_email(user.email, user.full_name, 'profile_updated', extra)
    except Exception as e:
        print(f"Confirmation email error: {e}")

    return jsonify({
        'message':   'Profile updated successfully',
        'full_name': user.full_name,
        'phone':     user.phone
    }), 200


@otp_bp.route('/forgot-password/send', methods=['POST'])
def forgot_password_send():
    data  = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'No account found with this email address'}), 404

    otp = generate_otp()
    otp_store[f"forgot_{email}"] = {
        'otp':     otp,
        'expires': datetime.utcnow() + timedelta(minutes=10)
    }

    email_sent = send_otp_email(email, otp, 'forgot_password')
    return jsonify({
        'message':    f'Verification code sent to {email}',
        'email':      email,
        'email_sent': email_sent
    }), 200


@otp_bp.route('/forgot-password/reset', methods=['POST'])
def forgot_password_reset():
    data         = request.get_json()
    email        = data.get('email', '').strip().lower()
    otp          = data.get('otp', '').strip()
    new_password = data.get('new_password', '')

    if not email or not otp or not new_password:
        return jsonify({'error': 'All fields are required'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    key    = f"forgot_{email}"
    stored = otp_store.get(key)
    if not stored:
        return jsonify({'error': 'OTP not found. Please request a new code.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP has expired. Please request a new code.'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP. Please try again.'}), 400

    del otp_store[key]

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.session.commit()

    # Send confirmation email
    try:
        send_confirmation_email(user.email, user.full_name, 'password_changed')
    except Exception as e:
        print(f"Confirmation email error: {e}")

    return jsonify({'message': 'Password reset successfully'}), 200
