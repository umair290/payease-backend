import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── Flask ──
    SECRET_KEY = os.environ.get('SECRET_KEY', '')

    # ── JWT ──
    JWT_SECRET_KEY             = os.environ.get('JWT_SECRET_KEY', '')
    JWT_ACCESS_TOKEN_EXPIRES   = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES  = timedelta(days=30)
    JWT_TOKEN_LOCATION         = ['headers']
    JWT_BLACKLIST_ENABLED      = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']

    # ── Database ──
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///payease.db')
    SQLALCHEMY_DATABASE_URI        = _db_url.replace('postgres://', 'postgresql://', 1) if _db_url.startswith('postgres://') else _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS      = {
        'pool_pre_ping': True,
        'pool_recycle':  300,
        'pool_size':     10,
        'max_overflow':  20,
    }

    # ── Cloudinary ──
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
    CLOUDINARY_API_KEY    = os.environ.get('CLOUDINARY_API_KEY',    '')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

    # ── Email (Resend) ──
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
    SENDER_EMAIL   = os.environ.get('SENDER_EMAIL',   'support@payease.space')

    # ── Legacy SMTP (kept for reference, not used if using Resend) ──
    MAIL_SERVER         = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
    MAIL_PORT           = int(os.environ.get('MAIL_PORT', '465'))
    MAIL_USE_TLS        = True
    MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME', '')

    # ── KYC Encryption ──
    KYC_ENCRYPTION_KEY = os.environ.get('KYC_ENCRYPTION_KEY', '')

    # ── File uploads ──
    UPLOAD_FOLDER      = 'uploads/kyc'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

    # ── Transfer limits ──
    MAX_TRANSFER_LIMIT   = 50000
    DAILY_TRANSFER_LIMIT = 100000

    # ── OTP ──
    OTP_EXPIRY = 300  # 5 minutes


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     ProductionConfig,   # ← production by default on Railway
}