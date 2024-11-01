from app import db
from datetime import datetime

class Subscriber(db.Document):
    email = db.StringField(required=True, unique=True)
    subscribed_at = db.DateTimeField(required=True, default=datetime.utcnow)
    venues = db.ListField(db.StringField())
    genres = db.ListField(db.StringField())