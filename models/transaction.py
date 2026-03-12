from extensions import db
from datetime import datetime

class Transaction(db.Model):

    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    from_wallet = db.Column(db.String(20))
    to_wallet = db.Column(db.String(20))
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default="success")
    description= db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return{
            "id":self.id,
            "from_wallet": self.from_wallet,
            "to_wallet": self.to_wallet,
            "amount": round(self.amount, 2),
            "type": self.type,
            "status": self.status,
            "description": self.description,
            "date": str(self.created_at)

        }