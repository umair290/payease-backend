from extensions import db
from datetime import datetime

class KYC(db.Model):
    __tablename__ = "kyc"

    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)

    # Sensitive fields — store as-is for now
    # (encrypt these in a later phase using Fernet)
    cnic_number       = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name_on_card = db.Column(db.String(100), nullable=True)
    date_of_birth     = db.Column(db.String(20),  nullable=True)

    # Cloudinary URLs for uploaded documents
    cnic_front        = db.Column(db.String(500), nullable=True)
    cnic_back         = db.Column(db.String(500), nullable=True)
    selfie            = db.Column(db.String(500), nullable=True)

    # Status: pending | approved | rejected
    status            = db.Column(db.String(20), default="pending", nullable=False, index=True)
    rejection_reason  = db.Column(db.String(500), nullable=True)

    submitted_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    verified_at       = db.Column(db.DateTime, nullable=True)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id":                 self.id,
            "user_id":            self.user_id,
            "cnic_number":        self.cnic_number,
            "full_name_on_card":  self.full_name_on_card,
            "date_of_birth":      self.date_of_birth,
            "cnic_front":         self.cnic_front,
            "cnic_back":          self.cnic_back,
            "selfie":             self.selfie,
            "status":             self.status,
            "rejection_reason":   self.rejection_reason,
            "submitted_at":       str(self.submitted_at),  # fixed: was "submitted-at"
            "verified_at":        str(self.verified_at) if self.verified_at else None,
        }