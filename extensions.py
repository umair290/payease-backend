from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager



# These extensions are created here and initialezed in app.py wihich prevents circular imports
db = SQLAlchemy()
jwt = JWTManager()
