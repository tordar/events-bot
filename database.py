from apscheduler.triggers.cron import CronTrigger
from flask import Flask
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
from dotenv import load_dotenv
import ssl

# Load environment variables
load_dotenv()

# MongoDB setup with SSL configuration
MONGO_URI = os.getenv('MONGO_URI')
# Global variables
client = None
db = None
subscribers_collection = None

def init_mongodb():
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            ssl=True,
            ssl_cert_reqs=ssl.CERT_NONE,
            tls=True,
            tlsAllowInvalidCertificates=True
        )
        # Test connection
        client.admin.command('ping')
        print("MongoDB connection successful")

        db = client['event_subscription_db']
        subscribers_collection = db['subscribers']
        # Create index for email uniqueness
        subscribers_collection.create_index([('email', 1)], unique=True)

        return client, db, subscribers_collection
    except ConnectionFailure as e:
        print(f"MongoDB connection error: {str(e)}")
    except Exception as e:
        print(f"Unexpected error during MongoDB initialization: {str(e)}")

    return None

def create_app():
    app = Flask(__name__)

    # Initialize services
    init_mongodb()

    return app


# Create the Flask app
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)