import datetime
import os
import json
from curl_cffi import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Instellingen
TENANT_ID = "f56b0aa2-2b7c-4b77-a163-3c4e72d26a4b"
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
        if response.status_code == 200:
            return response.json()
        print(f"[{date_str}] Fout bij ophalen ({response.status_code}): {response.text[:200]}")
        return []
    except Exception as e:
        print(f"[{date_str}] Exception bij verzoek: {e}")
        return []

def clear_existing_events(start_iso, end_iso):
    """ Wist alle bestaande Playtomic afspraken voor de komende periode (schone lei) """
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
    print(f"Start Playtomic sync voor Padelkapel ({TENANT_ID}) voor de komende {DAYS_AHEAD} dagen (vanaf {today})...")
    
    start_time_iso = datetime.datetime.combine(today, datetime.time.min).isoformat() + 'Z'
    end_time_iso = datetime.datetime.combine(today + datetime.timedelta(days=DAYS_AHEAD), datetime.time.max).isoformat() + 'Z'
    
    # 1. SCHONE LEI: Eerst alle bestaande afspraken opruimen
    clear_existing_events(start_time_iso, end_time_iso)

    total_added = 0

    # Openingstijden van de club (bijv. van 08:00 tot 23:00)
    OPENING_HOUR_START = 8   # 08:00
    OPENING_HOUR_END = 23    # 23:00

    for day_offset in range(DAYS_AHEAD):
        current_date = today + datetime.timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        data = get_playtomic_availability(TENANT_ID, date_str)
        
        if isinstance(data, list) and len(data) > 0:
            # Neem alleen het eerste resource-object als dat de dubbelbaan is,
            # of filter op de specifieke resource
            for resource in data:
                resource_name = (
                    resource.get('name') or 
                    resource.get('resource_name') or 
                    resource.get('properties', {}).get('name', '')
                ).lower()

                # Filter op 'dubbelbaan' of pak de eerste baan als namen leeg zijn
                if "enkel" in resource_name:
                    continue  # Sla enkelbanen over

                slots = resource.get('slots', [])
                
                # Filter ALLEEN de slots met een duur van 60 minuten
                available_times_60 = set()
                for slot in slots:
                    duration = slot.get('duration')
                    start_time = slot.get('start_time')
                    
                    if duration == 60 and start_time:
                        available_times_60.add(start_time)

                # Genereer ALLEEN hele uren (08:00, 09:00, 10:00, etc.)
                current_time = datetime.datetime.combine(current_date, datetime.time(OPENING_HOUR_START, 0))
                end_day_time = datetime.datetime.combine(current_date, datetime.time(OPENING_HOUR_END, 0))

                while current_time < end_day_time:
                    time_str = current_time.strftime("%H:%M:%S")
                    
                    # Als het hele uur NIET beschikbaar is voor 60m, is het slot bezet
                    if time_str not in available_times_60:
                        slot_start_dt = current_time
                        slot_end_dt = current_time + datetime.timedelta(hours=1)
                        
                        event_body = {
                            'summary': 'Playtomic Baan Bezet (Padelkapel)',
                            'description': f'Automatisch geblokkeerd via Playtomic (Dubbelbaan)',
                            'start': {'dateTime': slot_start_dt.isoformat(), 'timeZone': 'Europe/Amsterdam'},
                            'end': {'dateTime': slot_end_dt.isoformat(), 'timeZone': 'Europe/Amsterdam'},
                        }
                        service.events().insert(calendarId=calendar_id, body=event_body).execute()
                        print(f"[+ Toegevoegd] Blokkade op {date_str} van {current_time.strftime('%H:%M')} tot {slot_end_dt.strftime('%H:%M')}")
                        total_added += 1

                    # Stap telkens 1 HEEL UUR verder om dubbelingen en half-uur-overlap te voorkomen
                    current_time += datetime.timedelta(hours=1)

                # We verwerken maar 1 baan (de dubbelbaan) om dubbeling tussen banen te voorkomen
                break

    print(f"Sync voltooid. Totaal {total_added} nieuwe blokkades toegevoegd aan Google Calendar.")

if __name__ == "__main__":
    main()
