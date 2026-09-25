import os
import json
from datetime import datetime, timedelta, time
import zoneinfo
from curl_cffi import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Instellingen
DAYS_AHEAD = 14     # Aantal dagen vooruit synchroniseren
TIMEZONE = "Europe/Amsterdam"
CALENDAR_ID = os.environ.get("MAJO_CALENDAR_ID")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

# Openingstijden (06:00 tot 23:00)
OPENING_HOUR = 6
CLOSING_HOUR = 23

def get_google_calendar_service():
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    scopes = ['https://www.googleapis.com/auth/calendar']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return build('calendar', 'v3', credentials=creds)

def clear_existing_events(service, calendar_id, start_dt, end_dt):
    """Verwijder bestaande geautomatiseerde events in de periode om dubbelingen te voorkomen."""
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.isoformat(),
        timeMax=end_dt.isoformat(),
        singleEvents=True
    ).execute()
    
    events = events_result.get('items', [])
    for event in events:
        if event.get('description') == "MAJO_SYNC_AUTO":
            service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()

def fetch_majo_blocked_slots(date_str):
    """
    Haalt via de simpleOverview API alle beschikbare starttijden op 
    en berekent welke 30-minuten slots tussen OPENING_HOUR en CLOSING_HOUR BEZET/GEBLOKT zijn.
    """
    url = "https://boeken.majopadel.com/web/api/group/2052/v2/bookings/simpleOverview"
    
    params = [
        ("from", "00:00"),
        ("to", "24:00"),
        ("game_type", "doubles"),
        ("camera", "false"),
        ("favourite", "false"),
        ("availability", "1"),
        ("date", date_str),
        ("durations[]", "60"),
        ("durations[]", "90"),
        ("durations[]", "120"),
        ("firstRequest", "0")
    ]
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "referer": "https://boeken.majopadel.com/nl/booking",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest"
    }

    try:
        response = requests.get(url, params=params, headers=headers, impersonate="chrome")
        if response.status_code != 200:
            print(f"Fout bij ophalen {date_str}: HTTP {response.status_code}")
            return []

        data = response.json()
        raw_hours = data.get("hours", [])
        # Maak van "06:00:00" -> "06:00"
        available_times = {h[:5] for h in raw_hours}

        tz = zoneinfo.ZoneInfo(TIMEZONE)
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        curr_dt = datetime.combine(date_obj, time(OPENING_HOUR, 0), tzinfo=tz)
        end_dt = datetime.combine(date_obj, time(CLOSING_HOUR, 0), tzinfo=tz)

        blocked_slots = []
        while curr_dt <= end_dt:
            t_str = curr_dt.strftime("%H:%M")
            if t_str not in available_times:
                blocked_slots.append(curr_dt)
            curr_dt += timedelta(minutes=30)

        return blocked_slots
    except Exception as e:
        print(f"Exception bij ophalen {date_str}: {e}")
        return []

def group_blocked_slots_into_events(blocked_slots):
    """Samenvoegen van aaneengesloten 30-minuten blokken tot één aaneengesloten event."""
    if not blocked_slots:
        return []

    events = []
    start_time = blocked_slots[0]
    prev_time = blocked_slots[0]

    for slot in blocked_slots[1:]:
        if slot == prev_time + timedelta(minutes=30):
            prev_time = slot
        else:
            events.append((start_time, prev_time + timedelta(minutes=30)))
            start_time = slot
            prev_time = slot

    events.append((start_time, prev_time + timedelta(minutes=30)))
    return events

def sync_majo():
    if not CALENDAR_ID or not GOOGLE_CREDENTIALS_JSON:
        raise ValueError("MAJO_CALENDAR_ID of GOOGLE_CREDENTIALS_JSON ontbreekt in omgevingsvariabelen.")
        
    service = get_google_calendar_service()
    tz = zoneinfo.ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()
    
    start_sync = datetime.combine(today, time(0, 0), tzinfo=tz)
    end_sync = datetime.combine(today + timedelta(days=DAYS_AHEAD), time(23, 59), tzinfo=tz)
    
    print(f"Schoonmaken van Majo agenda van {start_sync.date()} t/m {end_sync.date()}...")
    clear_existing_events(service, CALENDAR_ID, start_sync, end_sync)
    
    total_events_created = 0
    
    for i in range(DAYS_AHEAD):
        current_date = today + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        
        blocked_slots = fetch_majo_blocked_slots(date_str)
        busy_blocks = group_blocked_slots_into_events(blocked_slots)
        
        for start_dt, end_dt in busy_blocks:
            event = {
                'summary': 'Majo Padel Bezet',
                'description': 'MAJO_SYNC_AUTO',
                'start': {'dateTime': start_dt.isoformat()},
                'end': {'dateTime': end_dt.isoformat()},
            }
            service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
            total_events_created += 1
            
        print(f"Dag {date_str}: {len(busy_blocks)} bezette blokken aangemaakt.")
        
    print(f"Sync voltooid! In totaal {total_events_created} events aangemaakt.")

if __name__ == "__main__":
    sync_majo()
