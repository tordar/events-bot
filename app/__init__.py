from flask import Flask, current_app, url_for
from flask_mongoengine import MongoEngine
from apscheduler.schedulers.background import BackgroundScheduler
from itsdangerous import URLSafeTimedSerializer
from app.services.email_service import EmailService
from app.services.event_service import EventService
from app.utils.broadcast_api import BroadcastAPI
import os

db = MongoEngine()
scheduler = BackgroundScheduler()
serializer = URLSafeTimedSerializer(os.getenv('SECRET_KEY'))

def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    # Initialize services
    broadcast_api = BroadcastAPI(db)
    app.email_service = EmailService()
    app.event_service = EventService(broadcast_api)
    app.broadcast_api = broadcast_api

    from app.routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Set up logging
    import logging
    from logging.handlers import RotatingFileHandler
    import os

    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/event_subscription.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Event Subscription startup')

    scheduler.add_job(send_weekly_updates, 'cron', day_of_week='mon', hour=9, minute=0)
    scheduler.start()

    return app


def send_weekly_updates():
    with create_app(os.getenv('FLASK_CONFIG') or 'config.Config').app_context():
        try:
            # Fetch new events
            all_events = current_app.event_service.fetch_new_events()

            # Get all subscribers
            subscribers = Subscriber.objects.all()

            for subscriber in subscribers:
                try:
                    # Get preferences
                    preferred_venues = subscriber.venues
                    preferred_genres = subscriber.genres

                    # Skip if no preferences set
                    if not preferred_venues and not preferred_genres:
                        current_app.logger.info(f"Skipping subscriber {subscriber.email}: No preferences set")
                        continue

                    filtered_events = current_app.event_service.filter_events(all_events, preferred_venues, preferred_genres)

                    if filtered_events:
                        # Generate a secure unsubscribe token
                        #unsubscribe_token = serializer.dumps(subscriber.email, salt='unsubscribe-salt')
                        #unsubscribe_url = url_for('main.unsubscribe', token=unsubscribe_token, _external=True)
                        #current_app.logger.debug(f"Generated unsubscribe URL for {subscriber.email}: {unsubscribe_url}")

                        current_app.email_service.send_weekly_update(subscriber, filtered_events)

                        current_app.logger.info(f"Weekly update sent to {subscriber.email} with {len(filtered_events)} events.")
                    else:
                        current_app.logger.info(f"No matching events for subscriber {subscriber.email}")

                except Exception as e:
                    current_app.logger.error(f"Error sending weekly update to {subscriber.email}: {str(e)}")

        except Exception as e:
            current_app.logger.error(f"Error in weekly update job: {str(e)}")

# Import models after db is defined
from app.models.subscriber import Subscriber