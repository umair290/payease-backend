from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, Wallet, Transaction, KYC
from datetime import datetime
import os
import resend

admin_bp = Blueprint("admin", __name__)

resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL', 'support@payease.space')


def is_admin(user_id):
    user = User.query.get(user_id)
    return user and user.is_admin


def send_kyc_email(email, full_name, status, reason=''):
    """Send KYC approval or rejection email to user"""
    now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')

    if status == 'approved':
        grad     = 'linear-gradient(135deg,#16A34A,#15803D)'
        icon     = '&#10003;'
        icon_bg  = '#DCFCE7'
        icon_col = '#16A34A'
        title    = 'KYC Verification Approved'
        subtitle = 'Your identity has been successfully verified'
        subject  = 'KYC Verification Approved — PayEase'
        body_html = '''
<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:18px;margin-bottom:20px;">
<p style="color:#15803D;font-size:14px;font-weight:600;margin:0 0 8px 0;">Your account is now fully verified.</p>
<p style="color:#166534;font-size:13px;margin:0;line-height:1.7;">
You now have full access to all PayEase features including:
</p>
<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
<tr><td style="padding:5px 0;font-size:13px;color:#166534;">&#10003; &nbsp; Send money to other wallets</td></tr>
<tr><td style="padding:5px 0;font-size:13px;color:#166534;">&#10003; &nbsp; Transfer up to PKR 50,000 per transaction</td></tr>
<tr><td style="padding:5px 0;font-size:13px;color:#166534;">&#10003; &nbsp; Pay utility bills and mobile top-ups</td></tr>
<tr><td style="padding:5px 0;font-size:13px;color:#166534;">&#10003; &nbsp; Full transaction history and statements</td></tr>
</table>
</div>'''
        warning_html = ''

    else:
        grad     = 'linear-gradient(135deg,#DC2626,#B91C1C)'
        icon     = '&#10007;'
        icon_bg  = '#FEE2E2'
        icon_col = '#DC2626'
        title    = 'KYC Verification Rejected'
        subtitle = 'Your identity verification could not be approved'
        subject  = 'KYC Verification Rejected — PayEase'
        reason_text = reason if reason else 'Documents were unclear or invalid'
        body_html = f'''
<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:12px;padding:18px;margin-bottom:20px;">
<p style="color:#DC2626;font-size:13px;font-weight:700;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:0.5px;">Rejection Reason</p>
<p style="color:#7F1D1D;font-size:13px;margin:0;line-height:1.7;">{reason_text}</p>
</div>

<div style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:12px;padding:18px;margin-bottom:20px;">
<p style="color:#92400E;font-size:13px;font-weight:700;margin:0 0 8px 0;">How to Resubmit</p>
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding:4px 0;font-size:13px;color:#78350F;">1. &nbsp; Ensure your CNIC images are clear and fully visible</td></tr>
<tr><td style="padding:4px 0;font-size:13px;color:#78350F;">2. &nbsp; Make sure your selfie shows your face clearly</td></tr>
<tr><td style="padding:4px 0;font-size:13px;color:#78350F;">3. &nbsp; Verify that your name and date of birth are correct</td></tr>
<tr><td style="padding:4px 0;font-size:13px;color:#78350F;">4. &nbsp; Login to PayEase and go to Profile &gt; KYC Verification</td></tr>
</table>
</div>'''
        warning_html = '''
<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:16px;">
<p style="color:#92400E;font-size:12px;font-weight:700;margin:0 0 4px 0;text-transform:uppercase;letter-spacing:0.5px;">Need Help?</p>
<p style="color:#78350F;font-size:13px;margin:0;line-height:1.6;">
If you believe this rejection is an error, please contact our support team at support@payease.space with your account details.
</p>
</div>'''

    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

<tr><td style="background:{grad};padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;letter-spacing:-0.5px;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Identity Verification</p>
</td></tr>

<tr><td style="padding:32px;">
<div style="text-align:center;margin-bottom:28px;">
  <div style="width:64px;height:64px;border-radius:50%;background:{icon_bg};margin:0 auto 14px auto;text-align:center;line-height:64px;font-size:32px;color:{icon_col};">{icon}</div>
  <h2 style="color:#1A1A2E;font-size:22px;font-weight:bold;margin:0 0 6px 0;">{title}</h2>
  <p style="color:#6B7280;font-size:13px;margin:0;">{subtitle}</p>
</div>

