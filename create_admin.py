from app import app
from extensions import db
from models import User, Wallet
import bcrypt
import random
import string

with app.app_context():
    hashed = bcrypt.hashpw(
        "admin123".encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    
    hashed_pin = bcrypt.hashpw(
        "0000".encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    
    admin = User(
        full_name    = "Admin",
        email        = "admin@payease.com",
        phone        = "03000000000",
        password     = hashed,
        pin          = hashed_pin,
        is_admin     = True,
        kyc_verified = True
    )
    db.session.add(admin)
    db.session.flush()

    wallet_number = "PK" + "".join(random.choices(string.digits, k=10))
    wallet = Wallet(
        user_id       = admin.id,
        wallet_number = wallet_number,
        balance       = 0.00
    )
    db.session.add(wallet)
    db.session.commit()
    print("Admin created successfully!")