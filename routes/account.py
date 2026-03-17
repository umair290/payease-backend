from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, Wallet, Transaction
import bcrypt
import os
import resend
from datetime import datetime, timedelta

account_bp = Blueprint("account", __name__)

# ── Resend setup ──
resend.api_key   = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')
SENDER_EMAIL     = os.environ.get('SENDER_EMAIL', 'support@payease.space')


def send_transfer_email_to_sender(sender_user, receiver_user, amount, ref, sender_wallet, receiver_wallet_num):
    """Send money sent confirmation to sender"""
    now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

<tr><td style="background:linear-gradient(135deg,#1A73E8,#0052CC);padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Digital Wallet & Payment Services</p>
</td></tr>

<tr><td style="padding:28px 32px 8px;">
<div style="text-align:center;margin-bottom:20px;">
  <div style="width:64px;height:64px;border-radius:50%;background:#DCFCE7;display:inline-flex;align-items:center;justify-content:center;font-size:28px;margin-bottom:10px;">💸</div>
  <h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 4px 0;">Money Sent Successfully!</h2>
  <p style="color:#888;font-size:13px;margin:0;">Your transfer has been processed</p>
</div>

<div style="background:linear-gradient(135deg,#1A73E8,#0052CC);border-radius:16px;padding:20px;text-align:center;margin-bottom:20px;">
  <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:0 0 4px 0;text-transform:uppercase;letter-spacing:1px;">Amount Sent</p>
  <p style="color:#fff;font-size:36px;font-weight:bold;margin:0;">PKR {amount:,.0f}</p>
</div>

<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFF;border-radius:14px;overflow:hidden;border:1px solid #E0E6F0;margin-bottom:20px;">
<tr style="background:#EEF2FF;">
  <td colspan="2" style="padding:10px 16px;font-size:11px;font-weight:700;color:#1A73E8;text-transform:uppercase;letter-spacing:0.5px;">Transaction Details</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">Sent To</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;text-align:right;">{receiver_user.full_name}</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">Receiver Wallet</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;text-align:right;font-family:monospace;">{receiver_wallet_num}</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">From Wallet</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;text-align:right;font-family:monospace;">{sender_wallet}</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">Reference</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A73E8;text-align:right;font-family:monospace;">{ref}</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">Date & Time</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;text-align:right;">{now}</td>
</tr>
<tr>
  <td style="padding:10px 16px;font-size:13px;color:#888;">Status</td>
  <td style="padding:10px 16px;text-align:right;"><span style="background:#DCFCE7;color:#16A34A;font-size:12px;font-weight:700;padding:4px 12px;border-radius:20px;">✓ Completed</span></td>
</tr>
</table>

<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:14px 16px;margin-bottom:20px;">
<p style="color:#C2410C;font-size:12px;font-weight:700;margin:0 0 4px 0;">🔒 Didn't make this transfer?</p>
<p style="color:#9A3412;font-size:12px;margin:0;line-height:1.5;">
If you did not initiate this transfer, please change your PIN immediately and contact support at support@payease.space
</p>
</div>
</td></tr>

<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:16px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">payease.space · support@payease.space</p>
<p style="color:#AAB0C0;font-size:10px;margin:4px 0 0 0;">© 2026 PayEase Digital Wallet. All rights reserved.</p>
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
            "subject": f"✅ PKR {amount:,.0f} Sent to {receiver_user.full_name} — PayEase",
            "html":    html,
        })
        print(f"Sender email sent to {sender_user.email}")
    except Exception as e:
        print(f"Sender email error: {e}")


def send_transfer_email_to_receiver(sender_user, receiver_user, amount, ref, sender_wallet, receiver_wallet_num):
    """Send money received notification to receiver"""
    now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

<tr><td style="background:linear-gradient(135deg,#16A34A,#15803D);padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Digital Wallet & Payment Services</p>
</td></tr>

<tr><td style="padding:28px 32px 8px;">
<div style="text-align:center;margin-bottom:20px;">
  <div style="width:64px;height:64px;border-radius:50%;background:#DCFCE7;display:inline-flex;align-items:center;justify-content:center;font-size:28px;margin-bottom:10px;">💰</div>
  <h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 4px 0;">Money Received!</h2>
  <p style="color:#888;font-size:13px;margin:0;">Funds have been added to your wallet</p>
</div>

