from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, Wallet, Transaction
import bcrypt

account_bp = Blueprint("account", __name__)


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

    user   = User.query.get(user_id)
    sender = Wallet.query.filter_by(user_id=user_id).first()

    # Verify PIN
    if not bcrypt.checkpw(
        pin.encode("utf-8"),
        user.pin.encode("utf-8")
    ):
        return jsonify({"error": "Incorrect PIN"}), 401

    # Check transfer limit
    if amount > 50000:
        return jsonify({"error": "Exceeds maximum transfer limit of 50,000"}), 400

    # Check KYC
    if not user.kyc_verified:
        return jsonify({"error": "KYC verification required for transfers"}), 403

    receiver = Wallet.query.filter_by(
        wallet_number=to_wallet_number
    ).first()

    if not receiver:
        return jsonify({"error": "Recipient wallet not found"}), 404

    if sender.wallet_number == to_wallet_number:
        return jsonify({"error": "Cannot send money to yourself"}), 400

    if sender.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    try:
        sender.balance   -= amount
        receiver.balance += amount

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
    data = request.get_json()
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
        'full_name': user.full_name,
        'phone': user.phone,
        'wallet_number': wallet_number,
        'kyc_verified': user.kyc_verified
    }), 200

@account_bp.route('/lookup-phone', methods=['POST'])
@jwt_required()
def lookup_by_phone():
    data = request.get_json()
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
        'full_name': user.full_name,
        'phone': user.phone,
        'wallet_number': wallet.wallet_number,
        'kyc_verified': user.kyc_verified
    }), 200



