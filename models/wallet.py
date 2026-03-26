from extensions import db
from datetime import datetime
from sqlalchemy import Numeric

class Wallet(db.Model):
    __tablename__ = "wallets"

    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    wallet_number = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # Use Numeric instead of Float for money — avoids floating point errors
    # precision=12 = up to 999,999,999.99 PKR
    # scale=2 = always 2 decimal places
    balance       = db.Column(Numeric(precision=12, scale=2), default=0.00, nullable=False)
    daily_spent   = db.Column(Numeric(precision=12, scale=2), default=0.00, nullable=False)

    # Track when daily_spent was last reset
    last_reset_date = db.Column(db.Date, default=datetime.utcnow().date, nullable=True)

    # Optimistic locking — prevents race conditions on concurrent balance updates
    version_id    = db.Column(db.Integer, default=0, nullable=False)

    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Optimistic locking config — SQLAlchemy will auto-increment version_id
    # and raise StaleDataError if two requests try to update same row simultaneously
    __mapper_args__ = {
        "version_id_col": version_id
    }

    def to_dict(self):
        return {
            "wallet_number":   self.wallet_number,
            "balance":         float(self.balance),
            "daily_spent":     float(self.daily_spent),
            "last_reset_date": str(self.last_reset_date) if self.last_reset_date else None,
            "created_at":      str(self.created_at),
        }