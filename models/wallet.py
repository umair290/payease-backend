from extensions import db
from datetime import datetime

class Wallet(db.Model):
    __tablename__ = "wallets"

    id = db.Column(db.Integer, primary_key=True)
    user_id= db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    wallet_number = db.Column(db.String(20), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.00)
    daily_spent = db.Column(db.Float, default=0.00)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return{
            "wallet_number": self.wallet_number,
            "balance": round(self.balance, 2),
            "daily_spent": round(self.daily_spent, 2),
            "created_at": str(self.created_at)    
            
            }
