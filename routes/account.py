from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db, limiter
from models import User, Wallet, Transaction
from utils.sanitize import (
    clean, clean_wallet_number, clean_description,
    clean_pin, clean_amount, clean_phone,
    validate_amount, validate_wallet_number
)
import bcrypt
import os
import re
import resend
from datetime import datetime, timedelta

account_bp = Blueprint("account", __name__)

resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL', 'support@payease.space')


# ──────────────────────────────────────────
# EMAIL FUNCTIONS
# ──────────────────────────────────────────

def send_transfer_email_to_sender(sender_user, receiver_user, amount, ref, sender_wallet, receiver_wallet_num):
    now  = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
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
<div style="text-align:center;margin-bottom:24px;">
  <div style="width:64px;height:64px;border-radius:50%;background:#DBEAFE;margin:0 auto 12px auto;text-align:center;line-height:64px;font-size:28px;color:#1A73E8;font-weight:bold;">&#10003;</div>
  <h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 4px 0;">Transfer Successful</h2>
  <p style="color:#6B7280;font-size:13px;margin:0;">Your payment has been processed successfully.</p>
</div>
<div style="background:linear-gradient(135deg,#1A73E8,#0052CC);border-radius:16px;padding:22px;text-align:center;margin-bottom:24px;">
  <p style="color:rgba(255,255,255,0.75);font-size:11px;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">Amount Transferred</p>
  <p style="color:#fff;font-size:38px;font-weight:bold;margin:0;letter-spacing:-1px;">PKR {amount:,.0f}</p>
</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;border-radius:14px;overflow:hidden;border:1px solid #E5E7EB;margin-bottom:24px;">
<tr style="background:#F3F4F6;">
  <td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Transaction Details</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Transaction ID</td>
  <td style="padding:12px 16px;font-size:12px;font-weight:700;color:#1A73E8;text-align:right;font-family:monospace;">{ref}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Sent To</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{receiver_user.full_name}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Recipient Wallet</td>
  <td style="padding:12px 16px;font-size:12px;font-weight:600;color:#111827;text-align:right;font-family:monospace;">{receiver_wallet_num}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">From Wallet</td>
  <td style="padding:12px 16px;font-size:12px;font-weight:600;color:#111827;text-align:right;font-family:monospace;">{sender_wallet}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Date and Time</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{now}</td>
</tr>
<tr>
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Status</td>
  <td style="padding:12px 16px;text-align:right;">
    <span style="background:#D1FAE5;color:#065F46;font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;text-transform:uppercase;letter-spacing:0.5px;">Completed</span>
  </td>
</tr>
</table>
<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:16px;">
<p style="color:#92400E;font-size:12px;font-weight:700;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:0.5px;">Security Notice</p>
<p style="color:#78350F;font-size:13px;margin:0;line-height:1.6;">
If you did not initiate this transfer, please change your PIN immediately and contact our support team at support@payease.space
</p>
</div>
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
            "to":      [sender_user.email],
            "subject": f"Transfer Confirmation — PKR {amount:,.0f} Sent to {receiver_user.full_name}",
            "html":    html,
        })
    except Exception as e:
        print(f"Sender email error: {e}")


def send_transfer_email_to_receiver(sender_user, receiver_user, amount, ref, sender_wallet, receiver_wallet_num):
    now  = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#16A34A,#15803D);padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;letter-spacing:-0.5px;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Digital Wallet and Payment Services</p>
</td></tr>
<tr><td style="padding:32px;">
<div style="text-align:center;margin-bottom:24px;">
  <div style="width:64px;height:64px;border-radius:50%;background:#D1FAE5;margin:0 auto 12px auto;text-align:center;line-height:64px;font-size:32px;color:#16A34A;">&#8595;</div>
  <h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 4px 0;">Payment Received</h2>
  <p style="color:#6B7280;font-size:13px;margin:0;">Funds have been credited to your PayEase wallet.</p>
</div>
<div style="background:linear-gradient(135deg,#16A34A,#15803D);border-radius:16px;padding:22px;text-align:center;margin-bottom:24px;">
  <p style="color:rgba(255,255,255,0.75);font-size:11px;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">Amount Received</p>
  <p style="color:#fff;font-size:38px;font-weight:bold;margin:0;letter-spacing:-1px;">PKR {amount:,.0f}</p>
