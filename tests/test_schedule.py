from datetime import date

from scripts.schedule import (
    merge_schedule_defaults,
    compute_plan,
    is_delivery_day,
    DEFAULT_SCHEDULE,
)


def test_merge_schedule_defaults_fills_missing_file():
    result = merge_schedule_defaults(None)
    assert result == DEFAULT_SCHEDULE


def test_merge_schedule_defaults_overlays_partial_data():
    result = merge_schedule_defaults({"count": 5})
    assert result["count"] == 5
    assert result["frequency"] == "daily"


def test_compute_plan_quota_mode_at_default_ten():
    plan = compute_plan(10)
    assert plan == {
        "mode": "quota",
        "required_categories": 4,
        "flexible_slots": 6,
        "overgenerate": 12,
    }


def test_compute_plan_quota_mode_no_flexible_slots():
    plan = compute_plan(4)
    assert plan == {
        "mode": "quota",
        "required_categories": 4,
        "flexible_slots": 0,
        "overgenerate": 0,
    }


def test_compute_plan_quota_mode_small_flexible_uses_minimum_overgenerate():
    plan = compute_plan(5)
    assert plan["flexible_slots"] == 1
    assert plan["overgenerate"] == 4


def test_compute_plan_open_mode_below_four():
    plan = compute_plan(3)
    assert plan == {"mode": "open", "target_count": 3}


def test_is_delivery_day_daily_always_true():
    schedule = merge_schedule_defaults({"frequency": "daily"})
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True


def test_is_delivery_day_every_other_day_true_when_no_history():
    schedule = merge_schedule_defaults({"frequency": "every_other_day", "last_delivered_date": None})
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True


def test_is_delivery_day_every_other_day_false_next_day():
    schedule = merge_schedule_defaults({
        "frequency": "every_other_day",
        "last_delivered_date": "2026-07-25",
    })
    assert is_delivery_day(schedule, date(2026, 7, 26)) is False


def test_is_delivery_day_every_other_day_true_two_days_later():
    schedule = merge_schedule_defaults({
        "frequency": "every_other_day",
        "last_delivered_date": "2026-07-25",
    })
    assert is_delivery_day(schedule, date(2026, 7, 27)) is True


def test_is_delivery_day_weekly_matches_selected_day():
    # 2026-07-25 is a Saturday
    schedule = merge_schedule_defaults({"frequency": "weekly", "days": ["sat"]})
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True


def test_is_delivery_day_weekly_rejects_other_days():
    # 2026-07-26 is a Sunday
    schedule = merge_schedule_defaults({"frequency": "weekly", "days": ["sat"]})
    assert is_delivery_day(schedule, date(2026, 7, 26)) is False


def test_is_delivery_day_biweekly_requires_both_weekday_and_gap():
    schedule = merge_schedule_defaults({
        "frequency": "biweekly",
        "days": ["sat"],
        "last_delivered_date": "2026-07-25",
    })
    # 2026-08-01 is a Saturday, but only 7 days later -- too soon
    assert is_delivery_day(schedule, date(2026, 8, 1)) is False
    # 2026-08-08 is a Saturday, 14 days later -- eligible
    assert is_delivery_day(schedule, date(2026, 8, 8)) is True


def test_is_delivery_day_weekly_empty_days_falls_back_to_daily():
    # An owner who deselected every day chip must not silently stop delivery forever.
    schedule = merge_schedule_defaults({"frequency": "weekly", "days": []})
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True
    assert is_delivery_day(schedule, date(2026, 7, 26)) is True


def test_is_delivery_day_twice_weekly_empty_days_falls_back_to_daily():
    schedule = merge_schedule_defaults({"frequency": "twice_weekly", "days": []})
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True
    assert is_delivery_day(schedule, date(2026, 7, 26)) is True


def test_is_delivery_day_biweekly_empty_days_falls_back_to_daily():
    # Same failure mode as weekly/twice_weekly: an empty days list must never
    # permanently block delivery, even though biweekly normally also gates on
    # a 14-day gap since the last delivery.
    schedule = merge_schedule_defaults({
        "frequency": "biweekly",
        "days": [],
        "last_delivered_date": "2026-07-25",
    })
    assert is_delivery_day(schedule, date(2026, 7, 26)) is True


def test_is_delivery_day_custom_matches_listed_date():
    schedule = merge_schedule_defaults({
        "frequency": "custom",
        "custom_dates": ["2026-08-01", "2026-08-15"],
    })
    assert is_delivery_day(schedule, date(2026, 8, 1)) is True
    assert is_delivery_day(schedule, date(2026, 8, 2)) is False


def test_is_delivery_day_custom_falls_back_to_daily_when_exhausted():
    schedule = merge_schedule_defaults({
        "frequency": "custom",
        "custom_dates": ["2026-07-01"],  # entirely in the past relative to the check date below
    })
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True
