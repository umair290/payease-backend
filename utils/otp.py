import random
import string
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User
from extensions import db

otp_bp = Blueprint('otp', __name__)
otp_store = {}

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

@otp_bp.route('/send', methods=['POST'])
@jwt_required()
def send_otp():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    purpose = data.get('purpose')

    if not purpose:
        return jsonify({'error': 'Purpose is required'}), 400
    if not user:
        return jsonify({'error': 'User not found'}), 404

    otp = generate_otp()
    otp_store[f"{user_id}_{purpose}"] = {
        'otp': otp,
        'expires': datetime.utcnow() + timedelta(minutes=10)
    }

    return jsonify({
        'message': 'OTP generated successfully',
        'email': user.email,
        'dev_otp': otp
    }), 200


@otp_bp.route('/verify', methods=['POST'])
@jwt_required()
def verify_otp():
    user_id = get_jwt_identity()
    data = request.get_json()
    purpose = data.get('purpose')
    otp = data.get('otp')

    key = f"{user_id}_{purpose}"
    stored = otp_store.get(key)

    if not stored:
        return jsonify({'error': 'OTP not found. Please request a new one.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP has expired.'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP.'}), 400

    del otp_store[key]
    return jsonify({'message': 'OTP verified successfully!'}), 200


@otp_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    new_password = data.get('new_password')
    otp = data.get('otp')

    if not new_password or not otp:
        return jsonify({'error': 'New password and OTP are required'}), 400

    key = f"{user_id}_change_password"
    stored = otp_store.get(key)

    if not stored:
        return jsonify({'error': 'OTP not found.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP expired'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP'}), 400

    del otp_store[key]

    import bcrypt
    user.password_hash = bcrypt.hashpw(
        new_password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    db.session.commit()
    return jsonify({'message': 'Password changed successfully!'}), 200


@otp_bp.route('/change-pin', methods=['POST'])
@jwt_required()
def change_pin():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    new_pin = data.get('new_pin')
    otp = data.get('otp')

    if not new_pin or not otp:
        return jsonify({'error': 'New PIN and OTP are required'}), 400
    if len(str(new_pin)) != 4:
        return jsonify({'error': 'PIN must be 4 digits'}), 400

    key = f"{user_id}_change_pin"
    stored = otp_store.get(key)

    if not stored:
        return jsonify({'error': 'OTP not found.'}), 400
    if datetime.utcnow() > stored['expires']:
        del otp_store[key]
        return jsonify({'error': 'OTP expired'}), 400
    if stored['otp'] != otp:
        return jsonify({'error': 'Invalid OTP'}), 400

    del otp_store[key]

    import bcrypt
    user.pin_hash = bcrypt.hashpw(
        str(new_pin).encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    db.session.commit()
    return jsonify({'message': 'PIN changed successfully!'}), 200
