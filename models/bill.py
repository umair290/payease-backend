from extensions import db
from datetime import datetime

class Bill(db.Model):
    __tablename = "bills"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    bill_type = db.Column(db.String(50), nullable=False)
    provider = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(100))
    status = db.Column(db.String(20), default="pending")
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    def to_dict(self):
        return{
            "id": self.id,
            "user_id": self.user_id,
            "bill_type": self.bill_type,
            "provider": self.provider,
            "amount": round(self.amount, 2),
            "reference": self.reference,
            "status": self.status,
            "paid_at": str(self.paid_at) if self.paid_at else None,
            "date": str(self.created_at)
        }
