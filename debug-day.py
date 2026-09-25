import json
from curl_cffi import requests

TARGET_DATE = "2026-09-27"

def debug_sunday():
    url = "https://boeken.majopadel.com/web/api/group/2052/v2/bookings/checkcart"
    
    # Test 1: Standaard query params
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
    
    print(f"=== FETCHING RAW API DATA FOR {TARGET_DATE} ===")
    response = requests.get(url, params=params, headers=headers, impersonate="chrome")
    
    print(f"HTTP Status: {response.status_code}")
    if response.status_code != 200:
        print("Response text:", response.text[:500])
        return

    data = response.json()
    
    # Print de top-level keys in de JSON response
    print("\nKeys in response JSON:", list(data.keys()))
    
    courts = data.get("court_availability", [])
    print(f"Aantal elementen in court_availability: {len(courts)}")
    
    if courts:
        print("\n--- EERSTE BAAN FULL STRUCTURE DUMP ---")
        print(json.dumps(courts[0], indent=2))
        
        print("\n--- AANTAL SLOTS PER BAAN ---")
        for idx, court in enumerate(courts):
            c_name = court.get("name", f"Baan-{idx}")
            avail = court.get("availability", [])
            durations = court.get("durations", [])
            print(f"{c_name}: {len(avail)} slots direct in 'availability', {len(durations)} items in 'durations'")

if __name__ == "__main__":
    debug_sunday()
