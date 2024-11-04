from logging import exception
from sendgrid.helpers.mail import Mail
from flask import render_template
from datetime import datetime, timedelta
from broadcast_api import BroadcastAPI
import pytz
from dateutil import parser

def send_weekly_updates(sendgrid_client, subscribers, events, from_email):
    if not subscribers or not sendgrid_client:
        print("Services not initialized")
        return

    try:
        # Fetch new events
        all_events = fetch_new_events()

        # Get all subscribers
        subscribers = subscribers.find()

        for subscriber in subscribers:
            try:
                # Get preferences
                preferences = subscriber.get('preferences', {})
                preferred_venues = preferences.get('venues', [])
                preferred_genres = preferences.get('genres', [])

                # Skip if no preferences set
                if not preferred_venues and not preferred_genres:
                    print(f"Skipping subscriber {subscriber['email']}: No preferences set")
                    continue

                filtered_events = []
                for event in all_events:
                    venue_match = False
                    genre_match = False

                    if preferred_venues:
                        venue_match = event['venue']['name'] in preferred_venues
                    else:
                        venue_match = True

                    if preferred_genres:
                        genre_match = any(tag in preferred_genres for tag in event.get('tags', []))
                    else:
                        genre_match = True

                    if venue_match and genre_match:
                        filtered_events.append(event)

                if filtered_events:
                    html_content = render_template('email_template.html',
                                                   events=filtered_events,
                                                   email=subscriber['email'])
                    message = Mail(
                        from_email=from_email,
                        to_emails=subscriber['email'],
                        subject='Weekly Event Update',
                        html_content=html_content
                    )
                    try:
                        response = sendgrid_client.send(message)
                        print(f"Sent weekly update to {subscriber['email']}. Status code: {response.status_code}")
                    except Exception as e:
                        print(f"Error sending email to {subscriber['email']}: {str(e)}")
            except Exception as e:
                print(f"Error processing subscriber {subscriber['email']}: {str(e)}")
    except Exception as e:
        print(f"Error in send_weekly_updates: {str(e)}")

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