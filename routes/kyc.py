from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, KYC
import os
import uuid
from datetime import datetime

kyc_bp = Blueprint("kyc", __name__)


def allowed_file(filename):
    allowed = {"png", "jpg", "jpeg"}
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in allowed


def save_image(file, folder):
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join("uploads", "kyc", folder, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file.save(path)
    return path
@kyc_bp.route("/submit", methods=["POST"])
@jwt_required()
def submit_kyc():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)

    # Check if KYC already submitted
    existing = KYC.query.filter_by(user_id=user_id).first()
    if existing:
        return jsonify({
            "error":  "KYC already submitted",
            "status": existing.status
        }), 409

    # Get CNIC number
    cnic_number = request.form.get("cnic_number")
    if not cnic_number:
        return jsonify({"error": "CNIC number is required"}), 400

    # Validate CNIC format (13 digits)
    cnic_clean = cnic_number.replace("-", "")
    if not cnic_clean.isdigit() or len(cnic_clean) != 13:
        return jsonify({"error": "Invalid CNIC format"}), 400

    # Check if CNIC already used
    if KYC.query.filter_by(cnic_number=cnic_clean).first():
        return jsonify({"error": "CNIC already registered"}), 409

    # Get uploaded files
    cnic_front = request.files.get("cnic_front")
    cnic_back  = request.files.get("cnic_back")
    selfie     = request.files.get("selfie")

    if not cnic_front or not cnic_back or not selfie:
        return jsonify({"error": "All images are required"}), 400

    # Validate file types
    for f in [cnic_front, cnic_back, selfie]:
        if not allowed_file(f.filename):
            return jsonify({"error": "Only jpg/png files allowed"}), 400

    try:
        # Save images
        front_path  = save_image(cnic_front, user_id)
        back_path   = save_image(cnic_back,  user_id)
        selfie_path = save_image(selfie,     user_id)

        # Create KYC record
        kyc = KYC(
            user_id     = user_id,
            cnic_number = cnic_clean,
            cnic_front  = front_path,
            cnic_back   = back_path,
            selfie      = selfie_path,
            status      = "pending"
        )
        db.session.add(kyc)
        db.session.commit()

        return jsonify({
            "message": "KYC submitted successfully!",
            "status":  "pending"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@kyc_bp.route("/status", methods=["GET"])
@jwt_required()
def kyc_status():
    user_id = get_jwt_identity()
    kyc     = KYC.query.filter_by(user_id=user_id).first()

    if not kyc:
        return jsonify({
            "status":  "not_submitted",
            "message": "KYC not submitted yet"
        }), 200

    return jsonify({
        "status":           kyc.status,
        "cnic_number":      kyc.cnic_number,
        "submitted_at":     str(kyc.submitted_at),
        "rejection_reason": kyc.rejection_reason
    }), 200