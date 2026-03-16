import os
import cloudinary
import cloudinary.uploader
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models.user import User
from models.kyc import KYC
from flask import current_app

kyc_bp = Blueprint('kyc', __name__)

def upload_to_cloudinary(file):
    cloudinary.config(
        cloud_name=current_app.config['CLOUDINARY_CLOUD_NAME'],
        api_key=current_app.config['CLOUDINARY_API_KEY'],
        api_secret=current_app.config['CLOUDINARY_API_SECRET']
    )
    result = cloudinary.uploader.upload(
        file,
        folder='payease/kyc',
        resource_type='image'
    )
    return result['secure_url']


@kyc_bp.route('/submit', methods=['POST'])
@jwt_required()
def submit_kyc():
    user_id = get_jwt_identity()

    existing = KYC.query.filter_by(user_id=user_id).first()
    if existing:
        if existing.status == 'pending':
            return jsonify({'error': 'KYC already submitted', 'status': 'pending'}), 409
        elif existing.status == 'approved':
            return jsonify({'error': 'KYC already approved', 'status': 'approved'}), 409
        elif existing.status == 'rejected':
            db.session.delete(existing)
            db.session.commit()

    cnic_number = request.form.get('cnic_number')
    full_name_on_card = request.form.get('full_name_on_card', '')
    date_of_birth = request.form.get('date_of_birth', '')

    if not cnic_number:
        return jsonify({'error': 'CNIC number is required'}), 400
    if len(cnic_number) != 13 or not cnic_number.isdigit():
        return jsonify({'error': 'CNIC must be 13 digits'}), 400

    cnic_front = request.files.get('cnic_front')
    cnic_back = request.files.get('cnic_back')
    selfie = request.files.get('selfie')

    if not cnic_front or not cnic_back or not selfie:
        return jsonify({'error': 'All documents are required'}), 400

    try:
        cnic_front_url = upload_to_cloudinary(cnic_front)
        cnic_back_url = upload_to_cloudinary(cnic_back)
        selfie_url = upload_to_cloudinary(selfie)

        kyc = KYC(
            user_id=user_id,
            cnic_number=cnic_number,
            full_name_on_card=full_name_on_card,
            date_of_birth=date_of_birth,
            cnic_front=cnic_front_url,
            cnic_back=cnic_back_url,
            selfie=selfie_url,
            status='pending'
        )
        db.session.add(kyc)
        db.session.commit()

        return jsonify({'message': 'KYC submitted successfully!'}), 201

    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@kyc_bp.route('/status', methods=['GET'])
@jwt_required()
def kyc_status():
    user_id = get_jwt_identity()
    kyc = KYC.query.filter_by(user_id=user_id).first()

    if not kyc:
        return jsonify({'status': None}), 200

    return jsonify({
        'status': kyc.status,
        'cnic_number': kyc.cnic_number,
        'full_name_on_card': kyc.full_name_on_card,
        'date_of_birth': kyc.date_of_birth,
        'rejection_reason': kyc.rejection_reason,
        'submitted_at': str(kyc.submitted_at),
        'verified_at': str(kyc.verified_at) if kyc.verified_at else None,
    }), 200