from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, Wallet, Transaction, KYC
from models.audit_log import AuditLog
from datetime import datetime
import os
import resend
from utils.encryption import encrypt_field, decrypt_field
from utils.sanitize import clean, clean_name, clean_phone, clean_cnic, clean_date

admin_bp = Blueprint("admin", __name__)

resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL', 'support@payease.space')

# ── Change requests still in-memory (no sensitive data) ──
change_requests = []


def is_admin(user_id):
    user = User.query.get(user_id)
    return user and user.is_admin


def add_log(user_id, action, detail, ip='N/A', admin_id=None, user_agent=None):
    """
    Persist audit log to PostgreSQL.
    Falls back silently — never breaks the main flow.
    """
    try:
        log = AuditLog(
            user_id    = user_id,
            admin_id   = admin_id,
            action     = str(action)[:100],
            detail     = str(detail)[:2000] if detail else None,
            ip         = str(ip)[:45]       if ip and ip != 'N/A' else None,
            user_agent = str(user_agent)[:255] if user_agent else None,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Audit log error (non-critical): {e}")
        try:
            db.session.rollback()
        except Exception:
            pass


def kyc_to_dict_decrypted(kyc, user):
    return {
        'id':                kyc.id,
        'user_id':           kyc.user_id,
        'cnic_number':       decrypt_field(kyc.cnic_number),
        'full_name_on_card': decrypt_field(kyc.full_name_on_card) if kyc.full_name_on_card else '',
        'date_of_birth':     decrypt_field(kyc.date_of_birth)     if kyc.date_of_birth     else '',
        'cnic_front':        kyc.cnic_front,
        'cnic_back':         kyc.cnic_back,
        'selfie':            kyc.selfie,
        'status':            kyc.status,
        'rejection_reason':  kyc.rejection_reason,
        'submitted_at':      str(kyc.submitted_at),
        'verified_at':       str(kyc.verified_at) if kyc.verified_at else None,
        'user': {
            'full_name': user.full_name,
            'email':     user.email,
            'phone':     user.phone,
        }
    }


# ──────────────────────────────────────────
# EMAIL FUNCTIONS
# ──────────────────────────────────────────

def send_kyc_email(email, full_name, status, reason=''):
    now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    if status == 'approved':
        grad      = 'linear-gradient(135deg,#16A34A,#15803D)'
        icon      = '&#10003;'
        icon_bg   = '#DCFCE7'
        icon_col  = '#16A34A'
        title     = 'KYC Verification Approved'
        subtitle  = 'Your identity has been successfully verified'
        subject   = 'KYC Verification Approved — PayEase'
        body_html = '''
<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:18px;margin-bottom:20px;">
<p style="color:#15803D;font-size:14px;font-weight:600;margin:0 0 8px 0;">Your account is now fully verified.</p>
<p style="color:#166534;font-size:13px;margin:0;line-height:1.7;">You now have full access to all PayEase features.</p>
</div>'''
        warning_html = ''
    else:
        grad      = 'linear-gradient(135deg,#DC2626,#B91C1C)'
        icon      = '&#10007;'
        icon_bg   = '#FEE2E2'
        icon_col  = '#DC2626'
        title     = 'KYC Verification Rejected'
        subtitle  = 'Your identity verification could not be approved'
        subject   = 'KYC Verification Rejected — PayEase'
        reason_text = reason if reason else 'Documents were unclear or invalid'
        body_html = f'''
<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:12px;padding:18px;margin-bottom:20px;">
<p style="color:#DC2626;font-size:13px;font-weight:700;margin:0 0 6px 0;">Rejection Reason</p>
<p style="color:#7F1D1D;font-size:13px;margin:0;line-height:1.7;">{reason_text}</p>
</div>'''
        warning_html = '''
<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:16px;">
<p style="color:#92400E;font-size:12px;font-weight:700;margin:0 0 4px 0;">Need Help?</p>
<p style="color:#78350F;font-size:13px;margin:0;line-height:1.6;">Contact support at support@payease.space</p>
</div>'''

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:{grad};padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Identity Verification</p>
</td></tr>
<tr><td style="padding:32px;">
<div style="text-align:center;margin-bottom:28px;">
  <div style="width:64px;height:64px;border-radius:50%;background:{icon_bg};margin:0 auto 14px auto;text-align:center;line-height:64px;font-size:32px;color:{icon_col};">{icon}</div>
  <h2 style="color:#1A1A2E;font-size:22px;font-weight:bold;margin:0 0 6px 0;">{title}</h2>
  <p style="color:#6B7280;font-size:13px;margin:0;">{subtitle}</p>
</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;border-radius:14px;overflow:hidden;border:1px solid #E5E7EB;margin-bottom:24px;">
<tr style="background:#F3F4F6;"><td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Verification Details</td></tr>
<tr style="border-bottom:1px solid #E5E7EB;"><td style="padding:12px 16px;font-size:13px;color:#6B7280;">Account Holder</td><td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{full_name}</td></tr>
<tr style="border-bottom:1px solid #E5E7EB;"><td style="padding:12px 16px;font-size:13px;color:#6B7280;">Status</td><td style="padding:12px 16px;text-align:right;"><span style="background:{"#DCFCE7" if status == "approved" else "#FEE2E2"};color:{"#065F46" if status == "approved" else "#7F1D1D"};font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;">{"Approved" if status == "approved" else "Rejected"}</span></td></tr>
<tr><td style="padding:12px 16px;font-size:13px;color:#6B7280;">Date and Time</td><td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{now}</td></tr>
</table>
{body_html}{warning_html}
</td></tr>
<tr><td style="background:#F9FAFB;border-top:1px solid #E5E7EB;padding:20px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#9CA3AF;font-size:11px;margin:0;">payease.space | support@payease.space</p>
</td></tr>
</table></td></tr></table></body></html>'''

    try:
        resend.Emails.send({
            "from": f"PayEase <{SENDER_EMAIL}>", "to": [email],
            "subject": subject, "html": html,
        })
        return True
    except Exception as e:
        print(f"KYC email error: {e}")
        return False


def send_account_deleted_email(email, full_name, reason=''):
    now  = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#DC2626,#B91C1C);padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Account Notification</p>
</td></tr>
<tr><td style="padding:32px;">
<div style="text-align:center;margin-bottom:24px;">
  <div style="width:64px;height:64px;border-radius:50%;background:#FEE2E2;margin:0 auto 14px auto;text-align:center;line-height:64px;font-size:28px;color:#DC2626;">&#10007;</div>
  <h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 6px 0;">Account Deleted</h2>
  <p style="color:#6B7280;font-size:13px;margin:0;">Your PayEase account has been permanently deleted</p>
</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;border-radius:14px;overflow:hidden;border:1px solid #E5E7EB;margin-bottom:24px;">
<tr style="background:#F3F4F6;"><td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Deletion Details</td></tr>
<tr style="border-bottom:1px solid #E5E7EB;"><td style="padding:12px 16px;font-size:13px;color:#6B7280;">Account</td><td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{full_name}</td></tr>
<tr style="border-bottom:1px solid #E5E7EB;"><td style="padding:12px 16px;font-size:13px;color:#6B7280;">Email</td><td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{email}</td></tr>
<tr style="border-bottom:1px solid #E5E7EB;"><td style="padding:12px 16px;font-size:13px;color:#6B7280;">Reason</td><td style="padding:12px 16px;font-size:13px;font-weight:600;color:#DC2626;text-align:right;">{reason if reason else "Policy violation"}</td></tr>
<tr><td style="padding:12px 16px;font-size:13px;color:#6B7280;">Date and Time</td><td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{now}</td></tr>
</table>
<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:12px;padding:16px;">
<p style="color:#7F1D1D;font-size:13px;margin:0;line-height:1.7;">
Your PayEase account and all associated data have been permanently deleted by an administrator.
If you believe this was a mistake, please contact us at support@payease.space
</p>
</div>
</td></tr>
<tr><td style="background:#F9FAFB;border-top:1px solid #E5E7EB;padding:20px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#9CA3AF;font-size:11px;margin:0;">payease.space | support@payease.space</p>
</td></tr>
</table></td></tr></table></body></html>'''

    try:
        resend.Emails.send({
            "from": f"PayEase <{SENDER_EMAIL}>", "to": [email],
            "subject": "Account Deleted — PayEase", "html": html,
        })
        return True
    except Exception as e:
        print(f"Deletion email error: {e}")
        return False


def send_admin_update_email(email, full_name, changes, reason=''):
    now          = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    changes_html = ''.join([
        f'<tr style="border-bottom:1px solid #E5E7EB;"><td style="padding:12px 16px;font-size:13px;color:#6B7280;">{k}</td><td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{v}</td></tr>'
        for k, v in changes.items()
    ])
    reason_html = f"<div style='background:#FFFBEB;border:1px solid #FDE68A;border-radius:12px;padding:16px;margin-bottom:20px;'><p style='color:#92400E;font-size:12px;font-weight:700;margin:0 0 4px 0;'>Reason</p><p style='color:#78350F;font-size:13px;margin:0;line-height:1.6;'>{reason}</p></div>" if reason else ""

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#7C3AED,#5B21B6);padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Account Update</p>
</td></tr>
<tr><td style="padding:32px;">
<div style="text-align:center;margin-bottom:24px;">
  <div style="width:64px;height:64px;border-radius:50%;background:#EDE9FE;margin:0 auto 14px auto;text-align:center;line-height:64px;font-size:28px;color:#7C3AED;">&#10003;</div>
  <h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 6px 0;">Account Information Updated</h2>
  <p style="color:#6B7280;font-size:13px;margin:0;">An administrator has updated your account information</p>
</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;border-radius:14px;overflow:hidden;border:1px solid #E5E7EB;margin-bottom:24px;">
<tr style="background:#F3F4F6;"><td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Changes Made</td></tr>
{changes_html}
<tr><td style="padding:12px 16px;font-size:13px;color:#6B7280;">Date and Time</td><td style="padding:12px 16px;font-size:13px;font-weight:600;color:#111827;text-align:right;">{now}</td></tr>
</table>
{reason_html}
<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:16px;">
<p style="color:#15803D;font-size:13px;margin:0;line-height:1.6;">
If you did not request this change or believe it is incorrect, please contact support@payease.space immediately.
</p>
</div>
</td></tr>
<tr><td style="background:#F9FAFB;border-top:1px solid #E5E7EB;padding:20px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#9CA3AF;font-size:11px;margin:0;">payease.space | support@payease.space</p>
</td></tr>
</table></td></tr></table></body></html>'''

    try:
        resend.Emails.send({
            "from": f"PayEase <{SENDER_EMAIL}>", "to": [email],
            "subject": "Account Information Updated by Admin — PayEase", "html": html,
        })
        return True
    except Exception as e:
        print(f"Admin update email error: {e}")
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
        "total_volume":       round(float(total_volume), 2)
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
        user_dict['balance']       = round(float(wallet.balance), 2) if wallet else 0
        user_dict['wallet_number'] = wallet.wallet_number if wallet else None
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
    if target.is_admin:
        return jsonify({"error": "Cannot block admin accounts"}), 403

    target.is_blocked = block_status
    db.session.commit()

    action = "blocked" if block_status else "unblocked"
    ip     = request.headers.get("X-Forwarded-For", request.remote_addr or "Unknown").split(",")[0].strip()

    add_log(
        target_id, f'Account {action}',
        f'Account was {action} by administrator',
        ip       = ip,
        admin_id = int(user_id)
    )

    try:
        from routes.notifications import add_notification
        add_notification(
            target_id, f'Account {action.capitalize()}',
            f'Your account has been {action} by an administrator. Contact support if needed.',
            'warning' if block_status else 'success', 'admin'
        )
    except Exception as e:
        print(f"Notification error: {e}")

    return jsonify({"message": f"User {action} successfully"}), 200


@admin_bp.route("/delete-user", methods=["POST"])
@jwt_required()
def delete_user():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data      = request.get_json()
    target_id = data.get("user_id")
    reason    = clean(data.get("reason", "Policy violation"), 500)

    if not target_id:
        return jsonify({"error": "User ID is required"}), 400

    target = User.query.get(target_id)
    if not target:
        return jsonify({"error": "User not found"}), 404
    if target.is_admin:
        return jsonify({"error": "Cannot delete admin accounts"}), 403

    target_email = target.email
    target_name  = target.full_name
    ip           = request.headers.get("X-Forwarded-For", request.remote_addr or "Unknown").split(",")[0].strip()

    try:
        wallet = Wallet.query.filter_by(user_id=target_id).first()
        if wallet:
            Transaction.query.filter(
                (Transaction.from_wallet == wallet.wallet_number) |
                (Transaction.to_wallet   == wallet.wallet_number)
            ).delete(synchronize_session=False)
            db.session.delete(wallet)

        kyc = KYC.query.filter_by(user_id=target_id).first()
        if kyc:
            db.session.delete(kyc)

        db.session.delete(target)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    try:
        send_account_deleted_email(target_email, target_name, reason)
    except Exception as e:
        print(f"Deletion email error: {e}")

    add_log(
        int(user_id), 'User Deleted',
        f'Deleted account: {target_email} — Reason: {reason}',
        ip       = ip,
        admin_id = int(user_id)
    )

    return jsonify({"message": f"User {target_name} deleted successfully"}), 200


@admin_bp.route("/update-user", methods=["POST"])
@jwt_required()
def update_user():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data      = request.get_json()
    target_id = data.get("user_id")
    reason    = clean(data.get("reason", "Admin correction"), 500)

    if not target_id:
        return jsonify({"error": "User ID is required"}), 400

    target = User.query.get(target_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    changes = {}
    ip      = request.headers.get("X-Forwarded-For", request.remote_addr or "Unknown").split(",")[0].strip()

    if data.get("full_name") and clean_name(data["full_name"]):
        new_name = clean_name(data["full_name"])
        old = target.full_name
        target.full_name = new_name
        if old != new_name:
            changes["Full Name"] = f"{old} → {new_name}"

    if data.get("phone") and clean_phone(data["phone"]):
        new_phone = clean_phone(data["phone"])
        existing  = User.query.filter_by(phone=new_phone).first()
        if existing and existing.id != int(target_id):
            return jsonify({"error": "Phone number already in use"}), 409
        old = target.phone
        target.phone = new_phone
        if old != new_phone:
            changes["Phone"] = f"{old} → {new_phone}"

    kyc = KYC.query.filter_by(user_id=target_id).first()
    if kyc:
        if data.get("date_of_birth"):
            new_dob = clean_date(data["date_of_birth"])
            if new_dob:
                old = decrypt_field(kyc.date_of_birth) if kyc.date_of_birth else 'Not set'
                kyc.date_of_birth = encrypt_field(new_dob)
                changes["Date of Birth"] = f"{old} → {new_dob}"

        if data.get("cnic_number"):
            new_cnic = clean_cnic(data["cnic_number"])
            if new_cnic:
                old = decrypt_field(kyc.cnic_number) if kyc.cnic_number else 'Not set'
                kyc.cnic_number = encrypt_field(new_cnic)
                changes["CNIC Number"] = f"{old} → {new_cnic}"

        if data.get("full_name_on_card"):
            new_card_name = clean_name(data["full_name_on_card"], 100)
            if new_card_name:
                old = decrypt_field(kyc.full_name_on_card) if kyc.full_name_on_card else 'Not set'
                kyc.full_name_on_card = encrypt_field(new_card_name)
                changes["Name on Card"] = f"{old} → {new_card_name}"

    if not changes:
        return jsonify({"error": "No valid changes provided"}), 400

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    try:
        send_admin_update_email(target.email, target.full_name, changes, reason)
    except Exception as e:
        print(f"Update email error: {e}")

    try:
        from routes.notifications import add_notification
        add_notification(
            int(target_id), 'Account Information Updated',
            f'An administrator has updated your account: {", ".join(changes.keys())}. A confirmation email has been sent.',
            'info', 'admin'
        )
    except Exception as e:
        print(f"Notification error: {e}")

    add_log(
        int(target_id), 'User Updated',
        f'Updated {target.email}: {", ".join(changes.keys())} — Reason: {reason}',
        ip       = ip,
        admin_id = int(user_id)
    )

    return jsonify({"message": "User updated successfully", "changes": changes}), 200


@admin_bp.route("/logs", methods=["GET"])
@jwt_required()
def get_logs():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    filter_user   = request.args.get("user_id")
    filter_action = request.args.get("action", "").lower()
    limit         = min(int(request.args.get("limit", 500)), 1000)

    query = AuditLog.query.order_by(AuditLog.created_at.desc())

    if filter_user:
        query = query.filter(AuditLog.user_id == int(filter_user))
    if filter_action:
        query = query.filter(AuditLog.action.ilike(f'%{filter_action}%'))

    logs = query.limit(limit).all()

    return jsonify({"total": len(logs), "logs": [l.to_dict() for l in logs]}), 200


@admin_bp.route("/logs/add", methods=["POST"])
@jwt_required()
def log_activity():
    user_id    = get_jwt_identity()
    data       = request.get_json()
    action     = clean(data.get("action", "Unknown"), 100)
    detail     = clean(data.get("detail", ""),        500)
    ip         = request.headers.get("X-Forwarded-For", request.remote_addr or "Unknown").split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "")[:255]

    add_log(int(user_id), action, detail, ip=ip, user_agent=user_agent)
    return jsonify({"message": "Logged"}), 200


@admin_bp.route("/change-requests", methods=["GET"])
@jwt_required()
def get_change_requests():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403
    return jsonify({"total": len(change_requests), "requests": list(reversed(change_requests))}), 200


@admin_bp.route("/change-requests/submit", methods=["POST"])
@jwt_required()
def submit_change_request():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    data    = request.get_json()

    field  = clean(data.get("field",  ""), 50)
    value  = clean(data.get("value",  ""), 255)
    reason = clean(data.get("reason", ""), 500)

    if not field or not value or not reason:
        return jsonify({"error": "Field, value, and reason are required"}), 400

    allowed_fields = ["date_of_birth", "cnic_number", "full_name_on_card", "full_name", "phone"]
    if field not in allowed_fields:
        return jsonify({"error": f"Field '{field}' cannot be changed via request"}), 400

    change_requests.append({
        "id":           len(change_requests) + 1,
        "user_id":      user_id,
        "user_name":    user.full_name,
        "user_email":   user.email,
        "field":        field,
        "new_value":    value,
        "reason":       reason,
        "status":       "pending",
        "submitted_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    })

    return jsonify({"message": "Change request submitted. Admin will review it shortly."}), 200


@admin_bp.route("/change-requests/approve", methods=["POST"])
@jwt_required()
def approve_change_request():
    admin_id   = get_jwt_identity()
    if not is_admin(admin_id):
        return jsonify({"error": "Admin access required"}), 403

    data       = request.get_json()
    request_id = data.get("request_id")

    req = next((r for r in change_requests if r["id"] == request_id), None)
    if not req:
        return jsonify({"error": "Request not found"}), 404
    if req["status"] != "pending":
        return jsonify({"error": "Request already processed"}), 400

    result = update_user_field(req["user_id"], req["field"], req["new_value"])
    if not result:
        return jsonify({"error": "Failed to apply change"}), 500

    req["status"]       = "approved"
    req["processed_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    try:
        user = User.query.get(req["user_id"])
        from routes.notifications import add_notification
        add_notification(
            req["user_id"], 'Change Request Approved',
            f'Your request to update {req["field"].replace("_", " ").title()} has been approved.',
            'success', 'admin'
        )
        send_admin_update_email(
            user.email, user.full_name,
            {req["field"].replace("_", " ").title(): req["new_value"]},
            "Approved based on your request"
        )
    except Exception as e:
        print(f"Notification error: {e}")

    add_log(
        req["user_id"], 'Change Request Approved',
        f'Field {req["field"]} updated to: {req["new_value"]}',
        admin_id = int(admin_id)
    )

    return jsonify({"message": "Change request approved and applied"}), 200


@admin_bp.route("/change-requests/reject", methods=["POST"])
@jwt_required()
def reject_change_request():
    admin_id   = get_jwt_identity()
    if not is_admin(admin_id):
        return jsonify({"error": "Admin access required"}), 403

    data       = request.get_json()
    request_id = data.get("request_id")
    reason     = clean(data.get("reason", "Request could not be approved"), 500)

    req = next((r for r in change_requests if r["id"] == request_id), None)
    if not req:
        return jsonify({"error": "Request not found"}), 404

    req["status"]        = "rejected"
    req["reject_reason"] = reason
    req["processed_at"]  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    try:
        from routes.notifications import add_notification
        add_notification(
            req["user_id"], 'Change Request Rejected',
            f'Your request to update {req["field"].replace("_", " ").title()} was rejected. Reason: {reason}',
            'error', 'admin'
        )
    except Exception as e:
        print(f"Notification error: {e}")

    add_log(
        req["user_id"], 'Change Request Rejected',
        f'Request for field {req["field"]} rejected — {reason}',
        admin_id = int(admin_id)
    )

    return jsonify({"message": "Change request rejected"}), 200


def update_user_field(user_id, field, value):
    try:
        user = User.query.get(user_id)
        kyc  = KYC.query.filter_by(user_id=user_id).first()

        if field == "full_name" and user:
            user.full_name = clean_name(value)
        elif field == "phone" and user:
            clean_ph = clean_phone(value)
            existing = User.query.filter_by(phone=clean_ph).first()
            if existing and existing.id != int(user_id):
                return False
            user.phone = clean_ph
        elif field == "date_of_birth" and kyc:
            kyc.date_of_birth     = encrypt_field(clean_date(value))
        elif field == "cnic_number" and kyc:
            kyc.cnic_number       = encrypt_field(clean_cnic(value))
        elif field == "full_name_on_card" and kyc:
            kyc.full_name_on_card = encrypt_field(clean_name(value, 100))

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Update field error: {e}")
        return False


@admin_bp.route("/kyc/pending", methods=["GET"])
@jwt_required()
def pending_kyc():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    kyc_list = KYC.query.filter_by(status="pending").all()
    result   = []
    for kyc in kyc_list:
        user = User.query.get(kyc.user_id)
        result.append(kyc_to_dict_decrypted(kyc, user))

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

    kyc.status        = "approved"
    kyc.verified_at   = datetime.utcnow()
    user              = User.query.get(kyc.user_id)
    user.kyc_verified = True
    db.session.commit()

    try: send_kyc_email(user.email, user.full_name, 'approved')
    except Exception as e: print(f"KYC approval email error: {e}")

    try:
        from routes.notifications import add_notification
        add_notification(user.id, 'KYC Verification Approved',
            'Your identity has been verified. You now have full access to all PayEase features.',
            'success', 'kyc')
    except Exception as e:
        print(f"KYC notification error: {e}")

    add_log(
        user.id, 'KYC Approved',
        f'KYC approved for {user.email}',
        admin_id = int(user_id)
    )
    return jsonify({"message": "KYC approved successfully"}), 200


@admin_bp.route("/kyc/reject", methods=["POST"])
@jwt_required()
def reject_kyc():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data             = request.get_json()
    kyc_id           = data.get("kyc_id")
    rejection_reason = clean(data.get("reason", "Documents were unclear or invalid"), 500)

    kyc = KYC.query.get(kyc_id)
    if not kyc:
        return jsonify({"error": "KYC record not found"}), 404

    kyc.status           = "rejected"
    kyc.rejection_reason = rejection_reason
    user                 = User.query.get(kyc.user_id)
    db.session.commit()

    try: send_kyc_email(user.email, user.full_name, 'rejected', rejection_reason)
    except Exception as e: print(f"KYC rejection email error: {e}")

    try:
        from routes.notifications import add_notification
        add_notification(user.id, 'KYC Verification Rejected',
            f'Your KYC was rejected. Reason: {rejection_reason}. Please resubmit with valid documents.',
            'error', 'kyc')
    except Exception as e:
        print(f"KYC notification error: {e}")

    add_log(
        user.id, 'KYC Rejected',
        f'KYC rejected for {user.email} — {rejection_reason}',
        admin_id = int(user_id)
    )
    return jsonify({"message": "KYC rejected", "reason": rejection_reason}), 200


@admin_bp.route("/transactions", methods=["GET"])
@jwt_required()
def all_transactions():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    transactions = Transaction.query.order_by(
        Transaction.created_at.desc()
    ).limit(200).all()

    return jsonify({
        "total":        len(transactions),
        "transactions": [t.to_dict() for t in transactions]
    }), 200