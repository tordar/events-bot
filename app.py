from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
from dotenv import load_dotenv
from datetime import datetime
import ssl
from broadcast_api import BroadcastAPI

# Load environment variables
load_dotenv()


# Initialize Flask with explicit template folder
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)

# MongoDB setup with SSL configuration
MONGO_URI = os.getenv('MONGO_URI')
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL')

client = None
db = None
subscribers_collection = None
sendgrid_client = None


def init_mongodb():
    global client, db, subscribers_collection
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

    except Exception as e:
        print(f"MongoDB connection error: {str(e)}")
        pass


def init_sendgrid():
    global sendgrid_client
    try:
        sendgrid_client = SendGridAPIClient(SENDGRID_API_KEY)
        print("SendGrid client initialized successfully")
    except Exception as e:
        print(f"SendGrid initialization error: {str(e)}")
        pass


def send_confirmation_email(to_email):
    if not sendgrid_client:
        print("SendGrid client not initialized")
        return False

    try:
        html_content = render_template('subscription_confirmation.html')
        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=to_email,
            subject='Subscription Confirmed - Event Updates',
            html_content=html_content
        )
        response = sendgrid_client.send(message)
        print(f"Confirmation email sent to {to_email}. Status Code: {response.status_code}")
        return True
    except Exception as e:
        print(f"Error sending confirmation email: {str(e)}")
        return False


# Add these imports at the top
from broadcast_api import BroadcastAPI


# Add this function after your other initialization functions
def fetch_new_events():
    try:
        api = BroadcastAPI()
        all_events = api.get_upcoming_events()
        one_week_ago = datetime.utcnow() - timedelta(days=7)

        new_events = []
        for event in all_events:
            event_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
            if event_time > one_week_ago:
                new_events.append(event)

        return new_events
    except Exception as e:
        print(f"Error fetching events: {str(e)}")
        return []





# Initialize services
init_mongodb()
init_sendgrid()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/subscribe', methods=['POST'])
def subscribe():
    if not subscribers_collection:
        return jsonify({'message': 'Database connection not available'}), 503

    data = request.json
    email = data.get('email')

    try:
        subscriber = {
            'email': email,
            'subscribed_at': datetime.utcnow()
        }
        result = subscribers_collection.insert_one(subscriber)

        # Send confirmation email
        email_sent = send_confirmation_email(email)

        response_message = 'Subscribed successfully'
        if not email_sent:
            response_message += ' (confirmation email could not be sent)'

        return jsonify({'message': response_message}), 200
    except Exception as e:
        if 'duplicate key error' in str(e):
            return jsonify({'message': 'Already subscribed'}), 400
        return jsonify({'message': f'Error subscribing: {str(e)}'}), 500


@app.route('/health')
def health():
    status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {
            'mongodb': 'disconnected',
            'sendgrid': 'disconnected',
            'events': 'disconnected'
        }
    }

    try:
        if client:
            client.admin.command('ping')
            status['services']['mongodb'] = 'connected'
    except Exception as e:
        status['services']['mongodb'] = f'error: {str(e)}'

    try:
        if sendgrid_client:
            status['services']['sendgrid'] = 'initialized'
    except Exception as e:
        status['services']['sendgrid'] = f'error: {str(e)}'

    try:
        events = fetch_new_events()
        status['services']['events'] = f'connected ({len(events)} events)'
    except Exception as e:
        status['services']['events'] = f'error: {str(e)}'

    is_healthy = all(s == 'connected' or s == 'initialized' or s.startswith('connected')
                     for s in status['services'].values())

    return jsonify(status), 200 if is_healthy else 503

# Add this new route after your other routes
@app.route('/events')
def get_events():
    try:
        events = fetch_new_events()
        return jsonify({
            'status': 'success',
            'count': len(events),
            'events': events
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)