from extensions import db
from datetime import datetime

class User(db.Model):
    __tablename__ = "users"

    id               = db.Column(db.Integer, primary_key=True)
    full_name        = db.Column(db.String(100), nullable=False)
    email            = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone            = db.Column(db.String(20),  unique=True, nullable=False, index=True)
    password         = db.Column(db.String(255), nullable=False)
    pin              = db.Column(db.String(255), nullable=False)

    # Status flags
    is_blocked       = db.Column(db.Boolean, default=False, nullable=False)
    is_admin         = db.Column(db.Boolean, default=False, nullable=False)
    kyc_verified     = db.Column(db.Boolean, default=False, nullable=False)

    # New device detection
    last_device_hash = db.Column(db.String(32), nullable=True)

    # Onboarding — stored in DB so it works across all devices
    onboarding_done  = db.Column(db.Boolean, default=False, nullable=False)

    # Avatar — Cloudinary URL
    avatar_url       = db.Column(db.String(500), nullable=True)

    # Beneficiaries — JSON array stored as text, max 10
    beneficiaries    = db.Column(db.Text, default='[]', nullable=False)

    # Login tracking
    last_login_at    = db.Column(db.DateTime, nullable=True)
    login_count      = db.Column(db.Integer,  default=0, nullable=False)

    # Timestamps
    created_at       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    wallet       = db.relationship("Wallet",      backref="user", uselist=False, cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", backref="user", cascade="all, delete-orphan")
    kyc          = db.relationship("KYC",         backref="user", uselist=False, cascade="all, delete-orphan")
    bills        = db.relationship("Bill",        backref="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":               self.id,
            "full_name":        self.full_name,
            "email":            self.email,
            "phone":            self.phone,
            "is_admin":         self.is_admin,
            "is_blocked":       self.is_blocked,
            "kyc_verified":     self.kyc_verified,
            "onboarding_done":  self.onboarding_done,
            "avatar_url":       self.avatar_url,
            "last_login_at":    str(self.last_login_at) if self.last_login_at else None,
            "login_count":      self.login_count,
            "created_at":       str(self.created_at),
        }