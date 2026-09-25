import json
from curl_cffi import requests

TARGET_DATE = "2026-09-27"

def inspect_raw_response(date_str):
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
    
    print(f"=== GET RAW DATA FOR {date_str} ===")
    response = requests.get(url, params=params, headers=headers, impersonate="chrome")
    
    if response.status_code != 200:
        print(f"HTTP Fout: {response.status_code}")
        return

    data = response.json()
    court_availability = data.get("court_availability", [])

    print(f"Totaal aantal banen in JSON: {len(court_availability)}\n")

    for idx, court in enumerate(court_availability):
        court_id = court.get("id")
        court_name = court.get("name") or court.get("title") or (court.get("court", {}).get("name") if isinstance(court.get("court"), dict) else "ONBEKEND")
        game_type = court.get("game")
        
        # Ophalen van alle starttijden in availability
        slots = court.get("availability", [])
        time_list = []
        for s in slots:
            # Check diverse mogelijke veldnamen voor starttijd
            t = s.get("start_time") or s.get("start") or s.get("start_date_time")
            if t:
                time_list.append(str(t))

        print(f"Baan [{idx}] -> ID: {court_id} | Naam: '{court_name}' | Type: '{game_type}'")
        print(f"  -> Aantal slots: {len(slots)}")
        print(f"  -> Gevonden tijden: {time_list[:10]} {'...' if len(time_list) > 10 else ''}")
        print("-" * 60)

if __name__ == "__main__":
    inspect_raw_response(TARGET_DATE)
