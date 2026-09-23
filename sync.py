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

    for day_offset in range(DAYS_AHEAD):
        current_date = today + datetime.timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        data = get_playtomic_availability(TENANT_ID, date_str)
        
        # Eenmalig op dag 1 de exacte JSON structuur printen om te zien wat Playtomic geeft
        if day_offset == 0 and data:
            print(f"--- DEBUG DATA DUMP DAG 1 ---")
            print(json.dumps(data, indent=2)[:1000])
            print(f"-----------------------------")

        if isinstance(data, list):
            for item in data:
                # Check op verschillende veldnamen voor baannaam
                resource_name = (
                    item.get('name') or 
                    item.get('resource_name') or 
                    item.get('properties', {}).get('name', '')
                ).lower()
                
                slots = item.get('slots', [])
                
                for slot in slots:
                    # Controleer op alle mogelijke velden die op 'bezet' kunnen duiden
                    is_available = slot.get('available', True)
                    status = slot.get('status', '').upper()
                    
                    # Een slot is bezet als available False is OF status 'LOCKED'/'BOOKED'/'UNAVAILABLE' is
                    is_blocked = (is_available is False) or (status in ['LOCKED', 'BOOKED', 'UNAVAILABLE', 'RESERVED'])
                    
                    if is_blocked:
                        start_time_str = slot.get('start_time')
                        end_time_str = slot.get('end_time')
                        
                        start_dt = datetime.datetime.fromisoformat(start_time_str)
                        end_dt = datetime.datetime.fromisoformat(end_time_str)
                        
                        start_iso = start_dt.isoformat()
                        
                        if start_iso not in existing_event_keys:
                            event_body = {
                                'summary': 'Playtomic Baan Bezet (Padelkapel)',
                                'description': f'Automatisch geblokkeerd via Playtomic voor {resource_name or "Dubbelbaan"}',
                                'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Europe/Amsterdam'},
                                'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Europe/Amsterdam'},
                            }
                            service.events().insert(calendarId=calendar_id, body=event_body).execute()
                            print(f"[+ Toegevoegd] Blokkade op {start_time_str}")
                            total_added += 1

    print(f"Sync voltooid. Totaal {total_added} nieuwe blokkades toegevoegd aan Google Calendar.")

if __name__ == "__main__":
    main()
