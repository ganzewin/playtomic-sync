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

def fetch_majo_availability(date_str):
    """Haal beschikbaarheid op via de Majopadel API (alleen dubbelbanen Padel 1 t/m 6)."""
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://boeken.majopadel.com/nl/booking"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, impersonate="chrome")
        if response.status_code != 200:
            print(f"Fout bij ophalen {date_str}: HTTP {response.status_code}")
            return set()
        
        data = response.json()
        available_times = set()
        
        court_availability = data.get("court_availability", [])
        for court_item in court_availability:
            court_name = court_item.get("name", "")
            game_type = court_item.get("game", "")
            
            # Negeer de singlebaan (Single 7 / singles)
            if game_type == "singles" or "single" in court_name.lower() or "7" in court_name:
                continue
                
            # Direct over de availability array lopen
            for slot in court_item.get("availability", []):
                start_time = slot.get("start_time", "")  # Formaat is "HH:MM:SS" of "HH:MM"
                if start_time:
                    time_str = start_time[:5]  # Pak "HH:MM"
                    available_times.add(time_str)
                            
        print(f"Dag {date_str}: {len(available_times)} unieke beschikbare starttijden gevonden op dubbelbanen.")
        return available_times

    except Exception as e:
        print(f"Uitzondering bij ophalen {date_str}: {e}")
        return set()
        
def calculate_busy_blocks(date_obj, available_times):
    """Bereken welke uren bezet zijn op basis van ontbrekende starttijden."""
    tz = zoneinfo.ZoneInfo(TIMEZONE)
    busy_blocks = []
    
    current_dt = datetime.combine(date_obj, time(OPENING_HOUR, 0), tzinfo=tz)
    end_day_dt = datetime.combine(date_obj, time(CLOSING_HOUR, 0), tzinfo=tz)
    
    block_start = None
    
    while current_dt < end_day_dt:
        time_str = current_dt.strftime("%H:%M")
        next_dt = current_dt + timedelta(minutes=60)
        
        # Als er op géén enkele dubbelbaan een starttijd is, is de hal op dat uur bezet
        if time_str not in available_times:
            if block_start is None:
                block_start = current_dt
        else:
            if block_start is not None:
                busy_blocks.append((block_start, current_dt))
                block_start = None
                
        current_dt = next_dt
        
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
        
        available_times = fetch_majo_availability(date_str)
        busy_blocks = calculate_busy_blocks(current_date, available_times)
        
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
