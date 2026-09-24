import datetime
import os
import json
from curl_cffi import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Instellingen
TENANT_ID = "f56b0aa2-2b7c-4b77-a163-3c4e72d26a4b"
COURT_NAME_FILTER = "dubbelbaan"
DAYS_AHEAD = 28

# Google Credentials laden uit GitHub Secrets
SCOPES = ['https://www.googleapis.com/auth/calendar']
creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
calendar_id = os.environ.get("CALENDAR_ID")

if not creds_json or not calendar_id:
    raise ValueError("Missing GOOGLE_CREDENTIALS_JSON or CALENDAR_ID environment variables.")

info = json.loads(creds_json)
credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)

headers = {
    'Referer': 'https://playtomic.com/clubs/padelkapel',
    'Origin': 'https://playtomic.com',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7',
    'x-playtomic-client': 'web',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-mobile': '?0'
}

def get_playtomic_availability(tenant_id, date_str):
    """ Haalt Playtomic availability data op voor een specifieke datum """
    url = "https://playtomic.com/api/clubs/availability"
    params = {
        'tenant_id': tenant_id,
        'date': date_str,
        'sport_id': 'PADEL'
    }
    
    try:
        response = requests.get(
            url, 
            headers=headers, 
            params=params, 
            impersonate="chrome120", 
            timeout=15
        )
        
        print(f"[{date_str}] HTTP Status: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        
        print(f"[{date_str}] Fout bij ophalen ({response.status_code}): {response.text[:200]}")
        return []
    except Exception as e:
        print(f"[{date_str}] Exception bij verzoek: {e}")
        return []

def main():
    today = datetime.date.today()
    print(f"Start Playtomic sync voor Padelkapel ({TENANT_ID}) voor de komende {DAYS_AHEAD} dagen (vanaf {today})...")
    
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

    total_added = 0

    # Definieer de openingstijden (bijv. van 07:00 tot 23:00, elk half uur)
    OPENING_HOUR_START = 7   # 07:00
    OPENING_HOUR_END = 23    # 23:00
    SLOT_DURATION_MINUTES = 30 # Blokken van 30 min of 60 min

    for day_offset in range(DAYS_AHEAD):
        current_date = today + datetime.timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        data = get_playtomic_availability(TENANT_ID, date_str)
        
        if isinstance(data, list) and len(data) > 0:
            for resource in data:
                slots = resource.get('slots', [])
                
                # Verzamel alle starttijden die écht beschikbaar zijn (bijv. "08:00:00", "08:30:00")
                available_times = set()
                for slot in slots:
                    start_time = slot.get('start_time')
                    if start_time:
                        available_times.add(start_time)

                # Genereer alle mogelijke tijdslots tussen openingstijd en sluitingstijd
                current_time = datetime.datetime.combine(current_date, datetime.time(OPENING_HOUR_START, 0))
                end_day_time = datetime.datetime.combine(current_date, datetime.time(OPENING_HOUR_END, 0))

                while current_time < end_day_time:
                    time_str = current_time.strftime("%H:%M:%S")
                    
                    # Als de tijd NIET in de beschikbare tijden zit, is de baan BEZET!
                    if time_str not in available_times:
                        slot_start_dt = current_time
                        slot_end_dt = current_time + datetime.timedelta(minutes=SLOT_DURATION_MINUTES)
                        
                        # ISO format met tijdzone voor Google Calendar
                        start_iso = slot_start_dt.isoformat()
                        
                        if start_iso not in existing_event_keys:
                            event_body = {
                                'summary': 'Playtomic Baan Bezet (Padelkapel)',
                                'description': f'Automatisch geblokkeerd via Playtomic',
                                'start': {'dateTime': slot_start_dt.isoformat(), 'timeZone': 'Europe/Amsterdam'},
                                'end': {'dateTime': slot_end_dt.isoformat(), 'timeZone': 'Europe/Amsterdam'},
                            }
                            service.events().insert(calendarId=calendar_id, body=event_body).execute()
                            print(f"[+ Toegevoegd] Blokkade op {date_str} {time_str}")
                            total_added += 1

                    current_time += datetime.timedelta(minutes=SLOT_DURATION_MINUTES)

    print(f"Sync voltooid. Totaal {total_added} nieuwe blokkades toegevoegd aan Google Calendar.")
    
main()
