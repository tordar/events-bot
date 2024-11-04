import sys

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, render_template, request, jsonify
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from email_service import send_weekly_updates, fetch_new_events
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from broadcast_api import BroadcastAPI
import pytz
from dateutil import parser
from database import init_mongodb

# Load environment variables
load_dotenv()

# Initialize Flask with explicit template folder
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)


def init_services():
    # Initialize MongoDB
    mongodb_result = init_mongodb()
    if mongodb_result is None:
        print("Failed to initialize MongoDB. Exiting application.")
        sys.exit(1)

    client, db, subscribers_collection = mongodb_result

    # Initialize SendGrid
    sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('FROM_EMAIL')
    try:
        sendgrid_client = SendGridAPIClient(sendgrid_api_key)
        print("SendGrid client initialized successfully")
    except Exception as e:
        print(f"SendGrid initialization error: {str(e)}")
        sys.exit(1)

    # Initialize scheduler
    print("About to initialize scheduler")
    scheduler = BackgroundScheduler()

    def scheduled_weekly_update():
        print("Running scheduled weekly update")
        subscribers = subscribers_collection.find()
        events = fetch_new_events()  # Replace with actual event fetching logic
        send_weekly_updates(sendgrid_client, subscribers, events, from_email)

    print("Adding job to scheduler")
    scheduler.add_job(
        scheduled_weekly_update,
        CronTrigger(day_of_week='mon', hour=9, minute=0),
        id='weekly_updates'
    )
    try:
        scheduler.start()
        print("Scheduler initialized successfully")
    except Exception as e:
        print(f"Scheduler initialization error: {str(e)}")
        sys.exit(1)

    return client, db, subscribers_collection, sendgrid_client, scheduler

FROM_EMAIL = os.getenv('FROM_EMAIL')

# Initialize all services
client, db, subscribers_collection, sendgrid_client, scheduler = init_services()


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



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_venues')
def get_venues():
    try:
        with open('venue_names.json', 'r') as f:
            venues = json.load(f)
        return jsonify(venues)
    except Exception as e:
        print(f"Error loading venues: {str(e)}")
        return jsonify({'venue_names': []}), 500

@app.route('/get_genres')
def get_genres():
    try:
        with open('distinct_tags.json', 'r') as f:
            genres = json.load(f)
        return jsonify(genres)
    except Exception as e:
        print(f"Error loading genres: {str(e)}")
        return jsonify({'tags': []}), 500


@app.route('/subscribe', methods=['POST'])
def subscribe():
    if not subscribers_collection:
        return jsonify({'message': 'Database connection not available'}), 503

    data = request.json
    email = data.get('email')
    venues = data.get('venues', [])
    genres = data.get('genres', [])

    try:
        subscriber = {
            'email': email,
            'subscribed_at': datetime.utcnow(),
            'venues': venues,
            'genres': genres
        }
        result = subscribers_collection.insert_one(subscriber)
        print(f"Subscriber added to database with id: {result.inserted_id}")

        # Send confirmation email
        confirmation_sent = send_confirmation_email(email)

        # Fetch and send filtered events
        all_events = fetch_new_events()
        filtered_events = []

        for event in all_events:
            venue_match = False
            genre_match = False

            if venues:
                venue_match = event['venue']['name'] in venues
            else:
                venue_match = True

            if genres:
                genre_match = any(tag in genres for tag in event.get('tags', []))
            else:
                genre_match = True

            if venue_match and genre_match:
                filtered_events.append(event)

        if filtered_events:
            html_content = render_template('email_template.html',
                                           events=filtered_events,
                                           email=email)
            message = Mail(
                from_email=FROM_EMAIL,
                to_emails=email,
                subject='Your First Event Update',
                html_content=html_content
            )
            sendgrid_client.send(message)
            print(f"First event update sent to {email} with {len(filtered_events)} events")

        response_message = 'Subscribed successfully'
        if not confirmation_sent:
            response_message += ' (confirmation email could not be sent)'

        return jsonify({'message': response_message}), 200
    except Exception as e:
        if 'duplicate key error' in str(e):
            return jsonify({'message': 'Already subscribed'}), 400
        return jsonify({'message': f'Error subscribing: {str(e)}'}), 500


@app.route('/test-weekly-email/<email>')
def test_weekly_email(email):
    try:
        # First, verify this is a subscriber
        subscriber = subscribers_collection.find_one({'email': email})
        if not subscriber:
            return jsonify({
                'status': 'error',
                'message': 'Email not found. Only subscribers can receive test emails.'
            }), 404

        # Fetch events
        all_events = fetch_new_events()

        # Get preferences - handle both old and new structure
        preferred_venues = subscriber.get('preferences', {}).get('venues', []) or subscriber.get('venues', [])
        preferred_genres = subscriber.get('preferences', {}).get('genres', []) or subscriber.get('genres', [])

        # Check if any preferences are set
        if not preferred_venues and not preferred_genres:
            return jsonify({
                'status': 'warning',
                'message': 'No preferences set. Please set venue or genre preferences to receive event updates.',
                'preferences': {
                    'venues': preferred_venues,
                    'genres': preferred_genres
                }
            }), 400

        filtered_events = []
        for event in all_events:
            # Initialize match flags
            venue_match = False
            genre_match = False

            # Check venue preference
            if preferred_venues:
                venue_match = event['venue']['name'] in preferred_venues
            else:
                # If no venues specified, any venue is acceptable
                venue_match = True

            # Check genre preference
            if preferred_genres:
                genre_match = any(tag in preferred_genres for tag in event.get('tags', []))
            else:
                # If no genres specified, any genre is acceptable
                genre_match = True

            # Only add event if it matches both venue and genre preferences
            if venue_match and genre_match:
                filtered_events.append(event)

        if not filtered_events:
            return jsonify({
                'status': 'warning',
                'message': 'No events match your preferences for the selected period.',
                'preferences': {
                    'venues': preferred_venues,
                    'genres': preferred_genres
                }
            }), 200

        # Send email with filtered events
        html_content = render_template('email_template.html',
                                       events=filtered_events,
                                       email=email)
        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=email,
            subject='Weekly Event Update',
            html_content=html_content
        )
        response = sendgrid_client.send(message)

        return jsonify({
            'status': 'success',
            'message': f'Test email sent with {len(filtered_events)} matching events. Status Code: {response.status_code}',
            'preferences': {
                'venues': preferred_venues,
                'genres': preferred_genres
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/health')
def health():
    status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {
            'mongodb': 'disconnected',
            'sendgrid': 'disconnected',
            'events': 'disconnected',
            'scheduler': 'disconnected'
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

    try:
        if scheduler and scheduler.running:
            next_run = scheduler.get_job('weekly_updates').next_run_time
            status['services']['scheduler'] = f'running (next run: {next_run.isoformat()})'
        else:
            status['services']['scheduler'] = 'not running'
    except Exception as e:
        status['services']['scheduler'] = f'error: {str(e)}'

    is_healthy = all(s == 'connected' or s == 'initialized' or
                     s.startswith('connected') or s.startswith('running')
                     for s in status['services'].values())

    return jsonify(status), 200 if is_healthy else 503


if __name__ == '__main__':
    app.run(debug=True)