from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models.user        import User
from models.beneficiary import Beneficiary
import cloudinary
import cloudinary.uploader
import os

preferences_bp = Blueprint('preferences', __name__)

cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key    = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
)


# ─────────────────────────────────────────
# ONBOARDING
# ─────────────────────────────────────────

@preferences_bp.route('/onboarding/complete', methods=['POST'])
@jwt_required()
def complete_onboarding():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    user.onboarding_done = True
    db.session.commit()
    return jsonify({'message': 'Onboarding complete', 'onboarding_done': True}), 200


@preferences_bp.route('/onboarding/status', methods=['GET'])
@jwt_required()
def onboarding_status():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'onboarding_done': user.onboarding_done}), 200


# ─────────────────────────────────────────
# AVATAR
# ─────────────────────────────────────────

@preferences_bp.route('/avatar/upload', methods=['POST'])
@jwt_required()
def upload_avatar():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if 'avatar' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['avatar']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        result = cloudinary.uploader.upload(
            file,
            folder          = 'payease/avatars',
            transformation  = [{'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'}],
            allowed_formats = ['jpg', 'jpeg', 'png', 'webp'],
        )
        avatar_url       = result['secure_url']
        user.avatar_url  = avatar_url
        db.session.commit()
        return jsonify({'avatar_url': avatar_url, 'message': 'Avatar updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@preferences_bp.route('/avatar/remove', methods=['DELETE'])
@jwt_required()
def remove_avatar():
    user_id         = get_jwt_identity()
    user            = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    user.avatar_url = None
    db.session.commit()
    return jsonify({'message': 'Avatar removed'}), 200


# ─────────────────────────────────────────
# BENEFICIARIES — DB-backed
# ─────────────────────────────────────────

@preferences_bp.route('/beneficiaries', methods=['GET'])
@jwt_required()
def get_beneficiaries():
    user_id = get_jwt_identity()
    bens    = (
        Beneficiary.query
        .filter_by(user_id=user_id)
        .order_by(Beneficiary.created_at.desc())
        .all()
    )
    return jsonify({'beneficiaries': [b.to_dict() for b in bens]}), 200


@preferences_bp.route('/beneficiaries', methods=['POST'])
@jwt_required()
def save_beneficiary():
    user_id = get_jwt_identity()
    data    = request.get_json()

    wallet_number = (data.get('wallet_number') or '').strip().upper()
    full_name     = (data.get('full_name')     or '').strip()
    phone         = (data.get('phone')         or '').strip()
    avatar_url    = (data.get('avatar_url')    or '').strip()
    nickname      = (data.get('nickname')      or '').strip()

    if not wallet_number:
        return jsonify({'error': 'Wallet number is required'}), 400
    if not full_name:
        return jsonify({'error': 'Full name is required'}), 400

    # ── Check if already saved ──
    existing = Beneficiary.query.filter_by(
        user_id       = user_id,
        wallet_number = wallet_number
    ).first()

    if existing:
        # Update existing
        existing.full_name  = full_name
        existing.phone      = phone      or existing.phone
        existing.avatar_url = avatar_url or existing.avatar_url
        existing.nickname   = nickname   or existing.nickname
        db.session.commit()
        return jsonify({'message': 'Beneficiary updated', 'beneficiary': existing.to_dict()}), 200

    ben = Beneficiary(
        user_id       = user_id,
        wallet_number = wallet_number,
        full_name     = full_name,
        phone         = phone      or None,
        avatar_url    = avatar_url or None,
        nickname      = nickname   or None,
    )
    db.session.add(ben)
    db.session.commit()
    return jsonify({'message': 'Beneficiary saved', 'beneficiary': ben.to_dict()}), 201


@preferences_bp.route('/beneficiaries/<int:ben_id>', methods=['DELETE'])
@jwt_required()
def delete_beneficiary(ben_id):
    user_id = get_jwt_identity()
    ben     = Beneficiary.query.filter_by(id=ben_id, user_id=user_id).first()
    if not ben:
        return jsonify({'error': 'Beneficiary not found'}), 404
    db.session.delete(ben)
    db.session.commit()
    return jsonify({'message': 'Beneficiary removed'}), 20