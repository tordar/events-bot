from flask import Blueprint, render_template, request, jsonify, url_for, current_app
from app.models.subscriber import Subscriber
from app.services.email_service import EmailService
from app.services.event_service import EventService
from datetime import datetime

main = Blueprint('main', __name__)
email_service = EmailService()


@main.route('/')
def index():
    return render_template('index.html')


@main.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    email = data.get('email')
    venues = data.get('venues', [])
    genres = data.get('genres', [])

    try:
        subscriber = Subscriber(
            email=email,
            venues=venues,
            genres=genres,
            subscribed_at=datetime.utcnow()
        )
        subscriber.save()

        # Send confirmation email
        current_app.email_service.send_confirmation_email(email)

        # Fetch and send filtered events
        events = current_app.event_service.fetch_new_events()
        filtered_events = current_app.event_service.filter_events(events, venues, genres)

        if filtered_events:
            current_app.email_service.send_weekly_update(subscriber, filtered_events)

        return jsonify({'message': 'Subscribed successfully'}), 200
    except Exception as e:
        current_app.logger.error(f"Error subscribing: {str(e)}")
        return jsonify({'message': f'Error subscribing: {str(e)}'}), 500

@main.route('/get_venues')
def get_venues():
    try:
        venues = current_app.broadcast_api.get_all_venues()
        return jsonify({'venue_names': venues})
    except Exception as e:
        current_app.logger.error(f"Error loading venues: {str(e)}")
        return jsonify({'venue_names': [], 'error': str(e)}), 500

@main.route('/get_genres')
def get_genres():
    try:
        tags = current_app.broadcast_api.get_all_tags()
        return jsonify({'tags': tags})
    except Exception as e:
        current_app.logger.error(f"Error loading genres: {str(e)}")
        return jsonify({'tags': [], 'error': str(e)}), 500


@main.route('/unsubscribe/<token>')
def unsubscribe(token):
    try:
        email = serializer.loads(token, salt='unsubscribe-salt', max_age=3600*24*7)  # Token valid for 1 week
        subscriber = Subscriber.objects(email=email).first()
        if subscriber:
            subscriber.delete()
            return jsonify({'message': 'Unsubscribed successfully'}), 200
        else:
            return jsonify({'message': 'Subscriber not found'}), 404
    except:
        return jsonify({'message': 'Invalid or expired token'}), 400

@main.route('/test-weekly-email/<email>')
def test_weekly_email(email):
    try:
        # First, verify this is a subscriber
        subscriber = subscribers_collection.find_one({'email': email})
        unsubscribe_token = serializer.dumps(subscriber['email'], salt='unsubscribe-salt')
        unsubscribe_url = url_for('unsubscribe', token=unsubscribe_token, _external=True)
        print(f"Debug: Generated unsubscribe URL for {subscriber['email']}: {unsubscribe_url}")
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
                                       email=email,
                                        unsubscribe_url=unsubscribe_url)
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


@main.route('/health')
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


# Add other routes (unsubscribe, test-weekly-email, etc.) here