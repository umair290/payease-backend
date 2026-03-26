from extensions import db
from datetime import datetime
from sqlalchemy import Numeric

class Transaction(db.Model):
    __tablename__ = "transactions"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    from_wallet    = db.Column(db.String(20), nullable=True,  index=True)
    to_wallet      = db.Column(db.String(20), nullable=True,  index=True)

    # Numeric for money — no floating point errors
    amount         = db.Column(Numeric(precision=12, scale=2), nullable=False)

    # Type: transfer | deposit | electricity | gas | internet | topup
    type           = db.Column(db.String(30), nullable=False, index=True)

    # Direction: debit | credit — used by frontend insights/history
    direction      = db.Column(db.String(10), nullable=False, default="debit")

    status         = db.Column(db.String(20), default="success",  nullable=False)
    description    = db.Column(db.String(255), nullable=True)

    # Idempotency key — prevents duplicate transactions
    # Frontend generates this (e.g. UUID) and sends with request
    # Backend rejects if same key already exists
    idempotency_key = db.Column(db.String(64), nullable=True, unique=True, index=True)

    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id":           self.id,
            "from_wallet":  self.from_wallet,
            "to_wallet":    self.to_wallet,
            "amount":       float(self.amount),
            "type":         self.type,
            "direction":    self.direction,
            "status":       self.status,
            "description":  self.description,
            "created_at":   str(self.created_at),
            "date":         str(self.created_at),
        }