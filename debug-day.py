import json
from datetime import datetime, timedelta
from curl_cffi import requests

TARGET_DATE = "2026-09-27"
OPENING_TIME = "06:00"
CLOSING_TIME = "23:00"

def debug_simple_overview():
    # Nieuw endpoint en exacte querystring
    url = "https://boeken.majopadel.com/web/api/group/2052/v2/bookings/simpleOverview"
    
    params = [
        ("from", "00:00"),
        ("to", "24:00"),
        ("game_type", "doubles"),
        ("camera", "false"),
        ("favourite", "false"),
        ("availability", "1"),
        ("date", TARGET_DATE),
        ("durations[]", "120"),
        ("durations[]", "90"),
        ("durations[]", "60"),
        ("firstRequest", "0")
    ]
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "referer": "https://boeken.majopadel.com/nl/booking",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest"
    }

    print(f"=== CHECK SIMPLE OVERVIEW VOOR ZONDAG {TARGET_DATE} ===")
    response = requests.get(url, params=params, headers=headers, impersonate="chrome")
    
    print(f"HTTP Status: {response.status_code}")
    if response.status_code != 200:
        print("Fout bij ophalen:", response.text[:500])
        return

    data = response.json()
    
    # Haal alle beschikbare starttijden op uit de response
    # Afhankelijk van de JSON structuur van simpleOverview
    available_times = set()
    
    # 1. Inspecteer root keys
    print("Response keys:", list(data.keys()) if isinstance(data, dict) else "Lijst van items")
    
    # Mogelijke structuren verwerken (lijst van tijden of dict met slots/availability)
    slots = []
    if isinstance(data, dict):
        slots = data.get("availability", []) or data.get("slots", []) or data.get("times", [])
    elif isinstance(data, list):
        slots = data

    for slot in slots:
        if isinstance(slot, dict):
            t = slot.get("start_time") or slot.get("time") or slot.get("start")
        else:
            t = str(slot)
            
        if t:
            time_clean = t.split(" ")[-1][:5] if " " in str(t) else str(t)[:5]
            available_times.add(time_clean)

    print(f"\n✅ Beschikbare starttijden op dubbelbanen ({len(available_times)} stuks):")
    print(sorted(list(available_times)))

    # Compare tegen alle halfuurs-intervallen tussen 06:00 en 23:00
    print("\n--- STATUS PER 30 MINUTEN (06:00 - 23:00) ---")
    curr = datetime.strptime(OPENING_TIME, "%H:%M")
    end = datetime.strptime(CLOSING_TIME, "%H:%M")
    
    blocked_times = []
    
    while curr <= end:
        t_str = curr.strftime("%H:%M")
        if t_str in available_times:
            print(f"✅ {t_str} : VRIJ")
        else:
            print(f"❌ {t_str} : BEZET / GEBLOKT")
            blocked_times.append(t_str)
        curr += timedelta(minutes=30)

    print("\n--- TOTAAL OVERZICHT GEBLOKTE/BEZETTE SLOTS ---")
    print(f"Geblokt op zondag: {', '.join(blocked_times) if blocked_times else 'Geen'}")

if __name__ == "__main__":
    debug_simple_overview()
