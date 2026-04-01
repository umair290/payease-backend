from extensions import db
from datetime import datetime

class Beneficiary(db.Model):
    __tablename__ = 'beneficiaries'

    id            = db.Column(db.Integer,     primary_key=True)
    user_id       = db.Column(db.Integer,     db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    wallet_number = db.Column(db.String(20),  nullable=False)
    full_name     = db.Column(db.String(200), nullable=False)
    phone         = db.Column(db.String(20),  nullable=True)
    avatar_url    = db.Column(db.Text,        nullable=True)
    nickname      = db.Column(db.String(100), nullable=True)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'wallet_number', name='uq_user_beneficiary'),
    )

    def to_dict(self):
        return {
            'id':            self.id,
            'wallet_number': self.wallet_number,
            'full_name':     self.full_name,
            'phone':         self.phone or '',
            'avatar_url':    self.avatar_url or '',
            'nickname':      self.nickname or '',
            'created_at':    str(self.created_at),
        }