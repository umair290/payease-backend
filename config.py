import os

class Config:
    #App settings
    SECRET_KEY = os.environ.get("SECRET_KEY", "payease-secret-2024")

    #jwt settings
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "payease-jwt-secret-2024")
    JWT_ACCESS_TOKEN_EXPIRES = 3600 #1 hour

    #Databse settings
    #Using SQLlite for development, for production will use PostgreSQL (umair notes)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URI", "sqlite:///payease.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    #File upload settings for KYC
    UPLOAD_FOLDER = "uploads/kyc"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 #for max file size of 16MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

    #transfer limits
    MAX_TRANSFER_LIMIT = 50000 #Max amount per transaction
    DAILY_TRANSFER_LIMIT = 100000 #Max amount per day

    #OTP settings
    OTP_EXPIRY = 300 #5 minutes

class DevelopmentConfig(Config):
    DEBUG = True
class ProductionConfig(Config):
    DEBUG = False


#Active config
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}





