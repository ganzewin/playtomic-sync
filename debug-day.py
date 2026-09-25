import json
from curl_cffi import requests

TARGET_DATE = "2026-09-27"

def debug_sunday_slots():
    url = "https://boeken.majopadel.com/web/api/group/2052/v2/bookings/checkcart"
    
    params = {
        "from": "06:00",
        "to": "24:00",
        "camera": "false",
        "favourite": "false",
        "availability": "1",
        "date": TARGET_DATE
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://boeken.majopadel.com/nl/booking"
    }
    
    print(f"=== ANALYSE ZONDAG {TARGET_DATE} ===")
    response = requests.get(url, params=params, headers=headers, impersonate="chrome")
    
    if response.status_code != 200:
        print(f"HTTP Fout: {response.status_code}")
        return

    data = response.json()
    courts = data.get("court_availability", [])

    # Structuur opslaan per dubbelbaan
    court_slots = {}  # { 'Padel 1': set('06:00', ...), ... }

    for court_item in courts:
        court_info = court_item.get("court", {})
        court_name = court_info.get("name", "")
        game_type = court_info.get("game", "")
        
        # Sla singlebaan over
        if game_type == "singles" or "single" in court_name.lower() or "7" in court_name:
            continue
            
        times_found = set()
        
        # Doorzoek ALLE durations (60, 90, 120 min)
        for dur in court_item.get("durations", []):
            dur_len = dur.get("duration")
            for slot in dur.get("availability", []):
                start_dt = slot.get("start_date_time", "")
                if " " in start_dt:
                    time_str = start_dt.split(" ")[1][:5]
                    times_found.add(f"{time_str} ({dur_len}m)")

        court_slots[court_name] = times_found

    print("\n--- 1. BESCHIKBARE SLOTS PER DUBBELBAAN ---")
    for name, slots in court_slots.items():
        sorted_slots = sorted(list(slots))
        print(f"{name}: {len(sorted_slots)} slots -> {sorted_slots if sorted_slots else 'GEEN BESCHIKBAARHEID'}")

    print("\n--- 2. SPECIFIEKE CHECK OP JOUW TARGET TIJDEN ---")
    target_times = ["09:30", "10:00", "10:30", "11:00"]
    
    for t in target_times:
        free_courts = []
        for name, slots in court_slots.items():
            # Check of er een slot begint op deze tijd
            if any(s.startswith(t) for s in slots):
                free_courts.append(name)
                
        if not free_courts:
            print(f"❌ {t} uur: GEEN ENKELE DUBBELBAAN VRIJ (Bezet / Geblokt)")
        else:
            print(f"✅ {t} uur: Vrij op {len(free_courts)} baan/banen ({', '.join(free_courts)})")

if __name__ == "__main__":
    debug_sunday_slots()
