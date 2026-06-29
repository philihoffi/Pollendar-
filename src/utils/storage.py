import json
import logging
from datetime import datetime
from pathlib import Path

from src.utils.helpers import TZ

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "config.json"
POLLS_FILE = DATA_DIR / "polls.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    _ensure_data_dir()
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config root must be a JSON object")
        return data
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.error("Failed to load config: %s", e)
        return {}


def save_config(data: dict):
    _ensure_data_dir()
    tmp = CONFIG_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(CONFIG_FILE)
    except OSError as e:
        logger.error("Failed to save config: %s", e)


def get_summary_channel_id() -> int | None:
    return load_config().get("summary_channel_id")


def set_summary_channel_id(channel_id: int | None):
    config = load_config()
    if channel_id is None:
        config.pop("summary_channel_id", None)
    else:
        config["summary_channel_id"] = channel_id
    save_config(config)


def get_all_polls() -> list[dict]:
    _ensure_data_dir()
    if not POLLS_FILE.exists():
        return []
    try:
        data = json.loads(POLLS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("polls root must be a JSON array")
        return data
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.error("Failed to load polls: %s", e)
        return []


def save_polls(polls: list[dict]):
    _ensure_data_dir()
    tmp = POLLS_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(polls, indent=2), encoding="utf-8")
        tmp.replace(POLLS_FILE)
    except OSError as e:
        logger.error("Failed to save polls: %s", e)


def add_poll_entry(
    message_id: int,
    channel_id: int,
    title: str,
    options: list[str],
    duration_hours: int,
    runoff: bool = False,
    runoff_parent: int | None = None,
):
    polls = get_all_polls()
    polls.append({
        "message_id": message_id,
        "channel_id": channel_id,
        "title": title,
        "options": options,
        "duration_hours": duration_hours,
        "finalized": False,
        "runoff": runoff,
        "runoff_parent": runoff_parent,
        "created_at": datetime.now(TZ).isoformat(),
    })
    save_polls(polls)


def mark_poll_finalized(message_id: int):
    polls = get_all_polls()
    for p in polls:
        if p["message_id"] == message_id:
            p["finalized"] = True
            break
    save_polls(polls)


def get_unfinalized_polls() -> list[dict]:
    return [p for p in get_all_polls() if not p["finalized"]]
