import os
import resend
import cloudinary
import cloudinary.uploader
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db, limiter
from models.user import User
from models.kyc  import KYC
from utils.sanitize   import clean, clean_cnic, clean_name, clean_date, validate_cnic
from utils.encryption import encrypt_field, decrypt_field
from datetime import datetime

kyc_bp = Blueprint('kyc', __name__)

resend.api_key = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL', 'support@payease.space')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE      = 5 * 1024 * 1024  # 5MB

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
        transformation= [
            {'quality': 'auto', 'fetch_format': 'auto'},
            {'width': 1200, 'crop': 'limit'}
        ]
    )
    return result['secure_url']


# ── Email helpers ────────────────────────────────────────────

def send_kyc_submitted_email(email, full_name):
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#CA8A04,#92400E);padding:32px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;">Identity Verification</p>
</td></tr>
<tr><td style="padding:32px 36px;text-align:center;">
<h2 style="color:#92400E;font-size:22px;font-weight:bold;margin:0 0 8px 0;">Documents Received!</h2>
<p style="color:#888;font-size:13px;margin:0 0 20px 0;line-height:1.7;">
Hi <strong>{full_name}</strong>, we have received your KYC documents and they are now under review.
</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:14px;margin-bottom:24px;">
<tr><td style="padding:16px;text-align:left;">
<p style="color:#92400E;font-size:13px;font-weight:700;margin:0 0 8px 0;">What happens next:</p>
<p style="color:#78350F;font-size:13px;margin:0 0 4px 0;">• Our team will review your documents</p>
<p style="color:#78350F;font-size:13px;margin:0 0 4px 0;">• Review usually takes up to 24 hours</p>
<p style="color:#78350F;font-size:13px;margin:0;">• You will receive an email with the result</p>
</td></tr>
</table>
<a href="https://payeaseweb.vercel.app/dashboard" style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#1A73E8,#7C3AED);color:#fff;text-decoration:none;border-radius:12px;font-weight:bold;font-size:14px;">Back to Dashboard</a>
</td></tr>
<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:16px 36px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">payeaseweb.vercel.app</p>
</td></tr>
</table></td></tr></table>
</body></html>'''
    try:
        resend.Emails.send({
            "from":    f"PayEase <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": "PayEase — KYC Documents Received, Under Review",
            "html":    html,
        })
    except Exception as e:
        print(f"KYC submitted email error: {e}")


def send_kyc_approved_email(email, full_name):
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#16A34A,#15803D);padding:32px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;">Identity Verification</p>
</td></tr>
<tr><td style="padding:32px 36px;text-align:center;">
<h2 style="color:#15803D;font-size:24px;font-weight:bold;margin:0 0 8px 0;">KYC Approved!</h2>
<p style="color:#888;font-size:13px;margin:0 0 20px 0;line-height:1.7;">
Hi <strong>{full_name}</strong>, your identity has been successfully verified.
You can now use all PayEase features including transfers and higher limits.
</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:14px;margin-bottom:24px;">
<tr><td style="padding:16px;text-align:left;">
<p style="color:#15803D;font-size:13px;font-weight:700;margin:0 0 8px 0;">What you can do now:</p>
<p style="color:#166534;font-size:13px;margin:0 0 4px 0;">✓ Send money to any wallet</p>
<p style="color:#166534;font-size:13px;margin:0 0 4px 0;">✓ Higher transaction limits</p>
<p style="color:#166534;font-size:13px;margin:0;">✓ Full access to all features</p>
</td></tr>
</table>
<a href="https://payeaseweb.vercel.app/dashboard" style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#16A34A,#15803D);color:#fff;text-decoration:none;border-radius:12px;font-weight:bold;font-size:14px;box-shadow:0 6px 20px rgba(22,163,74,0.3);">Open PayEase</a>
</td></tr>
<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:16px 36px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">payeaseweb.vercel.app</p>
</td></tr>
</table></td></tr></table>
</body></html>'''
    try:
        resend.Emails.send({
            "from":    f"PayEase <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": "PayEase — Your Identity Has Been Verified!",
            "html":    html,
        })
    except Exception as e:
        print(f"KYC approved email error: {e}")


