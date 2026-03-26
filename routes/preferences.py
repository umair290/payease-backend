from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User
import cloudinary
import cloudinary.uploader
import json
import os

preferences_bp = Blueprint('preferences', __name__)

# ── Cloudinary setup ──
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key    = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
)

# ──────────────────────────────
# ONBOARDING
# ──────────────────────────────

@preferences_bp.route('/onboarding/complete', methods=['POST'])
@jwt_required()
def complete_onboarding():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    user.onboarding_done = True
    db.session.commit()
    return jsonify({'message': 'Onboarding complete'}), 200

@preferences_bp.route('/onboarding/status', methods=['GET'])
@jwt_required()
def get_onboarding_status():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'onboarding_done': user.onboarding_done}), 200

# ──────────────────────────────
# AVATAR
# ──────────────────────────────

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
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    try:
        result = cloudinary.uploader.upload(
            file,
            folder         = 'payease/avatars',
            public_id      = f'user_{user_id}_avatar',
            overwrite      = True,
            resource_type  = 'image',
            transformation = [
                {'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'},
                {'quality': 'auto', 'fetch_format': 'auto'}
            ]
        )
        user.avatar_url = result['secure_url']
        db.session.commit()
        return jsonify({
            'message':    'Avatar uploaded',
            'avatar_url': user.avatar_url
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@preferences_bp.route('/avatar/remove', methods=['DELETE'])
@jwt_required()
def remove_avatar():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    try:
        cloudinary.uploader.destroy(f'payease/avatars/user_{user_id}_avatar')
    except Exception:
        pass
    user.avatar_url = None
    db.session.commit()
    return jsonify({'message': 'Avatar removed'}), 200

# ──────────────────────────────
# BENEFICIARIES
# ──────────────────────────────

@preferences_bp.route('/beneficiaries', methods=['GET'])
@jwt_required()
def get_beneficiaries():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    try:
        bens = json.loads(user.beneficiaries or '[]')
    except Exception:
        bens = []
    return jsonify({'beneficiaries': bens}), 200

@preferences_bp.route('/beneficiaries', methods=['POST'])
@jwt_required()
def save_beneficiary():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    data = request.get_json()
    for field in ['id', 'full_name', 'phone', 'wallet_number']:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    try:
        bens = json.loads(user.beneficiaries or '[]')
    except Exception:
        bens = []

    # Reject duplicate
    if any(b['wallet_number'] == data['wallet_number'] for b in bens):
        return jsonify({'error': 'Already in your contacts'}), 409

    new_ben = {
        'id':            data['id'],
        'full_name':     data['full_name'],
        'phone':         data['phone'],
        'wallet_number': data['wallet_number'],
        'kyc_verified':  data.get('kyc_verified', False),
        'saved_at':      data.get('saved_at', ''),
    }
    bens = [new_ben] + bens
    bens = bens[:10]   # max 10 contacts
    user.beneficiaries = json.dumps(bens)
    db.session.commit()
    return jsonify({'message': 'Saved', 'beneficiaries': bens}), 200

@preferences_bp.route('/beneficiaries/<int:ben_id>', methods=['DELETE'])
@jwt_required()
def delete_beneficiary(ben_id):
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    try:
        bens = json.loads(user.beneficiaries or '[]')
    except Exception:
        bens = []
    bens = [b for b in bens if b['id'] != ben_id]
    user.beneficiaries = json.dumps(bens)
    db.session.commit()
    return jsonify({'message': 'Removed', 'beneficiaries': bens}), 200
