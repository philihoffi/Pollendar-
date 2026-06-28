from datetime import date, time

import pytest

from src.utils.helpers import format_date, parse_date, parse_time


class TestParseDate:
    def test_valid_date(self):
        assert parse_date("24.12.2024") == date(2024, 12, 24)

    def test_invalid_date_format(self):
        with pytest.raises(ValueError, match="TT.MM.JJJJ"):
            parse_date("2024-12-24")

    def test_invalid_date_value(self):
        with pytest.raises(ValueError):
            parse_date("32.13.2024")


class TestParseTime:
    def test_valid_time(self):
        assert parse_time("14:30") == time(14, 30)

    def test_invalid_time_format(self):
        with pytest.raises(ValueError, match="HH:MM"):
            parse_time("2:30 PM")

    def test_invalid_time_value(self):
        with pytest.raises(ValueError):
            parse_time("25:00")


class TestFormatDate:
    def test_format_date(self):
        assert format_date(date(2024, 12, 24)) == "24.12.2024"
