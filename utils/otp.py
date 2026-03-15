import random
import string
import resend
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User
from extensions import db

otp_bp = Blueprint('otp', __name__)

# Temporary OTP storage
otp_store = {}

import os
resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, otp, purpose):
    purposes = {
        'change_password': 'Change Password',
        'change_pin': 'Change PIN',
    }
    purpose_label = purposes.get(purpose, 'Verification')

    html_body = f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
            <tr>
                <td align="center">
                    <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

                        <!-- Header -->
                        <tr>
                            <td style="background:linear-gradient(135deg,#1A73E8,#0052CC);padding:32px;text-align:center;">
                                <table cellpadding="0" cellspacing="0" style="margin:0 auto;">
                                    <tr>
                                        <td style="background:rgba(255,255,255,0.15);border-radius:14px;padding:10px 24px;">
                                            <span style="color:#fff;font-size:28px;font-weight:bold;">Pay</span>
                                            <span style="color:rgba(180,215,255,1);font-size:28px;font-weight:bold;">Ease</span>
                                        </td>
                                    </tr>
                                </table>
                                <p style="color:rgba(255,255,255,0.75);font-size:13px;margin:12px 0 0 0;letter-spacing:0.5px;">
                                    Digital Wallet & Payment Services
                                </p>
                            </td>
                        </tr>

                        <!-- Body -->
                        <tr>
                            <td style="padding:36px 40px;">
                                <h2 style="color:#1A1A2E;font-size:22px;font-weight:bold;margin:0 0 8px 0;">
                                    {purpose_label} Request
                                </h2>
                                <p style="color:#888;font-size:14px;margin:0 0 28px 0;line-height:1.6;">
                                    We received a request to {purpose_label.lower()} on your PayEase account.
                                    Use the OTP below to complete the process.
                                </p>

                                <!-- OTP Box -->
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td style="background:linear-gradient(135deg,#F0F4FF,#E8EFFF);border:2px dashed #1A73E8;border-radius:16px;padding:28px;text-align:center;">
                                            <p style="color:#888;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 12px 0;">
                                                One-Time Password (OTP)
                                            </p>
                                            <p style="color:#1A73E8;font-size:48px;font-weight:bold;letter-spacing:16px;margin:0;font-family:monospace;">
                                                {otp}
                                            </p>
                                            <div style="margin:16px auto 0;display:inline-block;background:rgba(255,68,68,0.08);border:1px solid rgba(255,68,68,0.2);border-radius:20px;padding:6px 16px;">
                                                <p style="color:#FF4444;font-size:12px;font-weight:600;margin:0;">
                                                    ⏱ Expires in 10 minutes
                                                </p>
                                            </div>
                                        </td>
                                    </tr>
                                </table>

                                <!-- Security Note -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;">
                                    <tr>
                                        <td style="background:#FFF8F0;border:1px solid #FFE0B2;border-radius:12px;padding:16px;">
                                            <p style="color:#FF8C00;font-size:12px;font-weight:700;margin:0 0 4px 0;">
                                                🔒 Security Notice
                                            </p>
                                            <p style="color:#888;font-size:12px;margin:0;line-height:1.5;">
                                                Never share this OTP with anyone. PayEase will never ask for your OTP via phone or chat.
                                                If you did not request this, please secure your account immediately.
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:20px 40px;">
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td style="text-align:center;">
                                            <p style="color:#1A73E8;font-size:14px;font-weight:bold;margin:0 0 4px 0;">
                                                Pay<span style="color:#AAB0C0;">Ease</span>
                                            </p>
                                            <p style="color:#AAB0C0;font-size:11px;margin:0;">
                                                © 2026 PayEase Digital Wallet. All rights reserved.
                                            </p>
                                            <p style="color:#AAB0C0;font-size:11px;margin:6px 0 0 0;">
                                                This is an automated email. Please do not reply.
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    '''

    resend.Emails.send({
        "from": "PayEase <onboarding@resend.dev>",
        "to": [email],
        "subject": f"PayEase - {purpose_label} OTP",
        "html": html_body,
    })


@otp_bp.route('/send', methods=['POST'])
@jwt_required()
def send_otp():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    purpose = data.get('purpose')

    if not purpose:
        return jsonify({'error': 'Purpose is required'}), 400

    otp = generate_otp()
    otp_store[f"{user_id}_{purpose}"] = {
        'otp': otp,
        'expires': datetime.utcnow() + timedelta(minutes=10)
    }

    try:
        send_otp_email(user.email, otp, purpose)
        return jsonify({
            'message': f'OTP sent to {user.email}',
            'email': user.email
        }), 200
    except Exception as e:
        return jsonify({'error': f'Failed to send OTP: {str(e)}'}), 500


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
        return jsonify({'error': 'OTP has expired. Please request a new one.'}), 400

    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP. Please try again.'}), 400

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
        return jsonify({'error': 'OTP not found. Please request a new one.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP has expired'}), 400
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
        return jsonify({'error': 'OTP not found. Please request a new one.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP has expired'}), 400
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