</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;border-radius:14px;overflow:hidden;border:1px solid #E5E7EB;margin-bottom:24px;">
<tr style="background:#F3F4F6;">
  <td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Transaction Details</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Transaction ID</td>
  <td style="padding:12px 16px;font-size:12px;font-weight:700;color:#1A73E8;text-align:right;font-family:monospace;">{ref}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Received From</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{sender_user.full_name}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Sender Wallet</td>
  <td style="padding:12px 16px;font-size:12px;font-weight:600;color:#111827;text-align:right;font-family:monospace;">{sender_wallet}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Your Wallet</td>
  <td style="padding:12px 16px;font-size:12px;font-weight:600;color:#111827;text-align:right;font-family:monospace;">{receiver_wallet_num}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Date and Time</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{now}</td>
</tr>
<tr>
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Status</td>
  <td style="padding:12px 16px;text-align:right;">
    <span style="background:#D1FAE5;color:#065F46;font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;text-transform:uppercase;letter-spacing:0.5px;">Credited</span>
  </td>
</tr>
</table>
<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:16px;text-align:center;">
<p style="color:#15803D;font-size:13px;font-weight:600;margin:0 0 4px 0;">Your wallet has been updated.</p>
<p style="color:#166534;font-size:12px;margin:0;line-height:1.5;">Log in to PayEase to view your updated balance.</p>
</div>
</td></tr>
<tr><td style="background:#F9FAFB;border-top:1px solid #E5E7EB;padding:20px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#9CA3AF;font-size:11px;margin:0;">payease.space &nbsp;|&nbsp; support@payease.space</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''
    try:
        resend.Emails.send({
            "from":    f"PayEase <{SENDER_EMAIL}>",
            "to":      [receiver_user.email],
            "subject": f"Payment Received — PKR {amount:,.0f} from {sender_user.full_name}",
            "html":    html,
        })
    except Exception as e:
        print(f"Receiver email error: {e}")


def send_fraud_alert_email(email, full_name, amount, receiver_name, receiver_wallet, alert_type):
    now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    if alert_type == 'large_transfer':
        title    = 'Large Transfer Alert'
        subtitle = f'A large transfer of PKR {amount:,.0f} was made from your account'
        color    = '#DC2626'
        grad     = 'linear-gradient(135deg,#DC2626,#B91C1C)'
        subject  = f'Large Transfer Alert — PKR {amount:,.0f} — PayEase Security'
        message  = f'A transfer of <strong>PKR {amount:,.0f}</strong> was initiated from your PayEase wallet to <strong>{receiver_name}</strong> (Wallet: {receiver_wallet}).<br><br>This exceeds our large transfer threshold of PKR 25,000. If you authorized this, no action is needed. Otherwise, change your PIN and password immediately.'
    else:
        title    = 'Unusual Activity Detected'
        subtitle = 'Multiple rapid transfers detected on your account'
        color    = '#B45309'
        grad     = 'linear-gradient(135deg,#B45309,#92400E)'
        subject  = 'Unusual Activity Detected — PayEase Security Notice'
        message  = f'Multiple transfers within a short period were detected from your account. Most recent: <strong>PKR {amount:,.0f}</strong> to <strong>{receiver_name}</strong>.<br><br>If this was not you, change your PIN and password immediately and contact support@payease.space'

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:{grad};padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;">PayEase</p>
<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:6px 0 0 0;">Security Alert</p>
</td></tr>
<tr><td style="padding:32px;">
<div style="text-align:center;margin-bottom:24px;">
  <div style="width:64px;height:64px;border-radius:50%;background:#FEE2E2;margin:0 auto 12px auto;text-align:center;line-height:64px;font-size:28px;color:{color};">&#9888;</div>
  <h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 4px 0;">{title}</h2>
  <p style="color:#6B7280;font-size:13px;margin:0;">{subtitle}</p>
</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;border-radius:14px;overflow:hidden;border:1px solid #E5E7EB;margin-bottom:24px;">
<tr style="background:#FEF2F2;">
  <td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:0.8px;">Alert Details</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Account</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{full_name}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Amount</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:700;color:{color};text-align:right;">PKR {amount:,.0f}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Recipient</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{receiver_name}</td>
