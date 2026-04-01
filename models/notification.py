from extensions import db
from datetime import datetime

class Notification(db.Model):
    __tablename__ = 'notifications'

    id         = db.Column(db.Integer,     primary_key=True)
    user_id    = db.Column(db.Integer,     db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title      = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text,        nullable=False)
    type       = db.Column(db.String(50),  default='info')    # info, success, warning, error
    icon       = db.Column(db.String(50),  default='bell')    # send, receive, deposit, security, etc.
    read       = db.Column(db.Boolean,     default=False, nullable=False)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id':         self.id,
            'title':      self.title,
            'message':    self.message,
            'type':       self.type,
            'icon':       self.icon,
            'read':       self.read,
            'created_at': str(self.created_at),
        }