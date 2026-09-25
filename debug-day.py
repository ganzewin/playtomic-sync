import json
from datetime import datetime, timedelta
from curl_cffi import requests

TARGET_DATE = "2026-09-27"

def debug_with_curl_headers():
    url = "https://boeken.majopadel.com/web/api/group/2052/v2/bookings/checkcart"
    
    params = {
        "from": "06:00",
        "to": "24:00",
        "camera": "false",
        "favourite": "false",
        "availability": "1",
        "date": TARGET_DATE
    }
    
    # Exacte headers en cookies uit jouw cURL
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-NL,en;q=0.9,nl-NL;q=0.8,nl;q=0.7,en-GB;q=0.6,en-US;q=0.5",
        "priority": "u=1, i",
        "referer": "https://boeken.majopadel.com/nl/booking",
        "sec-ch-ua": '"Google Chrome";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest",
        "x-socket-id": "295510.371654",
        "x-xsrf-token": "eyJpdiI6Ii9oWHVkNFJwV0pMQzMrOTVDQ1JwOHc9PSIsInZhbHVlIjoidzZDKzdzbU9aSkF0Rkl1WnBwV25XS29uQUlLbVFCVkVZNEVjQXVJYU44WjMySE41SzVKUnFHY1lWTW1pUDRtdmNEZ0Y0a1FpQlV2eXZQb2dEVDBLSDEvY015MTNhYm1YVFRuZVdTRFdRNy93TUprUStFQkxXN0xmcTlVWHZ6OTEiLCJtYWMiOiJjOGNmMGExYWNiOGFkNDk2YmY3ZTA5MzUxODlmNWU5OGNiZDNhY2NlOGM3NDMyZjIwODQ4NTNlMTI1MTY0YjZiIiwidGFnIjoiIn0=",
        "cookie": "sf_cookies_consent_selection=2026-07-v3; sf_cookies_consent_essential=1; sf_cookies_consent_analytics=1; sf_cookies_consent_marketing=1; _fbp=fb.1.1790333709877.924447911511706000; __stripe_mid=97b9257e-36fa-4ede-82c3-8c449405ca0ce63dda; __stripe_sid=1bb385bc-50be-4885-a298-b50c5478446ea2ba44; XSRF-TOKEN=eyJpdiI6Ii9oWHVkNFJwV0pMQzMrOTVDQ1JwOHc9PSIsInZhbHVlIjoidzZDKzdzbU9aSkF0Rkl1WnBwV25XS29uQUlLbVFCVkVZNEVjQXVJYU44WjMySE41SzVKUnFHY1lWTW1pUDRtdmNEZ0Y0a1FpQlV2eXZQb2dEVDBLSDEvY015MTNhYm1YVFRuZVdTRFdRNy93TUprUStFQkxXN0xmcTlVWHZ6OTEiLCJtYWMiOiJjOGNmMGExYWNiOGFkNDk2YmY3ZTA5MzUxODlmNWU5OGNiZDNhY2NlOGM3NDMyZjIwODQ4NTNlMTI1MTY0YjZiIiwidGFnIjoiIn0%3D; racketiq_cookie=eyJpdiI6IjQ3S3hjMHk0QmpWaHFXeWh5Y1E2YXc9PSIsInZhbHVlIjoiblZ6ZzhFVlM1R0s4cGZ2azJaWkJnbHRKTk9xZWJTZytXR0syUE5YV1dQR285cTRXTFh5cXdjR0RCbGpwdEM3SG9sZ1RXUTNCVFMxSjZFL3Q5cXFPcktsUjBmVW9ZYjAyck5IcC9OeUdvaENTejhCUXVYNkN4QTVyMzUyMWw4TjEiLCJtYWMiOiIxMmMyMGEzNmQ0YTg2MTQ0ZWUyNmU5YmMyMGM4OWQ2NWE5YTEyODI5OThlNDcwMTY4MzMyMTE3MGYyYWJhZDdmIiwidGFnIjoiIn0%3D"
    }

    print(f"=== OPHALEN DATA VOOR ZONDAG {TARGET_DATE} ===")
    response = requests.get(url, params=params, headers=headers, impersonate="chrome")
    
    if response.status_code != 200:
        print(f"HTTP Fout: {response.status_code}")
        return

    data = response.json()
    courts = data.get("court_availability", [])
    
    print(f"Aantal banen in API-response: {len(courts)}\n")
    
    all_free_times = {}  # { "06:00": ["Padel 1", "Padel 2"], ... }
    
    print("--- 1. SAMENVATTING PER DUBBELBAAN ---")
    for court_item in courts:
        court_info = court_item.get("court", {})
        court_name = court_info.get("name", "")
        game_type = court_info.get("game", "")
        
        # Sla Single 7 over
        if game_type == "singles" or "single" in court_name.lower() or "7" in court_name:
            continue
            
        court_times = set()
        for dur in court_item.get("durations", []):
            for slot in dur.get("availability", []):
                start_dt = slot.get("start_date_time", "")
                if " " in start_dt:
                    t_str = start_dt.split(" ")[1][:5]
                    court_times.add(t_str)
                    
                    if t_str not in all_free_times:
                        all_free_times[t_str] = []
                    if court_name not in all_free_times[t_str]:
                        all_free_times[t_str].append(court_name)

        sorted_times = sorted(list(court_times))
        print(f"{court_name}: {len(sorted_times)} starttijden -> {sorted_times[:8]} ... (totaal {len(sorted_times)})")

    print("\n--- 2. OVERZICHT PER TIJDSTIP (06:00 - 23:00) ---")
    curr = datetime.strptime("06:00", "%H:%M")
    end = datetime.strptime("23:00", "%H:%M")
    
    blocked_slots = []
    
    while curr <= end:
        t = curr.strftime("%H:%M")
        courts_free = all_free_times.get(t, [])
        if courts_free:
            print(f"✅ {t} : VRIJ op {len(courts_free)} baan/banen ({', '.join(courts_free)})")
        else:
            print(f"❌ {t} : GEBLOKT / BEZET (0 banen vrij)")
            blocked_slots.append(t)
        curr += timedelta(minutes=30)

    print("\n--- 3. ALLE GEBLOKTE/BEZETTE TIJDSTIPPEN OP ZONDAG ---")
    print(f"Geblokt/Bezet: {', '.join(blocked_slots) if blocked_slots else 'Geen enkel tijdstip geblokt'}")

if __name__ == "__main__":
    debug_with_curl_headers()
