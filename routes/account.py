from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db, limiter
from models import User, Wallet, Transaction
from utils.sanitize import (
    clean, clean_wallet_number, clean_description,
    clean_pin, clean_amount, clean_phone, normalize_phone,
    validate_amount, validate_wallet_number
)
import bcrypt
import os
import re
import resend
from datetime import datetime

account_bp = Blueprint("account", __name__)

resend.api_key = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL', '')


# ── Email helpers ──────────────────────────────────────────────

def send_deposit_email(email, full_name, amount, new_balance, wallet_number):
    now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#16A34A,#15803D);padding:32px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;">Deposit Successful</p>
</td></tr>
<tr><td style="padding:32px 36px;">
<h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 6px 0;">Money Added Successfully!</h2>
<p style="color:#888;font-size:13px;margin:0 0 24px 0;line-height:1.6;">Hi <strong>{full_name}</strong>, your deposit has been processed.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F9F4;border:2px solid #BBF7D0;border-radius:16px;margin-bottom:20px;">
<tr><td style="padding:24px;text-align:center;">
<p style="color:#15803D;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0;">Amount Deposited</p>
<p style="color:#15803D;font-size:40px;font-weight:bold;margin:0 0 4px 0;">PKR {amount:,.0f}</p>
<p style="color:#16A34A;font-size:13px;margin:0;">New Balance: <strong>PKR {new_balance:,.2f}</strong></p>
</td></tr></table>
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #E0E6F0;border-radius:14px;overflow:hidden;">
<tr style="background:#F8FAFF;"><td colspan="2" style="padding:10px 16px;font-size:11px;font-weight:700;color:#1A73E8;text-transform:uppercase;letter-spacing:0.5px;">Transaction Details</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Wallet</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;">{wallet_number}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Date</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;">{now}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Status</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#16A34A;">Completed</td></tr>
</table></td></tr>
<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:16px 36px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">payease.space</p>
</td></tr></table></td></tr></table>
</body></html>'''
    try:
        resend.Emails.send({"from": f"PayEase <{SENDER_EMAIL}>", "to": [email], "subject": f"PayEase — PKR {amount:,.0f} Deposited Successfully", "html": html})
    except Exception as e:
        print(f"Deposit email error: {e}")


def send_transfer_email_sender(email, full_name, amount, recipient_name, to_wallet, new_balance, ref):
    now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#1A73E8,#0052CC);padding:32px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;">Money Sent Successfully</p>
</td></tr>
<tr><td style="padding:32px 36px;">
<h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 6px 0;">Transfer Confirmed</h2>
<p style="color:#888;font-size:13px;margin:0 0 24px 0;line-height:1.6;">Hi <strong>{full_name}</strong>, your transfer has been processed.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#EFF6FF;border:2px solid #BFDBFE;border-radius:16px;margin-bottom:20px;">
<tr><td style="padding:24px;text-align:center;">
<p style="color:#1D4ED8;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0;">Amount Sent</p>
<p style="color:#1D4ED8;font-size:40px;font-weight:bold;margin:0 0 4px 0;">PKR {amount:,.0f}</p>
<p style="color:#1A73E8;font-size:13px;margin:0;">To: <strong>{recipient_name}</strong></p>
</td></tr></table>
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #E0E6F0;border-radius:14px;overflow:hidden;">
<tr style="background:#F8FAFF;"><td colspan="2" style="padding:10px 16px;font-size:11px;font-weight:700;color:#1A73E8;text-transform:uppercase;letter-spacing:0.5px;">Transfer Details</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Recipient</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;">{recipient_name}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Wallet ID</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;font-family:monospace;">{to_wallet}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Reference</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;">{ref}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">New Balance</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;">PKR {new_balance:,.2f}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Date</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;">{now}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Status</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#16A34A;">Completed</td></tr>
</table>
<div style="background:#FFF8F0;border:1px solid #FFE0B2;border-radius:12px;padding:14px 16px;margin-top:16px;">
<p style="color:#F59E0B;font-size:12px;font-weight:700;margin:0 0 4px 0;">Security Notice</p>
<p style="color:#888;font-size:12px;margin:0;line-height:1.5;">If you did not authorize this transfer, contact support immediately at payease.space</p>
</div></td></tr>
<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:16px 36px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">payease.space</p>
</td></tr></table></td></tr></table>
</body></html>'''
    try:
        resend.Emails.send({"from": f"PayEase <{SENDER_EMAIL}>", "to": [email], "subject": f"PayEase — PKR {amount:,.0f} Sent to {recipient_name}", "html": html})
    except Exception as e:
        print(f"Transfer sender email error: {e}")


def send_transfer_email_receiver(email, full_name, amount, sender_name, ref):
    now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#16A34A,#15803D);padding:32px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;">Money Received</p>
