from flask import Flask
from config import config
from extensions import db, jwt, limiter
from flask_cors import CORS
from models import User, Wallet, Transaction, Bill, KYC
from models.token_blocklist import TokenBlocklist
from models.audit_log import AuditLog
import os

def create_app(config_name="default"):
    app = Flask(__name__)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.config.from_object(config[config_name])
    os.makedirs("uploads/kyc", exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    from routes.auth          import auth_bp
    from routes.account       import account_bp
    from routes.kyc           import kyc_bp
    from routes.admin         import admin_bp
    from routes.bills         import bills_bp
    from routes.otp           import otp_bp
    from routes.notifications import notifications_bp
    from routes.preferences   import preferences_bp

    app.register_blueprint(auth_bp,          url_prefix="/api/auth")
    app.register_blueprint(account_bp,       url_prefix="/api/account")
    app.register_blueprint(kyc_bp,           url_prefix="/api/kyc")
    app.register_blueprint(admin_bp,         url_prefix="/api/admin")
    app.register_blueprint(bills_bp,         url_prefix="/api/bills")
    app.register_blueprint(otp_bp,           url_prefix="/api/otp")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(preferences_bp,   url_prefix="/api/preferences")

    with app.app_context():
        db.create_all()

        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                print("Running migrations...")

                # ── KYC columns — ALTER TYPE to TEXT for encrypted values ──
                conn.execute(text('ALTER TABLE kyc ALTER COLUMN cnic_number       TYPE TEXT'))
                conn.execute(text('ALTER TABLE kyc ALTER COLUMN full_name_on_card TYPE TEXT'))
                conn.execute(text('ALTER TABLE kyc ALTER COLUMN date_of_birth     TYPE TEXT'))
                conn.execute(text('ALTER TABLE kyc ALTER COLUMN rejection_reason  TYPE TEXT'))
                conn.execute(text('ALTER TABLE kyc ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP'))

                # ── User columns ──
                conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS last_device_hash VARCHAR(32)'))
                conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_done  BOOLEAN DEFAULT FALSE NOT NULL'))
                conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url       VARCHAR(500)'))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS beneficiaries    TEXT DEFAULT '[]' NOT NULL"))
                conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at    TIMESTAMP'))
                conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS login_count      INTEGER DEFAULT 0 NOT NULL'))
                conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at       TIMESTAMP'))

                # ── Wallet columns ──
                conn.execute(text('ALTER TABLE wallets ADD COLUMN IF NOT EXISTS last_reset_date DATE'))
                conn.execute(text('ALTER TABLE wallets ADD COLUMN IF NOT EXISTS version_id     INTEGER DEFAULT 0 NOT NULL'))
                conn.execute(text('ALTER TABLE wallets ADD COLUMN IF NOT EXISTS updated_at     TIMESTAMP'))

                # ── Transaction columns ──
                conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS direction        VARCHAR(10) DEFAULT 'debit' NOT NULL"))
                conn.execute(text('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS idempotency_key  VARCHAR(64)'))

                # ── Token blocklist ──
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS token_blocklist (
                        id         SERIAL PRIMARY KEY,
                        jti        VARCHAR(36) NOT NULL UNIQUE,
                        user_id    INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        created_at TIMESTAMP   DEFAULT NOW()
                    )
                '''))

                # ── Audit logs ──
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id         SERIAL PRIMARY KEY,
                        user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        admin_id   INTEGER,
                        action     VARCHAR(100) NOT NULL,
                        detail     TEXT,
                        ip         VARCHAR(45),
                        user_agent VARCHAR(255),
                        created_at TIMESTAMP DEFAULT NOW() NOT NULL
                    )
                '''))

                # ── Notifications ──
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS notifications (
                        id         SERIAL PRIMARY KEY,
                        user_id    INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        title      VARCHAR(200) NOT NULL,
                        message    TEXT         NOT NULL,
                        type       VARCHAR(50)  DEFAULT 'info',
                        icon       VARCHAR(50)  DEFAULT 'bell',
                        read       BOOLEAN      DEFAULT FALSE NOT NULL,
                        created_at TIMESTAMP    DEFAULT NOW()
                    )
                '''))

                # ── Beneficiaries ──
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS beneficiaries (
                        id            SERIAL PRIMARY KEY,
                        user_id       INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        wallet_number VARCHAR(20)  NOT NULL,
                        full_name     VARCHAR(200) NOT NULL,
                        phone         VARCHAR(20),
                        avatar_url    TEXT,
                        nickname      VARCHAR(100),
                        created_at    TIMESTAMP    DEFAULT NOW(),
                        CONSTRAINT uq_user_beneficiary UNIQUE (user_id, wallet_number)
                    )
                '''))

                # ── Indexes ──
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_users_email                ON users(email)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_users_phone                ON users(phone)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_wallets_user_id            ON wallets(user_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_wallets_wallet_number      ON wallets(wallet_number)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_transactions_user_id       ON transactions(user_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_transactions_from_wallet   ON transactions(from_wallet)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_transactions_to_wallet     ON transactions(to_wallet)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_transactions_type          ON transactions(type)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_transactions_created_at    ON transactions(created_at)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_transactions_idempotency   ON transactions(idempotency_key)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_bills_user_id              ON bills(user_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_bills_status               ON bills(status)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_bills_created_at           ON bills(created_at)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_kyc_user_id                ON kyc(user_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_kyc_status                 ON kyc(status)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_token_blocklist_jti        ON token_blocklist(jti)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_token_blocklist_user_id    ON token_blocklist(user_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id         ON audit_logs(user_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_audit_logs_admin_id        ON audit_logs(admin_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_audit_logs_action          ON audit_logs(action)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at      ON audit_logs(created_at)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_notifications_user_id     ON notifications(user_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_notifications_read        ON notifications(read)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_beneficiaries_user_id     ON beneficiaries(user_id)'))

                conn.commit()
                print("✅ All migrations done!")

        except Exception as e:
            print(f"Migration note: {e}")

        print("✅ Database ready!")

    return app


app = create_app()

@app.route("/")
def home():
    return {"message": "Welcome to PayEase API"}

if __name__ == "__main__":
    app.run(debug=True, port=5000)