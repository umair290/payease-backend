from extensions import db
from datetime import datetime
from sqlalchemy import Numeric

class Bill(db.Model):
    __tablename__ = "bills"   # FIXED: was __tablename (missing underscores)

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_type  = db.Column(db.String(50),  nullable=False, index=True)
    provider   = db.Column(db.String(100), nullable=False)

    # Numeric for money
    amount     = db.Column(Numeric(precision=12, scale=2), nullable=False)

    reference  = db.Column(db.String(100), nullable=True)

    # Status: pending | success | failed
    status     = db.Column(db.String(20), default="success", nullable=False, index=True)

    paid_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id":        self.id,
            "user_id":   self.user_id,
            "bill_type": self.bill_type,
            "provider":  self.provider,
            "amount":    float(self.amount),
            "reference": self.reference,
            "status":    self.status,
            "paid_at":   str(self.paid_at) if self.paid_at else None,
            "date":      str(self.created_at),
        }