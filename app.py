
from flask import Flask, render_template, request, jsonify, url_for
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from itsdangerous import URLSafeTimedSerializer
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from broadcast_api import BroadcastAPI
import ssl
import pytz
from dateutil import parser

# Load environment variables
load_dotenv()

# Initialise BroadcastAPI
broadcast_api = BroadcastAPI()

# Initialize Flask with explicit template folder
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)

# Initialize the serializer for creating secure tokens
serializer = URLSafeTimedSerializer(os.getenv('SECRET_KEY'))

# MongoDB setup with SSL configuration
MONGO_URI = os.getenv('MONGO_URI')
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL')

client = None
db = None
subscribers_collection = None
sendgrid_client = None
scheduler = None


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


def init_scheduler():
    global scheduler
    try:
        scheduler = BackgroundScheduler()
        # Schedule weekly email to be sent every Monday at 9 AM
        scheduler.add_job(
            send_weekly_updates,
            CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='weekly_updates',
            replace_existing=True
        )
        scheduler.start()
        print("Scheduler initialized successfully")
    except Exception as e:
        print(f"Scheduler initialization error: {str(e)}")
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



def fetch_new_events():
    try:
        api = BroadcastAPI()
        all_events = api.get_upcoming_events()
        # Make sure we have a timezone-aware datetime for comparison
        one_week_ago = datetime.now(pytz.UTC) - timedelta(days=7)

        new_events = []
        for event in all_events:
            try:
                # Parse the event time and ensure it's timezone-aware
                event_time = parser.parse(event['start_time'])
                if event_time.tzinfo is None:
                    # If the datetime is naive, make it timezone-aware
                    event_time = pytz.UTC.localize(event_time)

                if event_time > one_week_ago:
                    # Format the time for display
                    event['start_time'] = event_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                    new_events.append(event)
            except Exception as e:
                print(f"Error processing event: {str(e)}")
                continue

        return new_events
    except Exception as e:
        print(f"Error fetching events: {str(e)}")
        return []


# Initialize services
init_mongodb()
init_sendgrid()
init_scheduler()


@app.route('/')
def index():
    return render_template('index.html')




if __name__ == '__main__':
    app.run(debug=True)