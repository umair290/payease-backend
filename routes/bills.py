from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, Wallet, Transaction, Bill
import bcrypt

bills_bp = Blueprint("bills", __name__)

PROVIDERS = {
    "electricity": ["LESCO", "KESC"],
    "gas": ["SSGC", "SNGPL"],
    "internet": ["PTCL", "Nayatel"],
    "topup": ["Jazz", "Telenor", "Zong", "Ufone"]
}

@bills_bp.route("/providers", methods=["GET"])
def get_providers():
    return jsonify({"providers": PROVIDERS}), 200


@bills_bp.route("/pay", methods=["POST"])
@jwt_required()
def pay_bill():
    user_id = get_jwt_identity()
    data    = request.get_json()

    bill_type = data.get("bill_type")
    provider  = data.get("provider")
    amount    = data.get("amount")
    reference = data.get("reference")
    pin       = data.get("pin")

    if not all([bill_type, provider, amount, reference, pin]):
        return jsonify({"error": "All fields are required"}), 400

    if bill_type not in PROVIDERS:
        return jsonify({"error": "Invalid bill type"}), 400

    if provider not in PROVIDERS[bill_type]:
        return jsonify({"error": "Invalid provider"}), 400

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    user   = User.query.get(user_id)
    wallet = Wallet.query.filter_by(user_id=user_id).first()

    if not bcrypt.checkpw(
        pin.encode("utf-8"),
        user.pin.encode("utf-8")
    ):
        return jsonify({"error": "Incorrect PIN"}), 401

    if wallet.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    try:
        wallet.balance -= amount

        bill = Bill(
            user_id   = user_id,
            bill_type = bill_type,
            provider  = provider,
            amount    = amount,
            reference = reference,
            status    = "paid",
            paid_at   = db.func.now()
        )
        db.session.add(bill)

        txn = Transaction(
            user_id     = user_id,
            from_wallet = wallet.wallet_number,
            to_wallet   = provider,
            amount      = amount,
            type        = bill_type,
            description = f"{provider} bill payment - {reference}"
        )
        db.session.add(txn)
        db.session.commit()

        # ✅ Notification BEFORE return
        try:
            from routes.notifications import add_notification
            add_notification(
                user_id,
                '✅ Bill Payment Successful',
                f'PKR {amount:,.0f} paid for {provider} successfully',
                'success', 'bill'
            )
        except Exception as notif_err:
            print(f"Notification error: {notif_err}")

        return jsonify({
            "message":   "Bill paid successfully!",
            "bill_type": bill_type,
            "provider":  provider,
            "amount":    amount,
            "reference": reference,
            "balance":   round(wallet.balance, 2)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bills_bp.route("/history", methods=["GET"])
@jwt_required()
def bill_history():
    user_id = get_jwt_identity()
    bills = Bill.query.filter_by(
        user_id=user_id
    ).order_by(Bill.created_at.desc()).all()

    return jsonify({
        "total": len(bills),
        "bills": [b.to_dict() for b in bills]
    }), 200