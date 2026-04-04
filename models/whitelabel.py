from extensions import db
from datetime import datetime
import json


class WhitelabelConfig(db.Model):
    """Stores white-label branding configuration. One row per deployment."""
    __tablename__ = 'whitelabel_config'

    id              = db.Column(db.Integer, primary_key=True)
    app_name        = db.Column(db.String(100), default='PayEase')
    tagline         = db.Column(db.String(200), default='Your Digital Wallet')
    logo_url        = db.Column(db.Text)
    favicon_url     = db.Column(db.Text)
    primary_color   = db.Column(db.String(20), default='#1A73E8')
    secondary_color = db.Column(db.String(20), default='#7C3AED')
    accent_color    = db.Column(db.String(20), default='#16A34A')
    features        = db.Column(db.Text, default='{}')  # JSON
    support_email   = db.Column(db.String(200), default='support@payease.space')
    website_url     = db.Column(db.String(300), default='https://payease.space')
    updated_by      = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_features(self):
        try:
            return json.loads(self.features or '{}')
        except Exception:
            return {}

    def set_features(self, d):
        self.features = json.dumps(d)

    def to_dict(self):
        return {
            'id':              self.id,
            'app_name':        self.app_name,
            'tagline':         self.tagline,
            'logo_url':        self.logo_url,
            'favicon_url':     self.favicon_url,
            'primary_color':   self.primary_color,
            'secondary_color': self.secondary_color,
            'accent_color':    self.accent_color,
            'features':        self.get_features(),
            'support_email':   self.support_email,
            'website_url':     self.website_url,
            'updated_at':      self.updated_at.isoformat() if self.updated_at else None,
        }
