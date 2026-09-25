from datetime import datetime, timedelta
from curl_cffi import requests

TARGET_DATE = "2026-09-27"
OPENING_TIME = "06:00"
CLOSING_TIME = "23:00"

def check_simple_overview():
    url = "https://boeken.majopadel.com/web/api/group/2052/v2/bookings/simpleOverview"
    
    # Exacte query parameters van de werkende browser-call
    params = [
        ("from", "00:00"),
        ("to", "24:00"),
        ("game_type", "doubles"),
        ("camera", "false"),
        ("favourite", "false"),
        ("availability", "1"),
        ("date", TARGET_DATE),
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

    print(f"=== CHECK SIMPLE OVERVIEW VOOR ZONDAG {TARGET_DATE} ===")
    response = requests.get(url, params=params, headers=headers, impersonate="chrome")
    
    if response.status_code != 200:
        print(f"Fout bij ophalen ({response.status_code}):", response.text[:200])
        return

    data = response.json()
    
    # Pak de 'hours' array en neem alleen HH:MM over (bijv. "06:00:00" -> "06:00")
    raw_hours = data.get("hours", [])
    available_times = {h[:5] for h in raw_hours}

    print(f"✅ Beschikbare starttijden op dubbelbanen ({len(available_times)} slots):")
    print(sorted(list(available_times)))

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

    print("\n--- GEBLOKTE / BEZETTE SLOTS OP TARGET TIJDEN ---")
    target_check = ["09:30", "10:00", "10:30", "11:00"]
    for t in target_check:
        status = "❌ BEZET / GEBLOKT" if t in blocked_times else "✅ VRIJ"
        print(f"Slot {t}: {status}")

if __name__ == "__main__":
    check_simple_overview()