</tr>
<tr>
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Date and Time</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{now}</td>
</tr>
</table>
<div style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:12px;padding:18px;">
<p style="color:#92400E;font-size:13px;line-height:1.7;margin:0;">{message}</p>
</div>
</td></tr>
<tr><td style="background:#F9FAFB;border-top:1px solid #E5E7EB;padding:16px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#9CA3AF;font-size:11px;margin:0;">payease.space | support@payease.space</p>
</td></tr>
</table>
</td></tr>
</table>
</body></html>'''

    try:
        resend.Emails.send({
            "from":    f"PayEase Security <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": subject,
            "html":    html,
        })
    except Exception as e:
        print(f"Fraud alert email error: {e}")


# ──────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────

@account_bp.route("/balance", methods=["GET"])
@jwt_required()
def get_balance():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    wallet  = Wallet.query.filter_by(user_id=user_id).first()
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404
    return jsonify({
        "full_name":       user.full_name,
        "email":           user.email,
        "phone":           user.phone,
        "wallet_number":   wallet.wallet_number,
        "balance":         round(float(wallet.balance), 2),
        "kyc_verified":    user.kyc_verified,
        "onboarding_done": user.onboarding_done,
        "avatar_url":      user.avatar_url,
    }), 200


@account_bp.route("/deposit", methods=["POST"])
@jwt_required()
@limiter.limit("10 per hour")
def deposit():
    user_id = get_jwt_identity()
    data    = request.get_json()

    amount = clean_amount(data.get("amount"))
    if amount is None:
        return jsonify({"error": "Invalid amount"}), 400
    if amount > 500000:
        return jsonify({"error": "Deposit exceeds maximum allowed amount"}), 400

    try:
        # ── ROW LOCK ──
        wallet = Wallet.query.filter_by(
            user_id=user_id
        ).with_for_update().first()

        if not wallet:
            return jsonify({"error": "Wallet not found"}), 404

        wallet.balance += amount
        txn = Transaction(
            user_id     = user_id,
            from_wallet = None,
            to_wallet   = wallet.wallet_number,
            amount      = amount,
            type        = "deposit",
            direction   = "credit",
            description = "Deposit"
        )
        db.session.add(txn)
        db.session.commit()

        try:
            from routes.notifications import add_notification
            add_notification(
                user_id, 'Deposit Successful',
                f'PKR {amount:,.0f} has been deposited to your wallet.',
                'success', 'deposit'
            )
        except Exception as e:
            print(f"Notification error: {e}")

        return jsonify({
            "message":     "Deposit successful!",
            "new_balance": round(float(wallet.balance), 2)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@account_bp.route("/send", methods=["POST"])
@jwt_required()
@limiter.limit("20 per hour")
def send_money():
    user_id          = get_jwt_identity()
    data             = request.get_json()
    to_wallet_number = clean_wallet_number(data.get("to_wallet", ""))
    amount           = clean_amount(data.get("amount"))
    description      = clean_description(data.get("description", "Transfer"), 200)
    pin              = clean_pin(str(data.get("pin", "")))

    if not to_wallet_number:
        return jsonify({"error": "Recipient wallet is required"}), 400
    err = validate_wallet_number(to_wallet_number)
    if err: return jsonify({"error": err}), 400

    if amount is None:
        return jsonify({"error": "Invalid amount"}), 400
    err = validate_amount(amount)
    if err: return jsonify({"error": err}), 400

    if not pin or len(pin) != 4:
        return jsonify({"error": "PIN must be 4 digits"}), 400
    if not description:
        description = "Transfer"

    user        = User.query.get(user_id)
    sender_user = user

    if not bcrypt.checkpw(pin.encode("utf-8"), user.pin.encode("utf-8")):
        return jsonify({"error": "Incorrect PIN"}), 401
    if not user.kyc_verified:
        return jsonify({"error": "KYC verification required for transfers"}), 403

    sender_check = Wallet.query.filter_by(user_id=user_id).first()
    if not sender_check:
        return jsonify({"error": "Your wallet not found"}), 404
    if sender_check.wallet_number == to_wallet_number:
        return jsonify({"error": "Cannot send money to yourself"}), 400

    receiver_check = Wallet.query.filter_by(wallet_number=to_wallet_number).first()
    if not receiver_check:
        return jsonify({"error": "Recipient wallet not found"}), 404

    receiver_user = User.query.get(receiver_check.user_id)

    # ── Fraud Detection ──
    try:
        from routes.notifications import add_notification
        if amount >= 25000:
            add_notification(user_id, 'Large Transfer Alert',
                f'A transfer of PKR {amount:,.0f} to {receiver_user.full_name} was initiated. If this was not you, change your PIN immediately.',
                'warning', 'security')
            send_fraud_alert_email(user.email, user.full_name, amount,
                receiver_user.full_name, to_wallet_number, 'large_transfer')
        five_min_ago = datetime.utcnow() - timedelta(minutes=5)
        recent_count = Transaction.query.filter(
            Transaction.user_id    == user_id,
            Transaction.type       == 'transfer',
            Transaction.created_at >= five_min_ago
        ).count()
        if recent_count >= 3:
            add_notification(user_id, 'Unusual Activity Detected',
                f'{recent_count + 1} transfers in under 5 minutes. If this was not you, contact support.',
                'warning', 'security')
            send_fraud_alert_email(user.email, user.full_name, amount,
                receiver_user.full_name, to_wallet_number, 'rapid_transfer')
    except Exception as fraud_err:
        print(f"Fraud detection error: {fraud_err}")

    try:
        # ── ROW LOCK BOTH WALLETS — ordered to prevent deadlocks ──
        ids_ordered    = sorted([int(user_id), receiver_check.user_id])
        wallets_locked = Wallet.query.filter(
            Wallet.user_id.in_(ids_ordered)
        ).with_for_update().order_by(Wallet.user_id).all()

        sender   = next((w for w in wallets_locked if w.user_id == int(user_id)),           None)
        receiver = next((w for w in wallets_locked if w.user_id == receiver_check.user_id), None)

        if not sender or not receiver:
            db.session.rollback()
            return jsonify({"error": "Wallet error. Please try again."}), 500

        # ── Final balance check AFTER lock ──
        if float(sender.balance) < amount:
            db.session.rollback()
            return jsonify({"error": "Insufficient balance"}), 400

        sender.balance   -= amount
        receiver.balance += amount

        txn_debit = Transaction(
            user_id=user_id, from_wallet=sender.wallet_number,
            to_wallet=to_wallet_number, amount=amount,
            type="transfer", direction="debit", description=description
        )
        db.session.add(txn_debit)
        db.session.flush()

        ref = f"TXN-{str(txn_debit.id).zfill(6)}-{str(int(datetime.utcnow().timestamp()))[-6:]}"

        db.session.add(Transaction(
            user_id=receiver.user_id, from_wallet=sender.wallet_number,
            to_wallet=to_wallet_number, amount=amount,
            type="transfer", direction="credit", description=description
        ))
        db.session.commit()

        try:
            from routes.notifications import add_notification
            add_notification(user_id, 'Transfer Successful',
                f'PKR {amount:,.0f} sent to {receiver_user.full_name} successfully.', 'success', 'send')
            add_notification(receiver.user_id, 'Payment Received',
                f'PKR {amount:,.0f} received from {sender_user.full_name}.', 'success', 'receive')
        except Exception as e:
            print(f"Notification error: {e}")

        try:
            send_transfer_email_to_sender(sender_user, receiver_user, amount, ref, sender.wallet_number, to_wallet_number)
            send_transfer_email_to_receiver(sender_user, receiver_user, amount, ref, sender.wallet_number, to_wallet_number)
        except Exception as e:
            print(f"Transfer email error: {e}")

        return jsonify({
            "message":     "Money sent successfully!",
            "amount":      amount,
            "to_wallet":   to_wallet_number,
            "new_balance": round(float(sender.balance), 2)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@account_bp.route("/transactions", methods=["GET"])
@jwt_required()
def transaction_history():
    user_id      = get_jwt_identity()
    wallet       = Wallet.query.filter_by(user_id=user_id).first()
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404
    transactions = Transaction.query.filter(
        (Transaction.from_wallet == wallet.wallet_number) |
        (Transaction.to_wallet   == wallet.wallet_number)
    ).order_by(Transaction.created_at.desc()).all()
    result = []
    for txn in transactions:
        txn_dict              = txn.to_dict()
        txn_dict["direction"] = "credit" if txn.to_wallet == wallet.wallet_number else "debit"
        result.append(txn_dict)
    return jsonify({"wallet_number": wallet.wallet_number, "total": len(result), "transactions": result}), 200


@account_bp.route('/lookup', methods=['POST'])
@jwt_required()
@limiter.limit("30 per hour")
def lookup_wallet():
    data          = request.get_json()
    wallet_number = clean_wallet_number(data.get('wallet_number', ''))
    err = validate_wallet_number(wallet_number)
    if err: return jsonify({'error': err}), 400
    wallet = Wallet.query.filter_by(wallet_number=wallet_number).first()
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    user = User.query.get(wallet.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'full_name':     user.full_name,
        'phone':         user.phone,
        'wallet_number': wallet_number,
        'kyc_verified':  user.kyc_verified
    }), 200


@account_bp.route('/lookup-phone', methods=['POST'])
@jwt_required()
@limiter.limit("30 per hour")
def lookup_by_phone():
    data  = request.get_json()
    phone = clean_phone(data.get('phone', ''))
    if not phone or not phone.isdigit() or not (10 <= len(phone) <= 13):
        return jsonify({'error': 'Valid phone number required (10-13 digits)'}), 400
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({'error': 'No account found with this phone number'}), 404
    wallet = Wallet.query.filter_by(user_id=user.id).first()
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    return jsonify({
        'full_name':     user.full_name,
        'phone':         user.phone,
        'wallet_number': wallet.wallet_number,
        'kyc_verified':  user.kyc_verified
    }), 200
