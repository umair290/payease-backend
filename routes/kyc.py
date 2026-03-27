import os
import cloudinary
import cloudinary.uploader
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db, limiter
from models.user import User
from models.kyc import KYC
from utils.sanitize import clean, clean_cnic, clean_name, clean_date, validate_cnic

kyc_bp = Blueprint('kyc', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE      = 5 * 1024 * 1024   # 5MB per file

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_cloudinary(file):
    cloudinary.config(
        cloud_name = current_app.config['CLOUDINARY_CLOUD_NAME'],
        api_key    = current_app.config['CLOUDINARY_API_KEY'],
        api_secret = current_app.config['CLOUDINARY_API_SECRET'],
    )
    result = cloudinary.uploader.upload(
        file,
        folder        = 'payease/kyc',
        resource_type = 'image',
        transformation = [
            {'quality': 'auto', 'fetch_format': 'auto'},
            {'width': 1200, 'crop': 'limit'}              # cap resolution
        ]
    )
    return result['secure_url']


# 3 per day — KYC should only be submitted a few times
@kyc_bp.route('/submit', methods=['POST'])
@jwt_required()
@limiter.limit("3 per day")
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

    # ── Sanitize form fields ──
    cnic_number       = clean_cnic(request.form.get('cnic_number', ''))
    full_name_on_card = clean_name(request.form.get('full_name_on_card', ''), 100)
    date_of_birth     = clean_date(request.form.get('date_of_birth', ''))

    # ── Validate CNIC ──
    err = validate_cnic(cnic_number)
    if err: return jsonify({'error': err}), 400

    # ── Validate files ──
    cnic_front = request.files.get('cnic_front')
    cnic_back  = request.files.get('cnic_back')
    selfie     = request.files.get('selfie')

    if not cnic_front or not cnic_back or not selfie:
        return jsonify({'error': 'All three documents are required (cnic_front, cnic_back, selfie)'}), 400

    for label, f in [('ID Front', cnic_front), ('ID Back', cnic_back), ('Selfie', selfie)]:
        if not allowed_file(f.filename):
            return jsonify({'error': f'{label}: only PNG, JPG, JPEG, WEBP allowed'}), 400
        # Check file size
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify({'error': f'{label}: file size exceeds 5MB limit'}), 400

    # ── Check CNIC not already used by someone else ──
    existing_cnic = KYC.query.filter_by(cnic_number=cnic_number).first()
    if existing_cnic and existing_cnic.user_id != int(user_id):
        return jsonify({'error': 'This CNIC is already registered to another account'}), 409

    try:
        cnic_front_url = upload_to_cloudinary(cnic_front)
        cnic_back_url  = upload_to_cloudinary(cnic_back)
        selfie_url     = upload_to_cloudinary(selfie)

        kyc = KYC(
            user_id           = user_id,
            cnic_number       = cnic_number,
            full_name_on_card = full_name_on_card,
            date_of_birth     = date_of_birth,
            cnic_front        = cnic_front_url,
            cnic_back         = cnic_back_url,
            selfie            = selfie_url,
            status            = 'pending',
        )
        db.session.add(kyc)
        db.session.commit()

        return jsonify({'message': 'KYC submitted successfully! Under review.'}), 201

    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@kyc_bp.route('/status', methods=['GET'])
@jwt_required()
def kyc_status():
    user_id = get_jwt_identity()
    kyc     = KYC.query.filter_by(user_id=user_id).first()

    if not kyc:
        return jsonify({'status': None}), 200

    return jsonify({
        'status':           kyc.status,
        'cnic_number':      kyc.cnic_number,
        'full_name_on_card': kyc.full_name_on_card,
        'date_of_birth':    kyc.date_of_birth,
        'rejection_reason': kyc.rejection_reason,
        'submitted_at':     str(kyc.submitted_at),
        'verified_at':      str(kyc.verified_at) if kyc.verified_at else None,
    }), 200
