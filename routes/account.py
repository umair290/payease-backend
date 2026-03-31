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
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL', 'support@payease.space')


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

    # ── Accept amount as float directly — no over-sanitization ──
    raw_amount = data.get("amount")
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400

    if amount <= 0:
        return jsonify({"error": "Amount must be greater than zero"}), 400
    if amount > 500000:
        return jsonify({"error": "Deposit exceeds maximum allowed amount of PKR 500,000"}), 400

    # ── Round to 2 decimal places ──
    amount = round(amount, 2)

    # ── Optional idempotency key ──
    idempotency_key = clean(data.get("idempotency_key", "") or "", 64) or None

    # ── Check for duplicate request ──
    if idempotency_key:
        existing = Transaction.query.filter_by(
            idempotency_key=idempotency_key,
            user_id=user_id,
            type='deposit'
        ).first()
        if existing:
            wallet = Wallet.query.filter_by(user_id=user_id).first()
            return jsonify({
                "message":     "Deposit successful!",
                "new_balance": round(float(wallet.balance), 2),
                "duplicate":   True
            }), 200

    try:
        wallet = Wallet.query.filter_by(user_id=user_id).with_for_update().first()
        if not wallet:
            return jsonify({"error": "Wallet not found"}), 404

        wallet.balance = round(float(wallet.balance) + amount, 2)

        txn = Transaction(
            user_id         = user_id,
            from_wallet     = None,
            to_wallet       = wallet.wallet_number,
            amount          = amount,
            type            = "deposit",
            direction       = "credit",
            description     = "Deposit",
            status          = "completed",
            idempotency_key = idempotency_key
        )
        db.session.add(txn)
        db.session.commit()

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
    user_id = get_jwt_identity()
    data    = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    to_wallet_number = clean_wallet_number(data.get("to_wallet", ""))
    pin              = clean_pin(str(data.get("pin", "")))
    description      = clean_description(data.get("description", "Transfer"), 200)
    idempotency_key  = clean(data.get("idempotency_key", "") or "", 64) or None

    # ── Amount ──
    raw_amount = data.get("amount")
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400

    if amount <= 0:
        return jsonify({"error": "Amount must be greater than zero"}), 400
    if amount > 50000:
        return jsonify({"error": "Amount exceeds maximum transfer limit of PKR 50,000"}), 400

    amount = round(amount, 2)

    # ── Wallet validation ──
    if not to_wallet_number:
        return jsonify({"error": "Recipient wallet is required"}), 400
    if not re.match(r'^PK[A-Z0-9]{8,12}$', to_wallet_number):
        return jsonify({"error": "Invalid wallet number format"}), 400

    # ── PIN validation ──
    if not pin or len(pin) != 4:
        return jsonify({"error": "PIN must be exactly 4 digits"}), 400

    # ── Idempotency check ──
    if idempotency_key:
        existing = Transaction.query.filter_by(
            idempotency_key = idempotency_key,
            user_id         = user_id,
            type            = 'transfer',
            direction       = 'debit'
        ).first()
        if existing:
            wallet = Wallet.query.filter_by(user_id=user_id).first()
            return jsonify({
                "message":     "Money sent successfully!",
                "amount":      float(existing.amount),
                "to_wallet":   existing.to_wallet,
                "new_balance": round(float(wallet.balance), 2),
                "duplicate":   True
            }), 200

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # ── PIN check ──
    if not bcrypt.checkpw(pin.encode("utf-8"), user.pin.encode("utf-8")):
        return jsonify({"error": "Incorrect PIN"}), 401

    # ── KYC check ──
    if not user.kyc_verified:
        return jsonify({"error": "KYC verification required to make transfers"}), 403

    # ── Self-transfer check ──
    sender = Wallet.query.filter_by(user_id=user_id).first()
    if not sender:
        return jsonify({"error": "Sender wallet not found"}), 404
    if sender.wallet_number == to_wallet_number:
        return jsonify({"error": "Cannot send money to yourself"}), 400

    # ── Recipient ──
    receiver = Wallet.query.filter_by(wallet_number=to_wallet_number).first()
    if not receiver:
        return jsonify({"error": "Recipient wallet not found"}), 404

    # ── Balance check ──
    if float(sender.balance) < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    try:
        # ── Lock both wallets in consistent order to prevent deadlock ──
        first_id  = min(sender.user_id, receiver.user_id)
        second_id = max(sender.user_id, receiver.user_id)
        wallets   = {w.user_id: w for w in Wallet.query.filter(
            Wallet.user_id.in_([first_id, second_id])
        ).with_for_update().all()}

        locked_sender   = wallets[sender.user_id]
        locked_receiver = wallets[receiver.user_id]

        # ── Final balance check after acquiring lock ──
        if float(locked_sender.balance) < amount:
            return jsonify({"error": "Insufficient balance"}), 400

        locked_sender.balance   = round(float(locked_sender.balance)   - amount, 2)
        locked_receiver.balance = round(float(locked_receiver.balance) + amount, 2)

        # ── Debit transaction ──
        debit_txn = Transaction(
            user_id         = user_id,
            from_wallet     = locked_sender.wallet_number,
            to_wallet       = to_wallet_number,
            amount          = amount,
            type            = "transfer",
            direction       = "debit",
            description     = description,
            status          = "completed",
            idempotency_key = idempotency_key
        )
        db.session.add(debit_txn)

        # ── Credit transaction for receiver ──
        credit_txn = Transaction(
            user_id     = locked_receiver.user_id,
            from_wallet = locked_sender.wallet_number,
            to_wallet   = to_wallet_number,
            amount      = amount,
            type        = "transfer",
            direction   = "credit",
            description = description,
            status      = "completed"
        )
        db.session.add(credit_txn)
        db.session.commit()

        return jsonify({
            "message":     "Money sent successfully!",
            "amount":      amount,
            "to_wallet":   to_wallet_number,
            "new_balance": round(float(locked_sender.balance), 2)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@account_bp.route("/lookup", methods=["POST"])
@jwt_required()
@limiter.limit("30 per hour")
def lookup_wallet():
    data          = request.get_json()
    wallet_number = clean_wallet_number(data.get("wallet_number", ""))

    if not wallet_number:
        return jsonify({"error": "Wallet number is required"}), 400

    # ── Validate format after cleaning ──
    if not re.match(r'^PK[A-Z0-9]{8,12}$', wallet_number):
        return jsonify({"error": "Invalid wallet number format (must start with PK)"}), 400

    wallet = Wallet.query.filter_by(wallet_number=wallet_number).first()
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404

    user = User.query.get(wallet.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "full_name":     user.full_name,
        "phone":         user.phone,
        "wallet_number": wallet_number,
        "kyc_verified":  user.kyc_verified
    }), 200


@account_bp.route("/lookup-phone", methods=["POST"])
@jwt_required()
@limiter.limit("30 per hour")
def lookup_by_phone():
    data  = request.get_json()
    phone = normalize_phone(data.get("phone", ""))

    if not phone:
        return jsonify({"error": "Phone number is required"}), 400
    if not phone.isdigit() or not (10 <= len(phone) <= 13):
        return jsonify({"error": "Invalid phone number format"}), 400

    # ── Try normalized format first ──
    user = User.query.filter_by(phone=phone).first()

    # ── Try format variants as fallback ──
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
        return jsonify({"error": "No account found with this phone number"}), 404

    wallet = Wallet.query.filter_by(user_id=user.id).first()
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404

    return jsonify({
        "full_name":     user.full_name,
        "phone":         user.phone,
        "wallet_number": wallet.wallet_number,
        "kyc_verified":  user.kyc_verified
    }), 200


@account_bp.route("/transactions", methods=["GET"])
@jwt_required()
def get_transactions():
    user_id  = get_jwt_identity()
    page     = int(request.args.get("page",     1))
    per_page = int(request.args.get("per_page", 20))
    tx_type  = request.args.get("type",      "")
    direction= request.args.get("direction", "")

    # ── Cap per_page ──
    per_page = min(per_page, 100)

    query = Transaction.query.filter_by(user_id=user_id)

    if tx_type:
        query = query.filter_by(type=tx_type)
    if direction:
        query = query.filter_by(direction=direction)

    query = query.order_by(Transaction.created_at.desc())

    total        = query.count()
    transactions = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages  = max(1, (total + per_page - 1) // per_page)

    return jsonify({
        "transactions": [t.to_dict() for t in transactions],
        "total":        total,
        "page":         page,
        "per_page":     per_page,
        "total_pages":  total_pages,
        "has_next":     page < total_pages,
        "has_prev":     page > 1,
    }), 200