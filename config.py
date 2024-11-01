import os

class Config:
    MONGODB_SETTINGS = {
        'host': os.environ.get('MONGO_URI')
    }
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    FROM_EMAIL = os.environ.get('FROM_EMAIL')