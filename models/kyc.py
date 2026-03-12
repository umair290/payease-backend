from extensions import db
from datetime import datetime

class KYC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    cnic_number = db.Column(db.String(20), unique=True, nullable=False)
    cnic_front = db.Column(db.String(255))
    cnic_back = db.Column(db.String(255))
    selfie = db.Column(db.String(255))
    status = db.Column(db.String(20), default="pending")
    rejection_reason = db.Column(db.String(255))
    submitted_at = db.Column(db.DateTime, default = datetime.utcnow)
    verified_at = db.Column(db.DateTime)



    def to_dict(self):
        return{
            "id": self.id,
            "cnic_number": self.cnic_number,
            "cnic_front": self.cnic_front,
            "cnic_back": self.cnic_back,
            "selfie": self.selfie,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "submitted-at": str(self.submitted_at),
            "verified_at": str(self.verified_at) if self.verified_at else None

        } 