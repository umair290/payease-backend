import os
import random
import string
import resend
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User
from extensions import db

resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')

otp_bp = Blueprint('otp', __name__)
otp_store = {}

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, otp, purpose):
    purposes = {
        'change_password': 'Change Password',
        'change_pin': 'Change PIN',
    }
    purpose_label = purposes.get(purpose, 'Verification')

    html_body = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

<tr><td style="background:linear-gradient(135deg,#1A73E8,#0052CC);padding:32px;text-align:center;">
<span style="color:#fff;font-size:28px;font-weight:bold;">Pay</span>
<span style="color:rgba(180,215,255,1);font-size:28px;font-weight:bold;">Ease</span>
<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:8px 0 0 0;">Digital Wallet & Payment Services</p>
</td></tr>

<tr><td style="padding:36px 40px;">
<h2 style="color:#1A1A2E;font-size:22px;font-weight:bold;margin:0 0 8px 0;">{purpose_label} Request</h2>
<p style="color:#888;font-size:14px;margin:0 0 28px 0;line-height:1.6;">
We received a request to {purpose_label.lower()} on your PayEase account.
Use the OTP below to complete the process.
</p>

<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="background:#F0F4FF;border:2px dashed #1A73E8;border-radius:16px;padding:28px;text-align:center;">
<p style="color:#888;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 12px 0;">One-Time Password</p>
<p style="color:#1A73E8;font-size:48px;font-weight:bold;letter-spacing:16px;margin:0;font-family:monospace;">{otp}</p>
<p style="color:#FF4444;font-size:12px;font-weight:600;margin:12px 0 0 0;">Expires in 10 minutes</p>
</td></tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;">
<tr><td style="background:#FFF8F0;border:1px solid #FFE0B2;border-radius:12px;padding:16px;">
<p style="color:#FF8C00;font-size:12px;font-weight:700;margin:0 0 4px 0;">Security Notice</p>
<p style="color:#888;font-size:12px;margin:0;line-height:1.5;">
Never share this OTP with anyone. PayEase will never ask for your OTP via phone or chat.
</p>
</td></tr>
</table>
</td></tr>

<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:20px 40px;text-align:center;">
<p style="color:#1A73E8;font-size:14px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">2026 PayEase Digital Wallet. All rights reserved.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''

    try:
        response = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": [email],
            "subject": f"PayEase - {purpose_label} OTP",
            "html": html_body,
        })
        print(f"Email sent successfully: {response}")
        return True
    except Exception as e:
        print(f"Email failed: {str(e)}")
        return False


@otp_bp.route('/send', methods=['POST'])
@jwt_required()
def send_otp():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    purpose = data.get('purpose')

    if not purpose:
        return jsonify({'error': 'Purpose is required'}), 400
    if not user:
        return jsonify({'error': 'User not found'}), 404

    otp = generate_otp()
    otp_store[f"{user_id}_{purpose}"] = {
        'otp': otp,
        'expires': datetime.utcnow() + timedelta(minutes=10)
    }

    email_sent = send_otp_email(user.email, otp, purpose)

    return jsonify({
        'message': 'OTP generated successfully',
        'email': user.email,
        'dev_otp': otp,
        'email_sent': email_sent
    }), 200


@otp_bp.route('/verify', methods=['POST'])
@jwt_required()
def verify_otp():
    user_id = get_jwt_identity()
    data = request.get_json()
    purpose = data.get('purpose')
    otp = data.get('otp')

    key = f"{user_id}_{purpose}"
    stored = otp_store.get(key)

    if not stored:
        return jsonify({'error': 'OTP not found. Please request a new one.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP has expired.'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP.'}), 400

    del otp_store[key]
    return jsonify({'message': 'OTP verified successfully!'}), 200


@otp_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    new_password = data.get('new_password')
    otp = data.get('otp')

    if not new_password or not otp:
        return jsonify({'error': 'New password and OTP are required'}), 400

    key = f"{user_id}_change_password"
    stored = otp_store.get(key)

    if not stored:
        return jsonify({'error': 'OTP not found.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP expired'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP'}), 400

    del otp_store[key]

    import bcrypt
    user.password_hash = bcrypt.hashpw(
        new_password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    db.session.commit()
    return jsonify({'message': 'Password changed successfully!'}), 200


@otp_bp.route('/change-pin', methods=['POST'])
@jwt_required()
def change_pin():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    new_pin = data.get('new_pin')
    otp = data.get('otp')

    if not new_pin or not otp:
        return jsonify({'error': 'New PIN and OTP are required'}), 400
    if len(str(new_pin)) != 4:
        return jsonify({'error': 'PIN must be 4 digits'}), 400

    key = f"{user_id}_change_pin"
    stored = otp_store.get(key)

    if not stored:
        return jsonify({'error': 'OTP not found.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP expired'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP'}), 400

    del otp_store[key]

    import bcrypt
    user.pin_hash = bcrypt.hashpw(
        str(new_pin).encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    db.session.commit()
    return jsonify({'message': 'PIN changed successfully!'}), 200