</td></tr>
<tr><td style="padding:32px 36px;">
<h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 6px 0;">You Received Money!</h2>
<p style="color:#888;font-size:13px;margin:0 0 24px 0;line-height:1.6;">Hi <strong>{full_name}</strong>, someone sent you money via PayEase.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F9F4;border:2px solid #BBF7D0;border-radius:16px;margin-bottom:20px;">
<tr><td style="padding:24px;text-align:center;">
<p style="color:#15803D;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0;">Amount Received</p>
<p style="color:#15803D;font-size:40px;font-weight:bold;margin:0 0 4px 0;">PKR {amount:,.0f}</p>
<p style="color:#16A34A;font-size:13px;margin:0;">From: <strong>{sender_name}</strong></p>
</td></tr></table>
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #E0E6F0;border-radius:14px;overflow:hidden;">
<tr style="background:#F8FAFF;"><td colspan="2" style="padding:10px 16px;font-size:11px;font-weight:700;color:#16A34A;text-transform:uppercase;letter-spacing:0.5px;">Payment Details</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">From</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;">{sender_name}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Reference</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;">{ref}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Date</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#1A1A2E;">{now}</td></tr>
<tr style="border-top:1px solid #E0E6F0;"><td style="padding:10px 16px;color:#888;font-size:13px;">Status</td><td style="padding:10px 16px;font-weight:600;font-size:13px;color:#16A34A;">Completed</td></tr>
</table></td></tr>
<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:16px 36px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">payease.space</p>
</td></tr></table></td></tr></table>
</body></html>'''
    try:
        resend.Emails.send({"from": f"PayEase <{SENDER_EMAIL}>", "to": [email], "subject": f"PayEase — PKR {amount:,.0f} Received from {sender_name}", "html": html})
    except Exception as e:
        print(f"Transfer receiver email error: {e}")


# ── Helper: enrich transactions with counterparty names ──
def _enrich_transactions(transactions):
    """
    Given a list of Transaction objects, return a list of dicts
    with counterparty_name and counterparty_avatar added.
    Uses a single bulk JOIN query — no N+1.
    """
    counterparty_wallets = set()
    for t in transactions:
        if t.direction == 'debit'  and t.to_wallet:
            counterparty_wallets.add(t.to_wallet)
        elif t.direction == 'credit' and t.from_wallet:
            counterparty_wallets.add(t.from_wallet)

    name_map = {}
    if counterparty_wallets:
        rows = (
            db.session.query(Wallet.wallet_number, User.full_name, User.avatar_url)
            .join(User, User.id == Wallet.user_id)
            .filter(Wallet.wallet_number.in_(counterparty_wallets))
            .all()
        )
        for wallet_number, full_name, avatar_url in rows:
            name_map[wallet_number] = {"full_name": full_name, "avatar_url": avatar_url}

    result = []
    for t in transactions:
        tx_dict = t.to_dict()
        if t.direction == 'debit' and t.to_wallet:
            info = name_map.get(t.to_wallet, {})
        elif t.direction == 'credit' and t.from_wallet:
            info = name_map.get(t.from_wallet, {})
        else:
            info = {}
        tx_dict['counterparty_name']   = info.get('full_name')
        tx_dict['counterparty_avatar'] = info.get('avatar_url')
        result.append(tx_dict)
    return result


# ── Routes ─────────────────────────────────────────────────────

@account_bp.route("/balance", methods=["GET"])
@jwt_required()
def get_balance():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    wallet  = Wallet.query.filter_by(user_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
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
@limiter.limit("20 per hour")
def deposit():
    user_id = get_jwt_identity()
    data    = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    raw_amount = data.get("amount")
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400

    if amount <= 0:
        return jsonify({"error": "Amount must be greater than zero"}), 400
    if amount > 500000:
        return jsonify({"error": "Deposit exceeds maximum allowed amount of PKR 500,000"}), 400

    amount          = round(amount, 2)
    idempotency_key = clean(data.get("idempotency_key", "") or "", 64) or None

    if idempotency_key:
        existing = Transaction.query.filter_by(idempotency_key=idempotency_key, user_id=user_id, type='deposit').first()
        if existing:
            wallet = Wallet.query.filter_by(user_id=user_id).first()
            return jsonify({"message": "Deposit successful!", "new_balance": round(float(wallet.balance), 2), "duplicate": True}), 200

    try:
        user   = User.query.get(user_id)
        wallet = Wallet.query.filter_by(user_id=user_id).with_for_update().first()
        if not wallet:
            return jsonify({"error": "Wallet not found"}), 404

        wallet.balance = round(float(wallet.balance) + amount, 2)
        txn = Transaction(user_id=user_id, from_wallet=None, to_wallet=wallet.wallet_number, amount=amount, type="deposit", direction="credit", description="Deposit", status="completed", idempotency_key=idempotency_key)
        db.session.add(txn)
        db.session.commit()

        try:
            from routes.notifications import add_notification
            add_notification(user_id, title="Deposit Successful", message=f"PKR {amount:,.0f} has been added to your wallet. New balance: PKR {wallet.balance:,.2f}", notif_type='success', icon='deposit')
        except Exception as e:
            print(f"Notification error: {e}")

        try:
            send_deposit_email(email=user.email, full_name=user.full_name, amount=amount, new_balance=float(wallet.balance), wallet_number=wallet.wallet_number)
        except Exception as e:
            print(f"Deposit email error: {e}")

        return jsonify({"message": "Deposit successful!", "new_balance": round(float(wallet.balance), 2)}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@account_bp.route("/send", methods=["POST"])
@jwt_required()
@limiter.limit("20 per hour")
def send_money():
    user_id = get_jwt_identity()
    data    = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    to_wallet_number = clean_wallet_number(data.get("to_wallet", ""))
    pin              = clean_pin(str(data.get("pin", "")))
    description      = clean_description(data.get("description", "Transfer"), 200)
    idempotency_key  = clean(data.get("idempotency_key", "") or "", 64) or None

    raw_amount = data.get("amount")
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400

    if amount <= 0:   return jsonify({"error": "Amount must be greater than zero"}), 400
    if amount > 50000: return jsonify({"error": "Amount exceeds maximum transfer limit of PKR 50,000"}), 400
    amount = round(amount, 2)

    if not to_wallet_number: return jsonify({"error": "Recipient wallet is required"}), 400
    if not re.match(r'^PK[A-Z0-9]{8,12}$', to_wallet_number): return jsonify({"error": "Invalid wallet number format"}), 400
    if not pin or len(pin) != 4: return jsonify({"error": "PIN must be exactly 4 digits"}), 400

    if idempotency_key:
        existing = Transaction.query.filter_by(idempotency_key=idempotency_key, user_id=user_id, type='transfer', direction='debit').first()
        if existing:
            wallet = Wallet.query.filter_by(user_id=user_id).first()
            return jsonify({"message": "Money sent successfully!", "amount": float(existing.amount), "to_wallet": existing.to_wallet, "new_balance": round(float(wallet.balance), 2), "duplicate": True}), 200

    user = User.query.get(user_id)
    if not user: return jsonify({"error": "User not found"}), 404
    if not bcrypt.checkpw(pin.encode("utf-8"), user.pin.encode("utf-8")): return jsonify({"error": "Incorrect PIN"}), 401
    if not user.kyc_verified: return jsonify({"error": "KYC verification required to make transfers"}), 403

    sender = Wallet.query.filter_by(user_id=user_id).first()
    if not sender: return jsonify({"error": "Sender wallet not found"}), 404
    if sender.wallet_number == to_wallet_number: return jsonify({"error": "Cannot send money to yourself"}), 400

    receiver_wallet = Wallet.query.filter_by(wallet_number=to_wallet_number).first()
    if not receiver_wallet: return jsonify({"error": "Recipient wallet not found"}), 404
    if float(sender.balance) < amount: return jsonify({"error": "Insufficient balance"}), 400

    receiver_user = User.query.get(receiver_wallet.user_id)

    try:
        first_id  = min(int(user_id), receiver_wallet.user_id)
        second_id = max(int(user_id), receiver_wallet.user_id)
        wallets   = {w.user_id: w for w in Wallet.query.filter(Wallet.user_id.in_([first_id, second_id])).with_for_update().all()}

        locked_sender   = wallets[int(user_id)]
        locked_receiver = wallets[receiver_wallet.user_id]

        if float(locked_sender.balance) < amount:
            return jsonify({"error": "Insufficient balance"}), 400

        locked_sender.balance   = round(float(locked_sender.balance)   - amount, 2)
        locked_receiver.balance = round(float(locked_receiver.balance) + amount, 2)

        ref = 'TXN' + str(txn_id := int(datetime.utcnow().timestamp() * 1000))[-8:]

        debit_txn = Transaction(user_id=user_id, from_wallet=locked_sender.wallet_number, to_wallet=to_wallet_number, amount=amount, type="transfer", direction="debit", description=description, status="completed", idempotency_key=idempotency_key)
        db.session.add(debit_txn)

        credit_txn = Transaction(user_id=locked_receiver.user_id, from_wallet=locked_sender.wallet_number, to_wallet=to_wallet_number, amount=amount, type="transfer", direction="credit", description=description, status="completed")
        db.session.add(credit_txn)
        db.session.commit()

        try:
            from routes.notifications import add_notification
            add_notification(user_id, title="Money Sent", message=f"PKR {amount:,.0f} sent to {receiver_user.full_name if receiver_user else to_wallet_number}. New balance: PKR {locked_sender.balance:,.2f}", notif_type='success', icon='send')
            if receiver_user:
                add_notification(locked_receiver.user_id, title="Money Received", message=f"PKR {amount:,.0f} received from {user.full_name}.", notif_type='success', icon='receive')
        except Exception as e:
            print(f"Notification error: {e}")

        try:
            send_transfer_email_sender(email=user.email, full_name=user.full_name, amount=amount, recipient_name=receiver_user.full_name if receiver_user else to_wallet_number, to_wallet=to_wallet_number, new_balance=float(locked_sender.balance), ref=ref)
        except Exception as e:
            print(f"Sender email error: {e}")

        try:
            if receiver_user:
                send_transfer_email_receiver(email=receiver_user.email, full_name=receiver_user.full_name, amount=amount, sender_name=user.full_name, ref=ref)
        except Exception as e:
            print(f"Receiver email error: {e}")

        return jsonify({"message": "Money sent successfully!", "amount": amount, "to_wallet": to_wallet_number, "new_balance": round(float(locked_sender.balance), 2)}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@account_bp.route("/lookup", methods=["POST"])
@jwt_required()
@limiter.limit("30 per hour")
def lookup_wallet():
    data          = request.get_json()
    wallet_number = clean_wallet_number(data.get("wallet_number", ""))
    if not wallet_number: return jsonify({"error": "Wallet number is required"}), 400
    if not re.match(r'^PK[A-Z0-9]{8,12}$', wallet_number): return jsonify({"error": "Invalid wallet number format"}), 400

    wallet = Wallet.query.filter_by(wallet_number=wallet_number).first()
    if not wallet: return jsonify({"error": "Wallet not found"}), 404
    user = User.query.get(wallet.user_id)
    if not user: return jsonify({"error": "User not found"}), 404

    return jsonify({"full_name": user.full_name, "phone": user.phone, "wallet_number": wallet_number, "kyc_verified": user.kyc_verified, "avatar_url": user.avatar_url}), 200


@account_bp.route("/lookup-phone", methods=["POST"])
@jwt_required()
@limiter.limit("30 per hour")
def lookup_by_phone():
    data  = request.get_json()
    phone = normalize_phone(data.get("phone", ""))
    if not phone: return jsonify({"error": "Phone number is required"}), 400
    if not phone.isdigit() or not (10 <= len(phone) <= 13): return jsonify({"error": "Invalid phone number format"}), 400

    user = User.query.filter_by(phone=phone).first()
    if not user:
        variants = []
        if phone.startswith('0') and len(phone) == 11:    variants.append('92' + phone[1:])
        elif phone.startswith('92') and len(phone) == 12: variants.append('0' + phone[2:])
        for v in variants:
            user = User.query.filter_by(phone=v).first()
            if user: break

    if not user: return jsonify({"error": "No account found with this phone number"}), 404
    wallet = Wallet.query.filter_by(user_id=user.id).first()
    if not wallet: return jsonify({"error": "Wallet not found"}), 404

    return jsonify({"full_name": user.full_name, "phone": user.phone, "wallet_number": wallet.wallet_number, "kyc_verified": user.kyc_verified, "avatar_url": user.avatar_url}), 200


@account_bp.route("/transactions", methods=["GET"])
@jwt_required()
def get_transactions():
    user_id  = get_jwt_identity()
    page     = int(request.args.get("page",     1))
    per_page = int(request.args.get("per_page", 20))
    tx_type  = request.args.get("type",      "")
    direction= request.args.get("direction", "")

    per_page = min(per_page, 100)

    query = Transaction.query.filter_by(user_id=user_id)
    if tx_type:  query = query.filter_by(type=tx_type)
    if direction: query = query.filter_by(direction=direction)

    query        = query.order_by(Transaction.created_at.desc())
    total        = query.count()
    transactions = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages  = max(1, (total + per_page - 1) // per_page)

    # ── Enrich with counterparty names (single bulk JOIN, no N+1) ──
    enriched = _enrich_transactions(transactions)

    return jsonify({
        "transactions": enriched,
        "total":        total,
        "page":         page,
        "per_page":     per_page,
        "total_pages":  total_pages,
        "has_next":     page < total_pages,
        "has_prev":     page > 1,
    }), 200


@account_bp.route("/transactions/all", methods=["GET"])
@jwt_required()
def get_all_transactions():
    """Export endpoint — returns all transactions enriched with counterparty names."""
    user_id      = get_jwt_identity()
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).all()
    enriched     = _enrich_transactions(transactions)
    return jsonify({"transactions": enriched, "total": len(enriched)}), 200
