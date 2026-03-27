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
from datetime import datetime, timedelta

account_bp = Blueprint("account", __name__)

resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL', 'support@payease.space')


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
    user_id         = get_jwt_identity()
    data            = request.get_json()
    amount          = clean_amount(data.get("amount"))
    idempotency_key = clean(data.get("idempotency_key", ""), 64)

    if amount is None:
        return jsonify({"error": "Invalid amount"}), 400
    if amount > 500000:
        return jsonify({"error": "Deposit exceeds maximum allowed amount"}), 400

    if idempotency_key:
        existing = Transaction.query.filter_by(
            idempotency_key=idempotency_key,
            user_id=user_id,
            type='deposit'
        ).first()
        if existing:
            wallet = Wallet.query.filter_by(user_id=user_id).first()
            return jsonify({
                "message": "Deposit successful!",
                "new_balance": round(float(wallet.balance), 2),
                "duplicate": True
            }), 200

    try:
        wallet = Wallet.query.filter_by(user_id=user_id).with_for_update().first()
        if not wallet:
            return jsonify({"error": "Wallet not found"}), 404

        wallet.balance += amount

        txn = Transaction(
            user_id=user_id,
            from_wallet=None,
            to_wallet=wallet.wallet_number,
            amount=amount,
            type="deposit",
            direction="credit",
            description="Deposit",
            idempotency_key=idempotency_key or None
        )
        db.session.add(txn)
        db.session.commit()

        return jsonify({
            "message": "Deposit successful!",
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
    idempotency_key  = clean(data.get("idempotency_key", ""), 64)

    # ✅ Updated validation
    if not to_wallet_number:
        return jsonify({"error": "Recipient wallet is required"}), 400

    if not re.match(r'^PK[A-Z0-9]{8,12}$', to_wallet_number):
        return jsonify({"error": "Invalid wallet number format"}), 400

    if amount is None:
        return jsonify({"error": "Invalid amount"}), 400

    err = validate_amount(amount)
    if err:
        return jsonify({"error": err}), 400

    if not pin or len(pin) != 4:
        return jsonify({"error": "PIN must be 4 digits"}), 400

    if idempotency_key:
        existing = Transaction.query.filter_by(
            idempotency_key=idempotency_key,
            user_id=user_id,
            type='transfer',
            direction='debit'
        ).first()
        if existing:
            wallet = Wallet.query.filter_by(user_id=user_id).first()
            return jsonify({
                "message": "Money sent successfully!",
                "amount": float(existing.amount),
                "to_wallet": existing.to_wallet,
                "new_balance": round(float(wallet.balance), 2),
                "duplicate": True
            }), 200

    user = User.query.get(user_id)

    if not bcrypt.checkpw(pin.encode("utf-8"), user.pin.encode("utf-8")):
        return jsonify({"error": "Incorrect PIN"}), 401

    if not user.kyc_verified:
        return jsonify({"error": "KYC verification required for transfers"}), 403

    sender = Wallet.query.filter_by(user_id=user_id).first()
    if not sender:
        return jsonify({"error": "Wallet not found"}), 404

    if sender.wallet_number == to_wallet_number:
        return jsonify({"error": "Cannot send money to yourself"}), 400

    receiver = Wallet.query.filter_by(wallet_number=to_wallet_number).first()
    if not receiver:
        return jsonify({"error": "Recipient wallet not found"}), 404

    if float(sender.balance) < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    try:
        sender.balance -= amount
        receiver.balance += amount

        txn = Transaction(
            user_id=user_id,
            from_wallet=sender.wallet_number,
            to_wallet=to_wallet_number,
            amount=amount,
            type="transfer",
            direction="debit",
            description=description
        )
        db.session.add(txn)
        db.session.commit()

        return jsonify({
            "message": "Money sent successfully!",
            "amount": amount,
            "to_wallet": to_wallet_number,
            "new_balance": round(float(sender.balance), 2)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ✅ Updated lookup_wallet
@account_bp.route('/lookup', methods=['POST'])
@jwt_required()
@limiter.limit("30 per hour")
def lookup_wallet():
    data = request.get_json()
    wallet_number = clean_wallet_number(data.get('wallet_number', ''))

    if not wallet_number:
        return jsonify({'error': 'Wallet number is required'}), 400

    err = validate_wallet_number(wallet_number)
    if err:
        return jsonify({'error': err}), 400

    wallet = Wallet.query.filter_by(wallet_number=wallet_number).first()
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404

    user = User.query.get(wallet.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'full_name': user.full_name,
        'phone': user.phone,
        'wallet_number': wallet_number,
        'kyc_verified': user.kyc_verified
    }), 200


# ✅ Updated lookup_by_phone (FULL FIX)
@account_bp.route('/lookup-phone', methods=['POST'])
@jwt_required()
@limiter.limit("30 per hour")
def lookup_by_phone():
    data = request.get_json()

    phone = normalize_phone(data.get('phone', ''))

    if not phone:
        return jsonify({'error': 'Phone number required'}), 400

    if not phone.isdigit() or not (10 <= len(phone) <= 13):
        return jsonify({'error': 'Invalid phone number format'}), 400

    user = User.query.filter_by(phone=phone).first()

    # fallback for old DB formats
    if not user:
        variants = []

        if phone.startswith('0') and len(phone) == 11:
            variants.append('92' + phone[1:])
        elif phone.startswith('92') and len(phone) == 12:
            variants.append('0' + phone[2:])

        for v in variants:
            user = User.query.filter_by(phone=v).first()
            if user:
                break

    if not user:
        return jsonify({'error': 'No account found with this phone number'}), 404

    wallet = Wallet.query.filter_by(user_id=user.id).first()
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404

    return jsonify({
        'full_name': user.full_name,
        'phone': user.phone,
        'wallet_number': wallet.wallet_number,
        'kyc_verified': user.kyc_verified
    }), 200