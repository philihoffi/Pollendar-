import logging
from datetime import date, datetime, time

import discord
import pytz

logger = logging.getLogger(__name__)

TZ = pytz.timezone('Europe/Berlin')

ALLOWED_USER_IDS: set[int] = set()


def set_allowed_users(user_ids: set[int]):
    global ALLOWED_USER_IDS
    ALLOWED_USER_IDS = user_ids


def is_allowed(interaction: discord.Interaction) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return interaction.user.id in ALLOWED_USER_IDS


def parse_date(date_str: str) -> date:
    try:
        return datetime.strptime(date_str, '%d.%m.%Y').date()
    except ValueError:
        raise ValueError(
            f"Ungültiges Datum: '{date_str}'. Bitte das Format TT.MM.JJJJ verwenden, z. B. 24.12.2024"
        )


def parse_time(time_str: str) -> time:
    try:
        return datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
        raise ValueError(
            f"Ungültige Uhrzeit: '{time_str}'. Bitte das Format HH:MM verwenden, z. B. 14:30"
        )


def format_dt(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime('%d.%m.%Y %H:%M')


def format_date(d: date) -> str:
    return d.strftime('%d.%m.%Y')
