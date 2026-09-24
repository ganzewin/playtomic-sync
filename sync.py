import datetime
import os
import json
from zoneinfo import ZoneInfo
from curl_cffi import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Instellingen
TENANT_ID = "f56b0aa2-2b7c-4b77-a163-3c4e72d26a4b"
DAYS_AHEAD = 28
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")

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
    url = "https://playtomic.com/api/clubs/availability"
    params = {
        'tenant_id': tenant_id,
        'date': date_str,
        'sport_id': 'PADEL'
    }
    try:
        response = requests.get(url, headers=headers, params=params, impersonate="chrome120", timeout=15)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"[{date_str}] Exception: {e}")
        return []

def clear_existing_events(start_iso, end_iso):
    print("Oude Playtomic afspraken opruimen uit Google Calendar...")
    page_token = None
    deleted_count = 0

    while True:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_iso,
            timeMax=end_iso,
            q="Playtomic Baan Bezet",
            pageToken=page_token
        ).execute()

        items = events_result.get('items', [])
        for event in items:
            service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
            deleted_count += 1

        page_token = events_result.get('nextPageToken')
        if not page_token:
            break

    print(f"Opschonen voltooid: {deleted_count} oude afspraken verwijderd.")

def main():
    today = datetime.date.today()
    print(f"Start Playtomic sync voor Padelkapel ({TENANT_ID}) voor de komende {DAYS_AHEAD} dagen...")
    
    start_dt_utc = datetime.datetime.combine(today, datetime.time.min, tzinfo=datetime.timezone.utc)
    end_dt_utc = datetime.datetime.combine(today + datetime.timedelta(days=DAYS_AHEAD), datetime.time.max, tzinfo=datetime.timezone.utc)
    
    clear_existing_events(start_dt_utc.isoformat(), end_dt_utc.isoformat())

    total_added = 0

    # Openingstijden UTC (06:00 UTC = 08:00 NL tijd)
    OPENING_HOUR_UTC_START = 6
    OPENING_HOUR_UTC_END = 21

    for day_offset in range(DAYS_AHEAD):
        current_date = today + datetime.timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        data = get_playtomic_availability(TENANT_ID, date_str)
        
        if isinstance(data, list) and len(data) > 0:
            for resource in data:
                resource_name = (
                    resource.get('name') or 
                    resource.get('resource_name') or 
                    resource.get('properties', {}).get('name', '')
                ).lower()

                if "enkel" in resource_name:
                    continue  # Negeer enkelbaan

                slots = resource.get('slots', [])
                
                # Bepaal alle 30-minuten intervallen die ÉCHT vrij zijn om te spelen
                free_30min_intervals = set()
                for slot in slots:
                    start_str = slot.get('start_time')
                    duration = slot.get('duration', 0)
                    if start_str and duration > 0:
                        # Converteer HH:MM:SS naar een time object
                        h, m, s = map(int, start_str.split(':'))
                        slot_start_dt = datetime.datetime.combine(current_date, datetime.time(h, m), tzinfo=datetime.timezone.utc)
                        
                        # Voeg elk half uur van dit vrije slot toe aan de vrije verzameling
                        num_half_hours = duration // 30
                        for i in range(num_half_hours):
                            interval_time = slot_start_dt + datetime.timedelta(minutes=30 * i)
                            free_30min_intervals.add(interval_time)

                # Doorloop de dag in stappen van 30 minuten
                current_time_utc = datetime.datetime.combine(current_date, datetime.time(OPENING_HOUR_UTC_START, 0), tzinfo=datetime.timezone.utc)
                end_day_utc = datetime.datetime.combine(current_date, datetime.time(OPENING_HOUR_UTC_END, 0), tzinfo=datetime.timezone.utc)

                busy_intervals = []
                current_block_start = None

                while current_time_utc < end_day_utc:
                    # Als dit halfuur NIET in de vrije intervallen zit, is de baan bezet
                    if current_time_utc not in free_30min_intervals:
                        if current_block_start is None:
                            current_block_start = current_time_utc
                    else:
                        if current_block_start is not None:
                            busy_intervals.append((current_block_start, current_time_utc))
                            current_block_start = None

                    current_time_utc += datetime.timedelta(minutes=30)

                if current_block_start is not None:
                    busy_intervals.append((current_block_start, current_time_utc))

                # Maak de afspraken aan in Google Calendar
                for block_start_utc, block_end_utc in busy_intervals:
                    start_local = block_start_utc.astimezone(LOCAL_TZ)
                    end_local = block_end_utc.astimezone(LOCAL_TZ)
                    
                    event_body = {
                        'summary': 'Playtomic Baan Bezet (Padelkapel)',
                        'description': 'Automatisch geblokkeerd via Playtomic (Dubbelbaan)',
                        'start': {'dateTime': start_local.isoformat()},
                        'end': {'dateTime': end_local.isoformat()},
                    }
                    service.events().insert(calendarId=calendar_id, body=event_body).execute()
                    print(f"[+ Toegevoegd] Blokkade op {start_local.strftime('%Y-%m-%d %H:%M')} tot {end_local.strftime('%H:%M')}")
                    total_added += 1

                break

    print(f"Sync voltooid. Totaal {total_added} nieuwe samengevoegde blokkades toegevoegd.")

if __name__ == "__main__":
    main()
