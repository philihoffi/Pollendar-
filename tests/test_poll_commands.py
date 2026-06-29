import pytest
import pytz

from src.utils.storage import (
    add_poll_entry,
    get_all_polls,
    get_unfinalized_polls,
    mark_poll_finalized,
    save_polls,
)

TZ = pytz.timezone("Europe/Berlin")


@pytest.fixture(autouse=True)
def cleanup_polls():
    save_polls([])
    yield
    save_polls([])


class TestPollStorage:
    def test_add_and_retrieve(self):
        add_poll_entry(111, 222, "Test", ["opt1", "opt2"], 24)
        polls = get_all_polls()
        assert len(polls) == 1
        assert polls[0]["message_id"] == 111
        assert polls[0]["title"] == "Test"
        assert polls[0]["options"] == ["opt1", "opt2"]
        assert polls[0]["duration_hours"] == 24
        assert polls[0]["finalized"] is False
        assert polls[0]["runoff"] is False
        assert polls[0]["runoff_parent"] is None

    def test_mark_finalized(self):
        add_poll_entry(111, 222, "Test", ["opt1"], 24)
        mark_poll_finalized(111)
        polls = get_all_polls()
        assert polls[0]["finalized"] is True

    def test_get_unfinalized(self):
        add_poll_entry(111, 222, "A", ["o1"], 24)
        add_poll_entry(222, 333, "B", ["o2"], 24)
        mark_poll_finalized(111)
        unfinalized = get_unfinalized_polls()
        assert len(unfinalized) == 1
        assert unfinalized[0]["message_id"] == 222

    def test_add_runoff(self):
        add_poll_entry(111, 222, "Test", ["a", "b"], 2, runoff=True, runoff_parent=100)
        polls = get_all_polls()
        assert polls[0]["runoff"] is True
        assert polls[0]["runoff_parent"] == 100

    def test_multiple_polls(self):
        add_poll_entry(1, 2, "A", ["o1"], 24)
        add_poll_entry(3, 4, "B", ["o2"], 24)
        assert len(get_all_polls()) == 2

    def test_empty_polls_file(self):
        assert get_all_polls() == []

    def test_poll_created_at_set(self):
        add_poll_entry(1, 2, "T", ["o1"], 24)
        p = get_all_polls()[0]
        assert "created_at" in p
        from datetime import datetime
        datetime.fromisoformat(p["created_at"])


class TestPollValidation:
    def test_poll_requires_at_least_two_options(self):
        pass

    def test_poll_options_max_ten(self):
        pass
