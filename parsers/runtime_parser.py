import re
from datetime import datetime, timedelta
import pdfplumber


CHART_X0 = 120.75
CHART_X1 = 760.0
CHART_TOTAL_MINUTES = 24 * 60

MACHINE_COLORS = {
    (1.0, 0.565, 0.251): "439",      # orange
    (0.941, 0.78, 0.565): "438",     # tan
    (0.686, 0.686, 0.933): "436",    # purple
}


def duration_to_minutes(duration: str) -> int:
    hours, minutes, seconds = duration.split(":")
    total = int(hours) * 60 + int(minutes)

    if int(seconds) >= 30:
        total += 1

    return total


def x_to_minutes(x: float) -> int:
    minutes = round(((x - CHART_X0) / (CHART_X1 - CHART_X0)) * CHART_TOTAL_MINUTES)
    return max(0, min(minutes, CHART_TOTAL_MINUTES))


def minutes_to_datetime(report_date: str, minutes_after_7am: int) -> str:
    base_date = datetime.strptime(report_date, "%B %d, %Y")
    chart_start = base_date.replace(hour=7, minute=0, second=0)

    result = chart_start + timedelta(minutes=minutes_after_7am)
    return result.strftime("%Y-%m-%d %H:%M")


def find_duration_near_rect(words, rect):
    nearby_words = []

    for word in words:
        inside_rect_area = (
            word["x0"] >= rect["x0"] - 5
            and word["x1"] <= rect["x1"] + 5
            and word["top"] >= rect["top"] - 5
            and word["bottom"] <= rect["bottom"] + 20
        )

        if inside_rect_area:
            nearby_words.append(word["text"])

    block_text = " ".join(nearby_words)
    duration_match = re.search(r"\b\d+:\d{2}:\d{2}\b", block_text)

    if not duration_match:
        return None

    return duration_match.group(0)


def parse_runtime_report(pdf_path: str):
    sessions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            date_match = re.search(
                r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
                text
            )

            if not date_match:
                continue

            report_date = date_match.group(2)
            words = page.extract_words()

            for rect in page.rects:
                color = rect.get("non_stroking_color")

                if color not in MACHINE_COLORS:
                    continue

                # Filters out tiny chart/table rectangles.
                if rect["height"] < 40 or rect["width"] < 10:
                    continue

                machine = MACHINE_COLORS[color]

                start_minutes = x_to_minutes(rect["x0"])
                end_minutes = x_to_minutes(rect["x1"])

                if end_minutes <= start_minutes:
                    continue

                calculated_duration_minutes = end_minutes - start_minutes

                printed_duration = find_duration_near_rect(words, rect)

                if printed_duration:
                    duration_minutes = duration_to_minutes(printed_duration)
                    duration_source = "printed_duration"
                else:
                    duration_minutes = calculated_duration_minutes
                    duration_source = "bar_width"

                sessions.append({
                    "date": report_date,
                    "machine": machine,
                    "start_time": minutes_to_datetime(report_date, start_minutes),
                    "end_time": minutes_to_datetime(report_date, end_minutes),
                    "duration_minutes": duration_minutes,
                    "printed_duration": printed_duration,
                    "calculated_duration_minutes": calculated_duration_minutes,
                    "duration_source": duration_source,
                    "duration_difference_minutes": abs(duration_minutes - calculated_duration_minutes)
                })

    return sessions