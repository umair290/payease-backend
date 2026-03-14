from extensions import db
from datetime import datetime

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    pin = db.Column(db.String(255), nullable=False)
    is_blocked = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    kyc_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    #Relationships

    wallet = db.relationship("Wallet", backref="user", uselist=False)
    transactions = db.relationship("Transaction", backref="user")
    kyc = db.relationship("KYC", backref="user", uselist=False)

    def to_dict(self):
        return{
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "is_admin": self.is_admin,
            "is_blocked": self.is_blocked,
            "kyc_verified": self.kyc_verified,
            "created_at": str(self.created_at)
    
        }