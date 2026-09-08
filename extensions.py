"""
Shared Flask extension instances.
Kept in their own module so routes/models can import without circular imports.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
