from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# MongoDB setup
MONGO_URI = os.getenv('MONGO_URI')
client = MongoClient(MONGO_URI)
db = client['event_subscription_db']
subscribers_collection = db['subscribers']

# Create index for email uniqueness
subscribers_collection.create_index([('email', 1)], unique=True)


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
        return jsonify({'status': 'healthy', 'mongodb': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)