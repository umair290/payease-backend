from extensions import db
from datetime import datetime

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id         = db.Column(db.Integer,     primary_key=True)
    user_id    = db.Column(db.Integer,     db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    admin_id   = db.Column(db.Integer,     nullable=True, index=True)  # who performed the action (if admin)
    action     = db.Column(db.String(100), nullable=False, index=True)
    detail     = db.Column(db.Text,        nullable=True)
    ip         = db.Column(db.String(45),  nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        from models.user import User
        user  = User.query.get(self.user_id)  if self.user_id  else None
        admin = User.query.get(self.admin_id) if self.admin_id else None
        return {
            'id':         self.id,
            'user_id':    self.user_id,
            'user_name':  user.full_name  if user  else 'Unknown',
            'user_email': user.email      if user  else 'Unknown',
            'admin_id':   self.admin_id,
            'admin_name': admin.full_name if admin else None,
            'action':     self.action,
            'detail':     self.detail,
            'ip':         self.ip or '—',
            'timestamp':  self.created_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
        }