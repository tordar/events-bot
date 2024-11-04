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

    # Initialize MongoDB
    client, db, subscribers_collection = init_mongodb()

    if not all([client, db, subscribers_collection]):
        raise RuntimeError("Failed to initialize MongoDB. Application cannot start.")

    # Store MongoDB connection in app config
    app.config['MONGO_CLIENT'] = client
    app.config['MONGO_DB'] = db
    app.config['SUBSCRIBERS_COLLECTION'] = subscribers_collection


    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)