<div style="background:linear-gradient(135deg,#16A34A,#15803D);border-radius:16px;padding:20px;text-align:center;margin-bottom:20px;">
  <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:0 0 4px 0;text-transform:uppercase;letter-spacing:1px;">Amount Received</p>
  <p style="color:#fff;font-size:36px;font-weight:bold;margin:0;">PKR {amount:,.0f}</p>
</div>

<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFF;border-radius:14px;overflow:hidden;border:1px solid #E0E6F0;margin-bottom:20px;">
<tr style="background:#F0FDF4;">
  <td colspan="2" style="padding:10px 16px;font-size:11px;font-weight:700;color:#16A34A;text-transform:uppercase;letter-spacing:0.5px;">Transaction Details</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">Received From</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;text-align:right;">{sender_user.full_name}</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">Sender Wallet</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;text-align:right;font-family:monospace;">{sender_wallet}</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">Your Wallet</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;text-align:right;font-family:monospace;">{receiver_wallet_num}</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">Reference</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A73E8;text-align:right;font-family:monospace;">{ref}</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">Date & Time</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;text-align:right;">{now}</td>
</tr>
<tr>
  <td style="padding:10px 16px;font-size:13px;color:#888;">Status</td>
  <td style="padding:10px 16px;text-align:right;"><span style="background:#DCFCE7;color:#16A34A;font-size:12px;font-weight:700;padding:4px 12px;border-radius:20px;">✓ Received</span></td>
</tr>
</table>

<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:14px 16px;margin-bottom:20px;text-align:center;">
<p style="color:#15803D;font-size:14px;font-weight:700;margin:0 0 4px 0;">🎉 Your wallet has been credited!</p>
<p style="color:#166534;font-size:12px;margin:0;line-height:1.5;">
Login to PayEase to view your updated balance and transaction history.
</p>
</div>
</td></tr>

<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:16px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">payease.space · support@payease.space</p>
<p style="color:#AAB0C0;font-size:10px;margin:4px 0 0 0;">© 2026 PayEase Digital Wallet. All rights reserved.</p>
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
            "subject": f"💰 PKR {amount:,.0f} Received from {sender_user.full_name} — PayEase",
            "html":    html,
        })
        print(f"Receiver email sent to {receiver_user.email}")
    except Exception as e:
        print(f"Receiver email error: {e}")


@account_bp.route("/balance", methods=["GET"])
@jwt_required()
def get_balance():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    wallet  = Wallet.query.filter_by(user_id=user_id).first()

    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404

    return jsonify({
        "full_name":     user.full_name,
        "email":         user.email,
        "phone":         user.phone,
        "wallet_number": wallet.wallet_number,
        "balance":       round(wallet.balance, 2)
    }), 200


