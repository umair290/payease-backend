from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User
from datetime import datetime
import json

whitelabel_bp = Blueprint('whitelabel', __name__)

DEFAULT_FEATURES = {
    'bills':        True,
    'bill_split':   True,
    'virtual_card': True,
    'qr_code':      True,
    'insights':     True,
    'kyc_required': True,
}

def is_admin(user_id):
    user = User.query.get(user_id)
    return user and user.is_admin

def _get_or_create_config():
    from models.whitelabel import WhitelabelConfig
    cfg = WhitelabelConfig.query.first()
    if not cfg:
        cfg = WhitelabelConfig(features=json.dumps(DEFAULT_FEATURES))
        db.session.add(cfg)
        db.session.commit()
    return cfg


@whitelabel_bp.route("/whitelabel", methods=["GET"])
@jwt_required()
def get_whitelabel():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Forbidden"}), 403
    cfg = _get_or_create_config()
    return jsonify({"config": cfg.to_dict()}), 200


@whitelabel_bp.route("/whitelabel", methods=["POST"])
@jwt_required()
def save_whitelabel():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    cfg  = _get_or_create_config()

    if 'app_name'        in data: cfg.app_name        = (data['app_name'] or 'PayEase').strip()[:100]
    if 'tagline'         in data: cfg.tagline          = (data['tagline'] or '').strip()[:200]
    if 'logo_url'        in data: cfg.logo_url         = (data['logo_url'] or '').strip()[:500] or None
    if 'favicon_url'     in data: cfg.favicon_url      = (data['favicon_url'] or '').strip()[:500] or None
    if 'primary_color'   in data: cfg.primary_color    = (data['primary_color'] or '#1A73E8').strip()[:20]
    if 'secondary_color' in data: cfg.secondary_color  = (data['secondary_color'] or '#7C3AED').strip()[:20]
    if 'accent_color'    in data: cfg.accent_color     = (data['accent_color'] or '#16A34A').strip()[:20]
    if 'support_email'   in data: cfg.support_email    = (data['support_email'] or '').strip()[:200]
    if 'website_url'     in data: cfg.website_url      = (data['website_url'] or '').strip()[:300]
    if 'features'        in data: cfg.features         = json.dumps({**DEFAULT_FEATURES, **data['features']})

    cfg.updated_by = user_id
    cfg.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Saved", "config": cfg.to_dict()}), 200


@whitelabel_bp.route("/whitelabel/upload-logo", methods=["POST"])
@jwt_required()
def upload_whitelabel_logo():
    user_id = get_jwt_identity()
    if not is_admin(user_id):
        return jsonify({"error": "Forbidden"}), 403

    if 'logo' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['logo']
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    try:
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            file,
            folder        = "payease/whitelabel",
            public_id     = "logo",
            overwrite     = True,
            resource_type = "image",
        )
        logo_url = result.get('secure_url')
        cfg = _get_or_create_config()
        cfg.logo_url   = logo_url
        cfg.updated_by = user_id
        cfg.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"logo_url": logo_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500