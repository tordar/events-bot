import requests
import time
from datetime import datetime
import json
from typing import List, Dict, Optional, Set
import logging
import os
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import certifi


# Load environment variables
load_dotenv()

class BroadcastAPI:
    def __init__(self, cache_duration_minutes: int = 60):
        self.base_url = "https://www.broadcast.events/api/queryAllEventsByRegion_vM?&region=Oslo&published=true&limit=5000&skip=0"
        self.headers = {
            'User-Agent': 'Friendly Python Script - Personal Use Only - Contact tordar.tommervik@gmail.com',
            'Accept': 'application/json'
        }
        self.cache_file = 'broadcast_cache.json'
        self.cache_duration_minutes = cache_duration_minutes
        self.setup_logging()
        self.mongo_uri = os.getenv('MONGO_URI')
        if not self.mongo_uri:
            raise ValueError("MONGO_URI environment variable is not set")

        self.client = None
        self.db = None
        self.venues_collection = None
        self.tags_collection = None
        self.connect_to_mongodb()

    def connect_to_mongodb(self):
        try:
            # Use certifi to ensure secure connection
            self.client = MongoClient(self.mongo_uri, tlsCAFile=certifi.where())
            # Test the connection
            self.client.admin.command('ping')
            self.db = self.client['event_subscription_db']
            self.venues_collection = self.db['venues']
            self.tags_collection = self.db['tags']
            self.logger.info("Successfully connected to MongoDB Atlas")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            self.logger.error(f"Failed to connect to MongoDB Atlas: {e}")
            self.client = None
            self.db = None
            self.venues_collection = None
            self.tags_collection = None

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

        # Update venues and tags in MongoDB
        self.update_venues_and_tags(extracted_events)

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

    def update_venues_and_tags(self, events: List[Dict]):
        if not self.venues_collection or not self.tags_collection:
            self.logger.error("MongoDB collections are not available. Attempting to reconnect...")

        venues = set()
        tags = set()

        for event in events:
            if event['venue']['name']:
                venues.add(event['venue']['name'])
            tags.update(event['tags'])

        # Update venues
        venue_operations = [
            UpdateOne({'name': venue}, {'$set': {'name': venue}}, upsert=True)
            for venue in venues
        ]
        if venue_operations:
            self.venues_collection.bulk_write(venue_operations)
            self.logger.info(f"Updated {len(venues)} venues in MongoDB")

        # Update tags
        tag_operations = [
            UpdateOne({'name': tag}, {'$set': {'name': tag}}, upsert=True)
            for tag in tags
        ]
        if tag_operations:
            self.tags_collection.bulk_write(tag_operations)
            self.logger.info(f"Updated {len(tags)} tags in MongoDB")

    def get_all_venues(self) -> List[str]:
        return [venue['name'] for venue in self.venues_collection.find({}, {'name': 1, '_id': 0})]

    def get_all_tags(self) -> List[str]:
        return [tag['name'] for tag in self.tags_collection.find({}, {'name': 1, '_id': 0})]