<table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;border-radius:14px;overflow:hidden;border:1px solid #E5E7EB;margin-bottom:24px;">
<tr style="background:#F3F4F6;">
  <td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Verification Details</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Account Holder</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{full_name}</td>
</tr>
<tr style="border-bottom:1px solid #E5E7EB;">
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Status</td>
  <td style="padding:12px 16px;text-align:right;">
    <span style="background:{"#DCFCE7" if status == "approved" else "#FEE2E2"};color:{"#065F46" if status == "approved" else "#7F1D1D"};font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;text-transform:uppercase;letter-spacing:0.5px;">{"Approved" if status == "approved" else "Rejected"}</span>
  </td>
</tr>
<tr>
  <td style="padding:12px 16px;font-size:13px;color:#6B7280;">Date and Time</td>
  <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{now}</td>
</tr>
</table>

{body_html}
{warning_html}

</td></tr>

<tr><td style="background:#F9FAFB;border-top:1px solid #E5E7EB;padding:20px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#9CA3AF;font-size:11px;margin:0;">payease.space &nbsp;|&nbsp; support@payease.space</p>
<p style="color:#9CA3AF;font-size:10px;margin:6px 0 0 0;">This is an automated message. Please do not reply to this email.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''

    try:
        resend.Emails.send({
            "from":    f"PayEase <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": subject,
            "html":    html,
        })
        print(f"KYC {status} email sent to {email}")
        return True
    except Exception as e:
        print(f"KYC email error: {e}")
        return False


# ──────────────────────────────────────────
# ADMIN ROUTES
# ──────────────────────────────────────────

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
    total_volume       = db.session.query(db.func.sum(Transaction.amount)).scalar() or 0

    return jsonify({
        "total_users":        total_users,
        "total_transactions": total_transactions,
        "pending_kyc":        pending_kyc,
        "blocked_users":      blocked_users,
        "total_volume":       round(total_volume, 2)
    }), 200


@admin_bp.route("/users", methods=["GET"])
@jwt_required()
def get_all_users():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    users  = User.query.all()
    result = []
    for user in users:
        wallet    = Wallet.query.filter_by(user_id=user.id).first()
        user_dict = user.to_dict()
        user_dict["balance"] = round(wallet.balance, 2) if wallet else 0
        result.append(user_dict)

    return jsonify({"total": len(result), "users": result}), 200


@admin_bp.route("/block-user", methods=["POST"])
@jwt_required()
def block_user():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data         = request.get_json()
    target_id    = data.get("user_id")
    block_status = data.get("block", True)

    target = User.query.get(target_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    target.is_blocked = block_status
    db.session.commit()

    action = "blocked" if block_status else "unblocked"
    return jsonify({"message": f"User {action} successfully"}), 200


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

    return jsonify({"total": len(result), "kyc_list": result}), 200


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

    user              = User.query.get(kyc.user_id)
    user.kyc_verified = True
    db.session.commit()

    # Send KYC approval email
    try:
        send_kyc_email(user.email, user.full_name, 'approved')
    except Exception as e:
        print(f"KYC approval email error: {e}")

    # Send in-app notification
    try:
        from routes.notifications import add_notification
        add_notification(
            user.id,
            'KYC Verification Approved',
            'Your identity has been verified. You now have full access to all PayEase features.',
            'success', 'kyc'
        )
    except Exception as e:
        print(f"KYC notification error: {e}")

    return jsonify({"message": "KYC approved successfully"}), 200


@admin_bp.route("/kyc/reject", methods=["POST"])
@jwt_required()
def reject_kyc():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data             = request.get_json()
    kyc_id           = data.get("kyc_id")
    rejection_reason = data.get("reason", "Documents were unclear or invalid")

    kyc = KYC.query.get(kyc_id)
    if not kyc:
        return jsonify({"error": "KYC record not found"}), 404

    kyc.status           = "rejected"
    kyc.rejection_reason = rejection_reason

    user = User.query.get(kyc.user_id)
    db.session.commit()

    # Send KYC rejection email
    try:
        send_kyc_email(user.email, user.full_name, 'rejected', rejection_reason)
    except Exception as e:
        print(f"KYC rejection email error: {e}")

    # Send in-app notification
    try:
        from routes.notifications import add_notification
        add_notification(
            user.id,
            'KYC Verification Rejected',
            f'Your KYC was rejected. Reason: {rejection_reason}. Please resubmit with valid documents.',
            'error', 'kyc'
        )
    except Exception as e:
        print(f"KYC notification error: {e}")

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