@account_bp.route("/deposit", methods=["POST"])
@jwt_required()
def deposit():
    user_id = get_jwt_identity()
    data    = request.get_json()
    amount  = data.get("amount")

    if not amount or amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    wallet = Wallet.query.filter_by(user_id=user_id).first()

    try:
        wallet.balance += amount
        txn = Transaction(
            user_id     = user_id,
            from_wallet = None,
            to_wallet   = wallet.wallet_number,
            amount      = amount,
            type        = "deposit",
            description = "Deposit"
        )
        db.session.add(txn)
        db.session.commit()

        try:
            from routes.notifications import add_notification
            add_notification(
                user_id,
                '💰 Deposit Successful',
                f'PKR {amount:,.0f} deposited to your wallet',
                'success', 'deposit'
            )
        except Exception as notif_err:
            print(f"Notification error: {notif_err}")

        return jsonify({
            "message":     "Deposit successful!",
            "new_balance": round(wallet.balance, 2)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@account_bp.route("/send", methods=["POST"])
@jwt_required()
def send_money():
    user_id = get_jwt_identity()
    data    = request.get_json()

    to_wallet_number = data.get("to_wallet")
    amount           = data.get("amount")
    description      = data.get("description", "Transfer")
    pin              = data.get("pin")

    if not to_wallet_number or not amount:
        return jsonify({"error": "to_wallet and amount are required"}), 400
    if not pin:
        return jsonify({"error": "PIN is required for transfers"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than zero"}), 400

    user        = User.query.get(user_id)
    sender      = Wallet.query.filter_by(user_id=user_id).first()
    sender_user = User.query.get(user_id)

    # Verify PIN
    if not bcrypt.checkpw(pin.encode("utf-8"), user.pin.encode("utf-8")):
        return jsonify({"error": "Incorrect PIN"}), 401

    # Transfer limit
    if amount > 50000:
        return jsonify({"error": "Exceeds maximum transfer limit of 50,000"}), 400

    # KYC check
    if not user.kyc_verified:
        return jsonify({"error": "KYC verification required for transfers"}), 403

    receiver_wallet = Wallet.query.filter_by(wallet_number=to_wallet_number).first()
    if not receiver_wallet:
        return jsonify({"error": "Recipient wallet not found"}), 404
    if sender.wallet_number == to_wallet_number:
        return jsonify({"error": "Cannot send money to yourself"}), 400
    if sender.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    receiver_user = User.query.get(receiver_wallet.user_id)

    # ── Fraud Detection ──
    try:
        from routes.notifications import add_notification

        # Alert: Large transaction (PKR 25,000+)
        if amount >= 25000:
            add_notification(
                user_id,
                '🚨 Large Transfer Alert',
                f'A transfer of PKR {amount:,.0f} to {receiver_user.full_name} was initiated. If this wasn\'t you, change your PIN immediately.',
                'warning', 'security'
            )

        # Alert: Rapid transfers (3+ in 5 minutes)
        five_min_ago = datetime.utcnow() - timedelta(minutes=5)
        recent_count = Transaction.query.filter(
            Transaction.user_id   == user_id,
            Transaction.type      == 'transfer',
            Transaction.created_at >= five_min_ago
        ).count()

        if recent_count >= 3:
            add_notification(
                user_id,
                '⚠️ Unusual Activity Detected',
                f'{recent_count + 1} transfers in under 5 minutes. If this wasn\'t you, contact support immediately.',
                'warning', 'security'
            )

    except Exception as fraud_err:
        print(f"Fraud detection error: {fraud_err}")

    try:
        sender.balance          -= amount
        receiver_wallet.balance += amount

        # Generate reference number
        ref = 'TXN' + str(int(datetime.utcnow().timestamp()))[-8:]

        txn = Transaction(
            user_id     = user_id,
            from_wallet = sender.wallet_number,
            to_wallet   = to_wallet_number,
            amount      = amount,
            type        = "transfer",
            description = description
        )
        db.session.add(txn)
        db.session.commit()

        # ── Notifications ──
        try:
            from routes.notifications import add_notification
            add_notification(
                user_id,
                '💸 Money Sent',
                f'PKR {amount:,.0f} sent to {receiver_user.full_name} successfully',
                'success', 'send'
            )
            add_notification(
                receiver_wallet.user_id,
                '💰 Money Received',
                f'PKR {amount:,.0f} received from {sender_user.full_name}',
                'success', 'receive'
            )
        except Exception as notif_err:
            print(f"Notification error: {notif_err}")

        # ── Transfer Confirmation Emails ──
        try:
            send_transfer_email_to_sender(
                sender_user, receiver_user, amount, ref,
                sender.wallet_number, to_wallet_number
            )
            send_transfer_email_to_receiver(
                sender_user, receiver_user, amount, ref,
                sender.wallet_number, to_wallet_number
            )
        except Exception as email_err:
            print(f"Transfer email error: {email_err}")

        return jsonify({
            "message":     "Money sent successfully!",
            "amount":      amount,
            "to_wallet":   to_wallet_number,
            "new_balance": round(sender.balance, 2)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@account_bp.route("/transactions", methods=["GET"])
@jwt_required()
def transaction_history():
    user_id = get_jwt_identity()
    wallet  = Wallet.query.filter_by(user_id=user_id).first()

    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404

    transactions = Transaction.query.filter(
        (Transaction.from_wallet == wallet.wallet_number) |
        (Transaction.to_wallet   == wallet.wallet_number)
    ).order_by(Transaction.created_at.desc()).all()

    result = []
    for txn in transactions:
        txn_dict = txn.to_dict()
        if txn.to_wallet == wallet.wallet_number:
            txn_dict["direction"] = "credit"
        else:
            txn_dict["direction"] = "debit"
        result.append(txn_dict)

    return jsonify({
        "wallet_number": wallet.wallet_number,
        "total":         len(result),
        "transactions":  result
    }), 200


@account_bp.route('/lookup', methods=['POST'])
@jwt_required()
def lookup_wallet():
    data          = request.get_json()
    wallet_number = data.get('wallet_number')

    if not wallet_number:
        return jsonify({'error': 'Wallet number required'}), 400

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
def lookup_by_phone():
    data  = request.get_json()
    phone = data.get('phone')

    if not phone:
        return jsonify({'error': 'Phone number required'}), 400

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
