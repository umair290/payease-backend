from extensions import db
from datetime import datetime


class BillSplitGroup(db.Model):
    """A split bill created by a user."""
    __tablename__ = 'bill_split_groups'

    id          = db.Column(db.Integer,     primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    total_amount= db.Column(db.Numeric(12, 2), nullable=False)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    status      = db.Column(db.String(20), default='open')   # open | settled
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = db.relationship('BillSplitMember', backref='group', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, include_members=True):
        d = {
            'id':           self.id,
            'title':        self.title,
            'description':  self.description,
            'total_amount': float(self.total_amount),
            'created_by':   self.created_by,
            'status':       self.status,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
        }
        if include_members:
            d['members'] = [m.to_dict() for m in self.members]
            paid   = sum(float(m.share_amount) for m in self.members if m.status == 'paid')
            total  = sum(float(m.share_amount) for m in self.members)
            d['paid_amount']   = paid
            d['paid_count']    = sum(1 for m in self.members if m.status == 'paid')
            d['member_count']  = len(self.members)
        return d


class BillSplitMember(db.Model):
    """One member's share in a split bill."""
    __tablename__ = 'bill_split_members'

    id            = db.Column(db.Integer, primary_key=True)
    group_id      = db.Column(db.Integer, db.ForeignKey('bill_split_groups.id', ondelete='CASCADE'), nullable=False)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    wallet_number = db.Column(db.String(20), nullable=False)
    full_name     = db.Column(db.String(200))
    avatar_url    = db.Column(db.Text)
    share_amount  = db.Column(db.Numeric(12, 2), nullable=False)
    status        = db.Column(db.String(20), default='pending')  # pending | paid
    paid_at       = db.Column(db.DateTime)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':            self.id,
            'group_id':      self.group_id,
            'user_id':       self.user_id,
            'wallet_number': self.wallet_number,
            'full_name':     self.full_name,
            'avatar_url':    self.avatar_url,
            'share_amount':  float(self.share_amount),
            'status':        self.status,
            'paid_at':       self.paid_at.isoformat() if self.paid_at else None,
            'created_at':    self.created_at.isoformat() if self.created_at else None,
        }
