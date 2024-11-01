
from broadcast_api import BroadcastAPI
from datetime import datetime


def display_events(events):

    for event in events:
        print(f"\n🎵 {event['name']}")
        print(f"📅 {event['start_time'][:10] if event['start_time'] else 'Date not set'}")
        print(f"💰 {event['cover_charge'] if event['cover_charge'] else 'Price not listed'}")
        print(f"🎫 {'SOLD OUT!' if event.get('sold_out') else 'Tickets available'}")
        if event.get('tags'):
            print(f"🏷️  {', '.join(event['tags'])}")
            # Add venue information
            if event['venue'] and event['venue'].get('name'):
                print(f"📍 {event['venue']['name']}")
            else:
                print("📍 Venue not specified")
    print(f"\nTotal number of events: {len(events)}")

def main():
    api = BroadcastAPI()

    print("Fetching upcoming events ...")
    all_events = api.get_upcoming_events()
    #api.update_venues_and_tags()


    print("\nAll upcoming events:")
    print("-" * 50)
    display_events(all_events[:5000])  # Show first 5 events
    #api.extract_venue_names()




if __name__ == "__main__":
    main()