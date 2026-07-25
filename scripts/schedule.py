import json
from datetime import date

VALID_FREQUENCIES = {
    "daily",
    "every_other_day",
    "twice_weekly",
    "weekly",
    "biweekly",
    "custom",
}

WEEKDAY_ABBREVS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DEFAULT_DAYS_BY_FREQUENCY = {
    "twice_weekly": ["wed", "sat"],
    "weekly": ["sat"],
    "biweekly": ["sat"],
}

DEFAULT_SCHEDULE = {
    "count": 10,
    "frequency": "daily",
    "days": [],
    "custom_dates": [],
    "last_delivered_date": None,
}


def merge_schedule_defaults(raw):
    schedule = dict(DEFAULT_SCHEDULE)
    if raw:
        schedule.update(raw)
    return schedule


def compute_plan(count):
    if count < 4:
        return {"mode": "open", "target_count": count}
    flexible = count - 4
    overgenerate = 0 if flexible == 0 else max(2 * flexible, 4)
    return {
        "mode": "quota",
        "required_categories": 4,
        "flexible_slots": flexible,
        "overgenerate": overgenerate,
    }


def is_delivery_day(schedule, today):
    frequency = schedule["frequency"]
    last = schedule.get("last_delivered_date")
    last_date = date.fromisoformat(last) if last else None

    if frequency == "daily":
        return True

    if frequency == "every_other_day":
        return last_date is None or (today - last_date).days >= 2

    if frequency in ("twice_weekly", "weekly"):
        today_abbrev = WEEKDAY_ABBREVS[today.weekday()]
        return today_abbrev in schedule.get("days", [])

    if frequency == "biweekly":
        today_abbrev = WEEKDAY_ABBREVS[today.weekday()]
        if today_abbrev not in schedule.get("days", []):
            return False
        return last_date is None or (today - last_date).days >= 14

    if frequency == "custom":
        custom_dates = schedule.get("custom_dates", [])
        today_iso = today.isoformat()
        future_or_today = [d for d in custom_dates if d >= today_iso]
        if not future_or_today:
            return True  # exhausted -- fall back to daily behavior
        return today_iso in custom_dates

    raise ValueError(f"unknown frequency: {frequency}")


if __name__ == "__main__":
    with open("data/schedule.json", encoding="utf-8") as f:
        raw = json.load(f)
    schedule = merge_schedule_defaults(raw)
    today = date.today()
    delivery_day = is_delivery_day(schedule, today)
    result = {"is_delivery_day": delivery_day, "schedule": schedule}
    if delivery_day:
        result["plan"] = compute_plan(schedule["count"])
    print(json.dumps(result))
