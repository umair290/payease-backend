from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, Wallet, Transaction, KYC
from datetime import datetime

admin_bp = Blueprint("admin", __name__)


def is_admin(user_id):
    user = User.query.get(user_id)
    return user and user.is_admin


#Show Dashboard Statistics
@admin_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    total_users        = User.query.count()
    total_transactions = Transaction.query.count()
    pending_kyc        = KYC.query.filter_by(status="pending").count()
    blocked_users      = User.query.filter_by(is_blocked=True).count()

    total_volume = db.session.query(
        db.func.sum(Transaction.amount)
    ).scalar() or 0

    return jsonify({
        "total_users":        total_users,
        "total_transactions": total_transactions,
        "pending_kyc":        pending_kyc,
        "blocked_users":      blocked_users,
        "total_volume":       round(total_volume, 2)
    }), 200

#Viewing all users

@admin_bp.route("/users", methods=["GET"])
@jwt_required()
def get_all_users():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    users = User.query.all()
    result = []

    for user in users:
        wallet = Wallet.query.filter_by(user_id=user.id).first()
        user_dict = user.to_dict()
        user_dict["balance"] = round(wallet.balance, 2) if wallet else 0
        result.append(user_dict)

    return jsonify({
        "total": len(result),
        "users": result
    }), 200


@admin_bp.route("/block-user", methods=["POST"])
@jwt_required()
def block_user():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data          = request.get_json()
    target_id     = data.get("user_id")
    block_status  = data.get("block", True)

    target = User.query.get(target_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    target.is_blocked = block_status
    db.session.commit()

    action = "blocked" if block_status else "unblocked"
    return jsonify({
        "message": f"User {action} successfully"
    }), 200

#KYC Management

@admin_bp.route("/kyc/pending", methods=["GET"])
@jwt_required()
def pending_kyc():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    kyc_list = KYC.query.filter_by(status="pending").all()
    result   = []

    for kyc in kyc_list:
        user     = User.query.get(kyc.user_id)
        kyc_dict = kyc.to_dict()
        kyc_dict["user"] = {
            "full_name": user.full_name,
            "email":     user.email,
            "phone":     user.phone
        }
        result.append(kyc_dict)

    return jsonify({
        "total":    len(result),
        "kyc_list": result
    }), 200


@admin_bp.route("/kyc/approve", methods=["POST"])
@jwt_required()
def approve_kyc():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data   = request.get_json()
    kyc_id = data.get("kyc_id")

    kyc = KYC.query.get(kyc_id)
    if not kyc:
        return jsonify({"error": "KYC record not found"}), 404

    kyc.status      = "approved"
    kyc.verified_at = datetime.utcnow()

    # Update user kyc_verified flag
    user              = User.query.get(kyc.user_id)
    user.kyc_verified = True

    db.session.commit()

    return jsonify({
        "message": "KYC approved successfully!"
    }), 200



@admin_bp.route("/kyc/reject", methods=["POST"])
@jwt_required()
def reject_kyc():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data             = request.get_json()
    kyc_id           = data.get("kyc_id")
    rejection_reason = data.get("reason", "Documents unclear")

    kyc = KYC.query.get(kyc_id)
    if not kyc:
        return jsonify({"error": "KYC record not found"}), 404

    kyc.status           = "rejected"
    kyc.rejection_reason = rejection_reason

    db.session.commit()

    return jsonify({
        "message": "KYC rejected",
        "reason":  rejection_reason
    }), 200


@admin_bp.route("/transactions", methods=["GET"])
@jwt_required()
def all_transactions():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    transactions = Transaction.query.order_by(
        Transaction.created_at.desc()
    ).limit(100).all()

    return jsonify({
        "total":        len(transactions),
        "transactions": [t.to_dict() for t in transactions]
    }), 200