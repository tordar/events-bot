from datetime import datetime, timedelta
import pytz
from dateutil import parser

class EventService:
    def __init__(self, broadcast_api):
        self.broadcast_api = broadcast_api

    def fetch_new_events(self):
        all_events = self.broadcast_api.get_upcoming_events()
        one_week_ago = datetime.now(pytz.UTC) - timedelta(days=7)

        new_events = []
        for event in all_events:
            event_time = parser.parse(event['start_time'])
            if event_time.tzinfo is None:
                event_time = pytz.UTC.localize(event_time)

            if event_time > one_week_ago:
                event['start_time'] = event_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                new_events.append(event)

        return new_events

    def filter_events(self, events, preferred_venues, preferred_genres):
        filtered_events = []
        for event in events:
            venue_match = not preferred_venues or event['venue']['name'] in preferred_venues
            genre_match = not preferred_genres or any(tag in preferred_genres for tag in event.get('tags', []))
            if venue_match and genre_match:
                filtered_events.append(event)
        return filtered_events