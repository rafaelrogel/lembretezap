from backend.reminder_flow import parse_date_from_response, compute_in_seconds_from_date_hour, has_full_event_datetime
from backend.time_parse import parse_lembrete_time
from datetime import datetime
import zoneinfo

def test_dates():
    tz = "America/Sao_Paulo"
    msg = "me lembra de pagar aluguel dia 22 às 9h"
    is_full = has_full_event_datetime(msg)
    parsed_full = parse_lembrete_time(msg, tz_iana=tz)
    print(f"Full message: '{msg}' -> is_full: {is_full}, parsed: {parsed_full}")
    
    test_cases = ["22/03", "dia 22/03", "22", "dia 22", "todo dia 21: pagar contas"]
    
    for tc in test_cases:
        if "todo" in tc:
            res = parse_lembrete_time(tc)
            print(f"Input: {tc} -> {res}")
            continue
        pd = parse_date_from_response(tc)
        print(f"Input: {tc} -> Parsed: {pd}")
        if pd:
            in_sec = compute_in_seconds_from_date_hour(pd, 9, 0, tz)
            print(f"  in_seconds: {in_sec}")

if __name__ == "__main__":
    test_dates()
