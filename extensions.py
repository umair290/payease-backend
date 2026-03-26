import os
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── Extensions ──
db      = SQLAlchemy()
jwt     = JWTManager()
limiter = Limiter(
    key_func       = get_remote_address,
    default_limits = ["200 per hour", "50 per minute"],
    storage_uri    = "memory://",
)

# ── JWT: token blocklist check ──
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    from models.token_blocklist import TokenBlocklist
    jti   = jwt_payload["jti"]
    token = TokenBlocklist.query.filter_by(jti=jti).first()
    return token is not None

# ── JWT: custom error responses ──
@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    from flask import jsonify
    return jsonify({"error": "Token has been revoked. Please log in again."}), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    from flask import jsonify
    return jsonify({"error": "Token has expired. Please log in again."}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    from flask import jsonify
    return jsonify({"error": "Invalid token. Please log in again."}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    from flask import jsonify
    return jsonify({"error": "No token provided. Please log in."}), 401