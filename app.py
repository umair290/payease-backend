from flask import Flask
from config import config
from extensions import db, jwt
from flask_cors import CORS
from models import User, Wallet, Transaction, Bill, KYC
import os

def create_app(config_name="default"):
    app = Flask(__name__)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Load config
    app.config.from_object(config[config_name])

    # Create uploads folder if not exists
    os.makedirs("uploads/kyc", exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.account import account_bp
    from routes.kyc import kyc_bp
    from routes.admin import admin_bp
    from routes.bills import bills_bp
    from routes.otp import otp_bp
    from routes.notifications import notifications_bp

    app.register_blueprint(auth_bp,           url_prefix="/api/auth")
    app.register_blueprint(account_bp,        url_prefix="/api/account")
    app.register_blueprint(kyc_bp,            url_prefix="/api/kyc")
    app.register_blueprint(admin_bp,          url_prefix="/api/admin")
    app.register_blueprint(bills_bp,          url_prefix="/api/bills")
    app.register_blueprint(otp_bp,            url_prefix="/api/otp")
    app.register_blueprint(notifications_bp,  url_prefix="/api/notifications")

    with app.app_context():
        db.create_all()
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                # KYC columns
                conn.execute(text('ALTER TABLE kyc ADD COLUMN IF NOT EXISTS full_name_on_card VARCHAR(100)'))
                conn.execute(text('ALTER TABLE kyc ADD COLUMN IF NOT EXISTS date_of_birth VARCHAR(20)'))
                # Device detection column
                conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS last_device_hash VARCHAR(32)'))
                conn.commit()
                print("All migrations done!")
        except Exception as e:
            print(f"Migration note: {e}")
        print("Database ready!")

    return app


app = create_app()

@app.route("/")
def home():
    return {"message": "Welcome to PayEase API 🚀"}

if __name__ == "__main__":
    app.run(debug=True, port=5000)
