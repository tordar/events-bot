import requests
import json
import os
from datetime import datetime, timedelta

class BroadcastAPI:
    def __init__(self):
        self.cache_file = 'broadcast_cache.json'
        self.cache_duration = timedelta(hours=1)

    def _load_cache(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    if datetime.fromisoformat(cache_data['timestamp']) + self.cache_duration > datetime.now():
                        print("Using cached data")
                        return cache_data['events']
        except Exception as e:
            print(f"Error loading cache: {str(e)}")
        return None

    def _save_cache(self, events):
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'events': events
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            print(f"Error saving cache: {str(e)}")

    def get_upcoming_events(self):
        cached_events = self._load_cache()
        if cached_events:
            return cached_events

        # Your actual API endpoint and logic here
        # For now, returning sample data
        events = [
            {
                "name": "Sample Event 1",
                "start_time": (datetime.now() + timedelta(days=1)).isoformat(),
                "venue": {"name": "Sample Venue 1"},
                "tags": ["Jazz", "Live Music"]
            },
            {
                "name": "Sample Event 2",
                "start_time": (datetime.now() + timedelta(days=2)).isoformat(),
                "venue": {"name": "Sample Venue 2"},
                "tags": ["Rock", "Concert"]
            }
        ]

        self._save_cache(events)
        return events