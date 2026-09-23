import datetime
import os
import json
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Instellingen
TENANT_ID = "padelkapel"
COURT_NAME_FILTER = "dubbelbaan"  # Filtert specifiek op de dubbelbaan
DAYS_AHEAD = 28                  # 4 weken vooruit kijken

# Google Credentials laden uit GitHub Secrets
SCOPES = ['https://www.googleapis.com/auth/calendar']
creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
calendar_id = os.environ.get("CALENDAR_ID")

if not creds_json or not calendar_id:
    raise ValueError("Missing GOOGLE_CREDENTIALS_JSON or CALENDAR_ID environment variables.")

info = json.loads(creds_json)
credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)

def get_playtomic_availability(date_str):
    """ Haalt de banen en tijdsloten op van de Playtomic API voor een specifieke datum """
    # Officiële interne publieke API endpoint van Playtomic
    url = f"https://playtomic.io/api/v1/tenants/{TENANT_ID}/availability?date={date_str}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Fout bij ophalen Playtomic voor {date_str}: Status {response.status_code}")
            return []
    except Exception as e:
        print(f"Exception bij ophalen Playtomic data: {e}")
        return []

def main():
    today = datetime.date.today()
    print(f"Start Playtomic sync voor de komende {DAYS_AHEAD} dagen (vanaf {today})...")
    
    # 1. Haal bestaande Playtomic blokkades op uit Google Calendar om dubbelingen te voorkomen
    start_time_iso = datetime.datetime.combine(today, datetime.time.min).isoformat() + 'Z'
    end_time_iso = datetime.datetime.combine(today + datetime.timedelta(days=DAYS_AHEAD), datetime.time.max).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time_iso,
        timeMax=end_time_iso,
        singleEvents=True,
        q="Playtomic Baan Bezet"
    ).execute()
    
    existing_events = events_result.get('items', [])
    existing_event_keys = set()
    
    for event in existing_events:
        start = event['start'].get('dateTime')
        if start:
            existing_event_keys.add(start)

    # 2. Doorlopen van de komende 28 dagen
    for day_offset in range(DAYS_AHEAD):
        current_date = today + datetime.timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        data = get_playtomic_availability(date_str)
        
        for item in data:
            resource_name = item.get('resource_name', '').lower()
            
            # Check of het de Dubbelbaan betreft
            if COURT_NAME_FILTER in resource_name:
                slots = item.get('slots', [])
                for slot in slots:
                    # Als een slot niet beschikbaar is (bezet)
                    if not slot.get('available', True):
                        start_time_str = slot.get('start_time') # e.g. "2026-09-26T18:00:00"
                        end_time_str = slot.get('end_time')
                        
                        # Converteer naar ISO format voor Google Calendar
                        start_dt = datetime.datetime.fromisoformat(start_time_str)
                        end_dt = datetime.datetime.fromisoformat(end_time_str)
                        
                        start_iso = start_dt.isoformat()
                        
                        # Voeg toe als de blokkade nog niet in de agenda staat
                        if start_iso not in existing_event_keys:
                            event_body = {
                                'summary': 'Playtomic Baan Bezet (Padelkapel)',
                                'description': f'Automatisch geblokkeerd via Playtomic voor {resource_name}',
                                'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Europe/Amsterdam'},
                                'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Europe/Amsterdam'},
                            }
                            service.events().insert(calendarId=calendar_id, body=event_body).execute()
                            print(f"[+ Toegevoegd] Blokkade op {start_time_str} voor {resource_name}")

if __name__ == "__main__":
    main()
