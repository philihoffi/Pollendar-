import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "config.json"


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
