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
CALENDAR_ID = os.environ.get("MAJO_CALENDAR_ID")  # Google Calendar ID
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

# Openingstijden (06:00 - 23:00)
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

def fetch_majo_available_times(date_str):
    """
    Haalt alle starttijden op waarop minstens ÉÉN dubbelbaan (Padel 1-6) VRIJ is.
    """
    url = "https://boeken.majopadel.com/web/api/group/2052/v2/bookings/checkcart"
    
    params = {
        "from": "06:00",
        "to": "24:00",
        "camera": "false",
        "favourite": "false",
        "availability": "1",
        "date": date_str
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://boeken.majopadel.com/nl/booking"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, impersonate="chrome")
        if response.status_code != 200:
            print(f"Fout bij ophalen {date_str}: HTTP {response.status_code}")
            return set()
        
        data = response.json()
        available_start_times = set()
        
        court_availability = data.get("court_availability", [])
        for court_item in court_availability:
            # 1. Haal de baaninformatie op uit het geneste 'court' object
            court_info = court_item.get("court", {})
            court_name = court_info.get("name", "")
            game_type = court_info.get("game", "")
            
            # Negeer Single 7 / singlebanen
            if game_type == "singles" or "single" in court_name.lower() or "7" in court_name:
                continue
                
            # 2. Doorzoek de 'durations' array naar 60-minuten slots
            for dur in court_item.get("durations", []):
                if str(dur.get("duration")) == "60":
                    for slot in dur.get("availability", []):
                        start_dt = slot.get("start_date_time", "")
                        if " " in start_dt:
                            # '2026-09-27 06:00:00' -> pak '06:00'
                            time_str = start_dt.split(" ")[1][:5]
                            available_start_times.add(time_str)
                            
        print(f"Dag {date_str}: {len(available_start_times)} unieke starttijden gevonden op dubbelbanen.")
        return available_start_times

    except Exception as e:
        print(f"Uitzondering bij ophalen {date_str}: {e}")
        return set()
        
def calculate_busy_blocks(date_obj, available_start_times):
    """
    Bepaalt welke uren GEBLOKT/BEZET zijn (wanneer er géén enkele dubbelbaan vrij is).
    Voegt aaneengesloten bezette uren samen tot grotere blokken.
    """
    tz = zoneinfo.ZoneInfo(TIMEZONE)
    busy_blocks = []
    
    current_dt = datetime.combine(date_obj, time(OPENING_HOUR, 0), tzinfo=tz)
    end_day_dt = datetime.combine(date_obj, time(CLOSING_HOUR, 0), tzinfo=tz)
    
    block_start = None
    
    while current_dt < end_day_dt:
        time_str = current_dt.strftime("%H:%M")
        next_dt = current_dt + timedelta(minutes=60)
        
        # Als het tijdstip NIET in de beschikbare starttijden zit, zijn alle banen bezet op dit uur
        if time_str not in available_start_times:
            if block_start is None:
                block_start = current_dt
        else:
            # Er is weer een baan vrij, sluit het eventuele bezette blok af
            if block_start is not None:
                busy_blocks.append((block_start, current_dt))
                block_start = None
                
        current_dt = next_dt
        
    # Afsluiten als de dag eindigt met bezette uren
    if block_start is not None:
        busy_blocks.append((block_start, current_dt))
        
    return busy_blocks

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
        
        available_start_times = fetch_majo_available_times(date_str)
        busy_blocks = calculate_busy_blocks(current_date, available_start_times)
        
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
