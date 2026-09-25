import os
from datetime import datetime, timedelta
from curl_cffi import requests

# Google Calendar API imports (indien gebruikt in je project)
# from googleapiclient.discovery import build
# from google.oauth2.credentials import Credentials

OPENING_TIME = "06:00"
CLOSING_TIME = "23:00"

def fetch_blocked_slots(date_str):
    """
    Haalt via de simpleOverview API alle beschikbare starttijden op 
    en berekent welke slots tussen OPENING_TIME en CLOSING_TIME BEZET/GEBLOKT zijn.
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

    response = requests.get(url, params=params, headers=headers, impersonate="chrome")
    if response.status_code != 200:
        print(f"❌ Fout bij ophalen {date_str} ({response.status_code})")
        return []

    data = response.json()
    raw_hours = data.get("hours", [])
    available_times = {h[:5] for h in raw_hours}

    blocked_slots = []
    curr = datetime.strptime(f"{date_str} {OPENING_TIME}", "%Y-%m-%d %H:%M")
    end = datetime.strptime(f"{date_str} {CLOSING_TIME}", "%Y-%m-%d %H:%M")

    while curr <= end:
        t_str = curr.strftime("%H:%M")
        if t_str not in available_times:
            blocked_slots.append(curr)
        curr += timedelta(minutes=30)

    return blocked_slots

def group_blocked_slots_into_events(blocked_slots):
    """
    Voegt opeenvolgende 30-minuten geblokte slots samen tot één event (bijv. 09:30 tot 11:00).
    """
    if not blocked_slots:
        return []

    events = []
    start_time = blocked_slots[0]
    prev_time = blocked_slots[0]

    for slot in blocked_slots[1:]:
        if slot == prev_time + timedelta(minutes=30):
            prev_time = slot
        else:
            # Einde van een aaneengesloten geblokt blok
            events.append((start_time, prev_time + timedelta(minutes=30)))
            start_time = slot
            prev_time = slot

    events.append((start_time, prev_time + timedelta(minutes=30)))
    return events

def sync_to_google_calendar(events, date_str):
    """
    Plaats hier je bestaande Google Calendar Sync/API logica.
    """
    print(f"\n--- SYNCRONISEREN NAAR GOOGLE CALENDAR VOOR {date_str} ---")
    if not events:
        print("Geen geblokte of bezette tijden gevonden.")
        return

    for start_dt, end_dt in events:
        summary = "Majo Padel - Banen Bezet / Geblokt"
        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
        end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
        
        print(f"📅 Agenda Event: '{summary}' van {start_dt.strftime('%H:%M')} tot {end_dt.strftime('%H:%M')}")
        
        # Voorbeeld Google Calendar API call:
        # event = {
        #     'summary': summary,
        #     'start': {'dateTime': start_iso, 'timeZone': 'Europe/Amsterdam'},
        #     'end': {'dateTime': end_iso, 'timeZone': 'Europe/Amsterdam'},
        # }
        # calendar_service.events().insert(calendarId='primary', body=event).execute()

def main():
    # Dynamisch of voor specifieke dagen (bijv. aankomende week / specifieke datum)
    target_dates = ["2026-09-27"] 

    for date_str in target_dates:
        print(f"\n==================================================")
        print(f" OPHALEN GEBLOKTE SLOTS VOOR: {date_str}")
        print(f"==================================================")
        
        blocked_slots = fetch_blocked_slots(date_str)
        events = group_blocked_slots_into_events(blocked_slots)
        
        print(f"Aantal geblokte tijdsblokken: {len(events)}")
        for start_dt, end_dt in events:
            print(f" ❌ Geblokt/Bezet: {start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}")
            
        sync_to_google_calendar(events, date_str)

if __name__ == "__main__":
    main()
