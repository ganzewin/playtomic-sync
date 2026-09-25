import json
from datetime import datetime, timedelta, time
from curl_cffi import requests

TARGET_DATE = "2026-09-27"

def debug_majo_day(date_str):
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
    
    print(f"=== OPHALEN DATA VOOR {date_str} ===")
    response = requests.get(url, params=params, headers=headers, impersonate="chrome")
    
    if response.status_code != 200:
        print(f"HTTP Fout: {response.status_code}")
        return

    data = response.json()
    court_availability = data.get("court_availability", [])

    print(f"Aantal banen in API-response: {len(court_availability)}\n")

    # Structureer per baan
    banen_data = {}
    
    for court_item in court_availability:
        name = court_item.get("name", "Onbekend")
        game = court_item.get("game", "")
        slots = court_item.get("availability", [])
        
        # Sla single baan over voor dubbelanalyse (of laat staan als je die wel wilt zien)
        is_single = game == "singles" or "single" in name.lower() or "7" in name
        
        times = [s.get("start_time", "")[:5] for s in slots if s.get("start_time")]
        banen_data[name] = {
            "game": game,
            "is_single": is_single,
            "available_times": times,
            "raw_slots_count": len(slots)
        }

    # 1. Print per baan wat de API als 'beschikbaar' geeft
    print("--- 1. OVERZICHT PER BAAN ---")
    for name, info in banen_data.items():
        tag = "[SINGLE]" if info["is_single"] else "[DUBBEL]"
        times_formatted = ", ".join(info["available_times"]) if info["available_times"] else "GEEN (Volledig bezet/geblokt)"
        print(f"{tag} {name}: {len(info['available_times'])} beschikbare slots -> {times_formatted}")

    print("\n--- 2. UUR-VOOR-UUR DRILLDOWN (DUBBELBANEN PADEL 1-6) ---")
    
    # Maak een overzicht per uur van 06:00 tot 23:00
    hourly_summary = {}
    
    # Genereer alle uren van de dag
    start_t = datetime.strptime("06:00", "%H:%M")
    end_t = datetime.strptime("23:00", "%H:%M")
    
    curr = start_t
    while curr <= end_t:
        t_str = curr.strftime("%H:%M")
        available_courts = []
        
        for name, info in banen_data.items():
            if not info["is_single"]:  # Alleen dubbelbanen
                if t_str in info["available_times"]:
                    available_courts.append(name)
                    
        hourly_summary[t_str] = available_courts
        curr += timedelta(minutes=60)

    # Toon status per uur
    fully_booked_slots = []
    
    for t_str, courts in hourly_summary.items():
        count = len(courts)
        if count == 0:
            status = "VOLLEDIG BEZET / GEBLOKT (0 banen vrij)"
            fully_booked_slots.append(t_str)
        else:
            status = f"{count} baan/banen vrij ({', '.join(courts)})"
            
        print(f"{t_str} uur: {status}")

    print("\n--- 3. SAMENVATTING VOLLEDIG GEBLOKTE/BEZETTE UREN ---")
    print(f"Totaal aantal uren waarin ALLE dubbelbanen bezet/geblokt zijn: {len(fully_booked_slots)}")
    print(f"Tijdstippen: {', '.join(fully_booked_slots) if fully_booked_slots else 'Geen enkel uur is volledig bezet'}")

if __name__ == "__main__":
    debug_majo_day(TARGET_DATE)
