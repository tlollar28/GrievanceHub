import re
from datetime import datetime, timedelta
import pdfplumber


MACHINE_CODES = {"4360": "436", "4380": "438", "4390": "439"}


def usps_decimal_time_to_hhmm(decimal_time: str) -> str:
    hours = int(float(decimal_time))
    minutes = round((float(decimal_time) - hours) * 60)

    if minutes == 60:
        hours += 1
        minutes = 0

    hours = hours % 24
    return f"{hours:02d}:{minutes:02d}"


def parse_mmdd_to_date(mmdd: str) -> str:
    month, day = mmdd.split("/")
    return f"2026-{int(month):02d}-{int(day):02d}"


def make_datetime(date_str: str, time_str: str) -> datetime:
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def minutes_between(start_dt: datetime, end_dt: datetime) -> int:
    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    return round((end_dt - start_dt).total_seconds() / 60)


def parse_employee_assignments(
    pdf_path: str,
    craft: str,
    employee_type: str,
    max_pages: int | None = None,
):
    assignments = []
    ring_events = []

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]

        for page in pages:
            text = page.extract_text() or ""

            name_match = re.search(r"Employee Name\s+([A-Z][A-Z\s]+)", text)
            if not name_match:
                continue

            employee_name = name_match.group(1).strip()
            words = page.extract_words() or []

            rows = {}
            for word in words:
                y = round(word["top"] / 3) * 3
                rows.setdefault(y, []).append(word)

            for _, row_words in rows.items():
                row_words = sorted(row_words, key=lambda w: w["x0"])
                row_text = " ".join(w["text"] for w in row_words)

                event_match = re.search(r"\b(BT|OL|IL|MV|ET|OT)\b", row_text)
                date_match = re.search(r"\b(\d{2}/\d{2})\b", row_text)
                time_match = re.search(r"\b(\d{1,2}\.\d{2})\b", row_text)
                machine_match = re.search(r"\b(\d{4}-00)\b", row_text)

                if not event_match or not date_match or not time_match or not machine_match:
                    continue

                date = parse_mmdd_to_date(date_match.group(1))
                time = usps_decimal_time_to_hhmm(time_match.group(1))
                machine = machine_match.group(1)

                ring_events.append({
                    "employee_name": employee_name,
                    "craft": craft,
                    "employee_type": employee_type,
                    "date": date,
                    "machine": machine,
                    "time": time,
                    "datetime": make_datetime(date, time),
                    "event_type": event_match.group(1),
                })

    ring_events.sort(key=lambda x: (x["employee_name"], x["datetime"]))

    for i, event in enumerate(ring_events):
        if event["event_type"] not in ["BT", "MV"]:
            continue

        for next_event in ring_events[i + 1:]:
            if next_event["employee_name"] != event["employee_name"]:
                break

            if next_event["datetime"] <= event["datetime"]:
                continue

            assignments.append({
                "employee_name": event["employee_name"],
                "craft": event["craft"],
                "employee_type": event["employee_type"],
                "date": event["date"],
                "machine": event["machine"],
                "start_time": event["time"],
                "end_time": next_event["time"],
                "duration_minutes": minutes_between(event["datetime"], next_event["datetime"]),
            })
            break

    return assignments
