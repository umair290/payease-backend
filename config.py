import os
from datetime import timedelta

class Config:
    # App settings
    SECRET_KEY = os.environ.get("SECRET_KEY", "payease-secret-2024")

    # ── JWT settings ──
    JWT_SECRET_KEY            = os.environ.get("JWT_SECRET_KEY", "payease-jwt-secret-2024")
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(minutes=15)  # Short-lived access token
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)     # Long-lived refresh token
    JWT_TOKEN_LOCATION        = ["headers"]            # Look for tokens in headers only
    JWT_BLACKLIST_ENABLED     = True
    JWT_BLACKLIST_TOKEN_CHECKS = ["access", "refresh"]

    # Database settings
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///payease.db')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI    = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cloudinary settings
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', 'debkhln5h')
    CLOUDINARY_API_KEY    = os.environ.get('CLOUDINARY_API_KEY',    '663954632474482')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', 'sT4-evyiUqtJagfeeLnBiwx5pJE')

    # Email settings
    MAIL_SERVER         = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
    MAIL_PORT           = int(os.environ.get('MAIL_PORT', 465))
    MAIL_USE_TLS        = True
    MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', 'zodumair@gmail.com')
    MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', 'cmyblzglplizawel')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME', 'zodumair@gmail.com')

    # File upload settings
    UPLOAD_FOLDER        = "uploads/kyc"
    MAX_CONTENT_LENGTH   = 16 * 1024 * 1024   # 16MB
    ALLOWED_EXTENSIONS   = {"png", "jpg", "jpeg"}

    # Transfer limits
    MAX_TRANSFER_LIMIT   = 50000
    DAILY_TRANSFER_LIMIT = 100000

    # OTP settings
    OTP_EXPIRY = 300  # 5 minutes in seconds

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig
}