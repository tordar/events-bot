from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# MongoDB setup with timeout configuration
MONGO_URI = os.getenv('MONGO_URI')
client = None
db = None
subscribers_collection = None


def init_mongodb():
    global client, db, subscribers_collection
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        # Test connection
        client.admin.command('ping')
        print("MongoDB connection successful")

        db = client['event_subscription_db']
        subscribers_collection = db['subscribers']
        # Create index for email uniqueness
        subscribers_collection.create_index([('email', 1)], unique=True)

    except Exception as e:
        print(f"MongoDB connection error: {str(e)}")
        raise


# Initialize MongoDB connection
init_mongodb()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    email = data.get('email')

    try:
        subscriber = {
            'email': email,
            'subscribed_at': datetime.utcnow()
        }
        result = subscribers_collection.insert_one(subscriber)
        return jsonify({'message': 'Subscribed successfully'}), 200
    except Exception as e:
        if 'duplicate key error' in str(e):
            return jsonify({'message': 'Already subscribed'}), 400
        return jsonify({'message': f'Error subscribing: {str(e)}'}), 500


@app.route('/health')
def health():
    try:
        # Test MongoDB connection
        client.admin.command('ping')
        return jsonify({
            'status': 'healthy',
            'mongodb': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


if __name__ == '__main__':
    app.run(debug=True)