def send_kyc_rejected_email(email, full_name, reason):
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#DC2626,#B91C1C);padding:32px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;">Identity Verification</p>
</td></tr>
<tr><td style="padding:32px 36px;">
<h2 style="color:#DC2626;font-size:22px;font-weight:bold;margin:0 0 8px 0;text-align:center;">KYC Not Approved</h2>
<p style="color:#888;font-size:13px;margin:0 0 20px 0;line-height:1.7;text-align:center;">
Hi <strong>{full_name}</strong>, we were unable to verify your identity at this time.
</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#FEF2F2;border:1px solid #FECACA;border-radius:14px;margin-bottom:16px;">
<tr><td style="padding:16px;">
<p style="color:#DC2626;font-size:13px;font-weight:700;margin:0 0 8px 0;">Reason for rejection:</p>
<p style="color:#7F1D1D;font-size:13px;margin:0;line-height:1.6;">{reason or "Documents could not be verified. Please ensure all documents are clear and valid."}</p>
</td></tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFF;border:1px solid #E0E6F0;border-radius:14px;margin-bottom:24px;">
<tr><td style="padding:16px;">
<p style="color:#1A73E8;font-size:13px;font-weight:700;margin:0 0 8px 0;">How to fix this:</p>
<p style="color:#334155;font-size:13px;margin:0 0 4px 0;">• Ensure all document photos are clear and readable</p>
<p style="color:#334155;font-size:13px;margin:0 0 4px 0;">• Verify your CNIC number is entered correctly (13 digits)</p>
<p style="color:#334155;font-size:13px;margin:0 0 4px 0;">• Take photos in good lighting with all 4 corners visible</p>
<p style="color:#334155;font-size:13px;margin:0;">• Your selfie must clearly show your face</p>
</td></tr>
</table>
<div style="text-align:center;">
<a href="https://payeaseweb.vercel.app/kyc" style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#1A73E8,#7C3AED);color:#fff;text-decoration:none;border-radius:12px;font-weight:bold;font-size:14px;box-shadow:0 6px 20px rgba(26,115,232,0.3);">Resubmit KYC</a>
</div>
</td></tr>
<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:16px 36px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">payeaseweb.vercel.app</p>
</td></tr>
</table></td></tr></table>
</body></html>'''
    try:
        resend.Emails.send({
            "from":    f"PayEase <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": "PayEase — Action Required: KYC Application Update",
            "html":    html,
        })
    except Exception as e:
        print(f"KYC rejected email error: {e}")


# ── Routes ───────────────────────────────────────────────────

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

    cnic_number       = clean_cnic(request.form.get('cnic_number', ''))
    full_name_on_card = clean_name(request.form.get('full_name_on_card', ''), 100)
    date_of_birth     = clean_date(request.form.get('date_of_birth', ''))

    err = validate_cnic(cnic_number)
    if err:
        return jsonify({'error': err}), 400

    cnic_front = request.files.get('cnic_front')
    cnic_back  = request.files.get('cnic_back')
    selfie     = request.files.get('selfie')

    if not cnic_front or not cnic_back or not selfie:
        return jsonify({'error': 'All three documents are required'}), 400

    for label, f in [('ID Front', cnic_front), ('ID Back', cnic_back), ('Selfie', selfie)]:
        if not allowed_file(f.filename):
            return jsonify({'error': f'{label}: only PNG, JPG, JPEG, WEBP allowed'}), 400
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify({'error': f'{label}: file size exceeds 5MB. Images are auto-compressed on upload.'}), 400

    # ── Check CNIC not already used ──
    all_kyc = KYC.query.all()
    for k in all_kyc:
        if k.user_id != int(user_id):
            try:
                decrypted = decrypt_field(k.cnic_number)
                if decrypted == cnic_number:
                    return jsonify({'error': 'This CNIC is already registered to another account'}), 409
            except Exception:
                pass

    try:
        cnic_front_url = upload_to_cloudinary(cnic_front)
        cnic_back_url  = upload_to_cloudinary(cnic_back)
        selfie_url     = upload_to_cloudinary(selfie)

        encrypted_cnic = encrypt_field(cnic_number)
        encrypted_name = encrypt_field(full_name_on_card) if full_name_on_card else ''
        encrypted_dob  = encrypt_field(date_of_birth)     if date_of_birth     else ''

        kyc = KYC(
            user_id           = user_id,
            cnic_number       = encrypted_cnic,
            full_name_on_card = encrypted_name,
            date_of_birth     = encrypted_dob,
            cnic_front        = cnic_front_url,
            cnic_back         = cnic_back_url,
            selfie            = selfie_url,
            status            = 'pending',
        )
        db.session.add(kyc)
        db.session.commit()

        # ── In-app notification ──
        try:
            from routes.notifications import add_notification
            add_notification(
                user_id,
                title      = "KYC Documents Submitted",
                message    = "Your documents are under review. We'll notify you within 24 hours.",
                notif_type = 'info',
                icon       = 'shield'
            )
        except Exception as e:
            print(f"KYC notification error: {e}")

        # ── Email ──
        try:
            user = User.query.get(user_id)
            if user:
                send_kyc_submitted_email(user.email, user.full_name)
        except Exception as e:
            print(f"KYC submit email error: {e}")

        return jsonify({'message': 'KYC submitted successfully! Under review.'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Submission failed: {str(e)}'}), 500


@kyc_bp.route('/status', methods=['GET'])
@jwt_required()
def kyc_status():
    user_id = get_jwt_identity()
    kyc     = KYC.query.filter_by(user_id=user_id).first()

    if not kyc:
        return jsonify({'status': None}), 200

    return jsonify({
        'status':            kyc.status,
        'cnic_number':       decrypt_field(kyc.cnic_number)       if kyc.cnic_number       else '',
        'full_name_on_card': decrypt_field(kyc.full_name_on_card) if kyc.full_name_on_card else '',
        'date_of_birth':     decrypt_field(kyc.date_of_birth)     if kyc.date_of_birth     else '',
        'rejection_reason':  kyc.rejection_reason,
        'submitted_at':      str(kyc.submitted_at),
        'verified_at':       str(kyc.verified_at) if kyc.verified_at else None,
    }), 200


def approve_kyc_and_notify(kyc, user):
    kyc.status        = 'approved'
    kyc.verified_at   = datetime.utcnow()
    kyc.updated_at    = datetime.utcnow()
    user.kyc_verified = True
    db.session.commit()

    try:
        from routes.notifications import add_notification
        add_notification(
            user.id,
            title      = "KYC Approved!",
            message    = "Your identity has been verified. You can now send money and access all features.",
            notif_type = 'success',
            icon       = 'shield'
        )
    except Exception as e:
        print(f"KYC approve notification error: {e}")

    try:
        send_kyc_approved_email(user.email, user.full_name)
    except Exception as e:
        print(f"KYC approve email error: {e}")


def reject_kyc_and_notify(kyc, user, reason):
    kyc.status           = 'rejected'
    kyc.rejection_reason = reason
    kyc.updated_at       = datetime.utcnow()
    user.kyc_verified    = False
    db.session.commit()

    try:
        from routes.notifications import add_notification
        add_notification(
            user.id,
            title      = "KYC Not Approved",
            message    = f"Reason: {reason}. Please resubmit with correct documents.",
            notif_type = 'warning',
            icon       = 'warning'
        )
    except Exception as e:
        print(f"KYC reject notification error: {e}")

    try:
        send_kyc_rejected_email(user.email, user.full_name, reason)
    except Exception as e:
        print(f"KYC reject email error: {e}")