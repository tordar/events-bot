import requests
import time
from datetime import datetime
import json
from typing import List, Dict, Optional, Set
import logging


class BroadcastAPI:
    def __init__(self, cache_duration_minutes: int = 60):
        self.base_url = "https://www.broadcast.events/api/queryAllEventsByRegion_vM?&region=Oslo&published=true&start_time=2024-10-29T09:00&limit=5000&skip=0"
        self.headers = {
            'User-Agent': 'Friendly Python Script - Personal Use Only - Contact tordar.tommervik@gmail.com',
            'Accept': 'application/json'
        }
        self.cache_file = 'broadcast_cache.json'
        self.cache_duration_minutes = cache_duration_minutes
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _load_cache(self) -> Optional[Dict]:
        try:
            with open(self.cache_file, 'r') as f:
                cache = json.load(f)
                cache_time = datetime.fromisoformat(cache['timestamp'])
                if (datetime.now() - cache_time).total_seconds() < self.cache_duration_minutes * 60:
                    return cache['data']
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        return None

    def _save_cache(self, data: List[Dict]):
        cache = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        with open(self.cache_file, 'w') as f:
            json.dump(cache, f)

    def get_events(self) -> List[Dict]:
        """
        Get events from cache if available, otherwise fetch from API
        """
        cached_data = self._load_cache()
        if cached_data:
            self.logger.info("Using cached data")
            return cached_data

        self.logger.info("Fetching fresh data from API")
        response = requests.get(self.base_url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        self._save_cache(data)
        time.sleep(1)  # Be nice to the API
        return data

    def extract_event_info(self, event: Dict) -> Dict:
        """
        Extract relevant information from an event with safe fallbacks
        """
        custom_fields = event.get('custom_fields', {})
        place = event.get('place', {})

        return {
            'id': event.get('id'),
            'name': event.get('name'),
            'start_time': event.get('start_time'),
            'end_time': custom_fields.get('end_time'),
            'tags': event.get('tags', []),
            'age_limit': custom_fields.get('age'),
            'sold_out': custom_fields.get('soldOut', False),
            'ticket_url': custom_fields.get('ticketUrl'),
            'cover_charge': custom_fields.get('coverCharge', custom_fields.get('cover', 'Price not listed')),
            'venue': {
                'name': place.get('name'),
                'address': place.get('address'),
                'city': place.get('city')
            }
        }

    def get_upcoming_events(self, max_events: int = None) -> List[Dict]:
        """
        Get upcoming events with extracted information
        """
        events = self.get_events()
        extracted_events = [self.extract_event_info(event) for event in events]

        if max_events:
            return extracted_events[:max_events]
        return extracted_events


    def extract_distinct_tags(self, output_file: str = 'distinct_tags.json') -> Set[str]:
        """
        Extract all distinct tags from events and save them to a JSON file.

        :param output_file: Name of the JSON file to save the tags to.
        :return: A set of all distinct tags.
        """
        events = self.get_events()
        all_tags = set()

        for event in events:
            tags = event.get('tags', [])
            all_tags.update(tags)

        # Convert set to a sorted list for JSON serialization
        sorted_tags = sorted(list(all_tags))

        # Save to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({"tags": sorted_tags}, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Extracted {len(all_tags)} distinct tags and saved to {output_file}")
        return all_tags

    def extract_venue_names(self, output_file: str = 'venue_names.json') -> List[str]:
        """
        Extract all distinct venue names from events and save them to a JSON file.

        :param output_file: Name of the JSON file to save the venue names to.
        :return: A list of all distinct venue names.
        """
        events = self.get_events()
        venue_names = set()

        for event in events:
            place = event.get('place', {})
            venue_name = place.get('name')
            if venue_name:
                venue_names.add(venue_name)

        # Convert set to a sorted list for JSON serialization
        sorted_venue_names = sorted(list(venue_names))

        # Save to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({"venue_names": sorted_venue_names}, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Extracted {len(venue_names)} distinct venue names and saved to {output_file}")
        return sorted_venue_names