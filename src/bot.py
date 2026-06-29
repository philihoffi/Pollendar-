import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.calendar_client import GoogleCalendarClient
from src.utils.helpers import set_allowed_users

load_dotenv()

logger = logging.getLogger('bot')

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', '')
CALENDAR_ID = os.getenv('CALENDAR_ID', '')
CREDENTIALS_PATH = os.getenv('CREDENTIALS_PATH', '/app/credentials/service_account.json')
ALLOWED_USER_IDS_STR = os.getenv('ALLOWED_USER_IDS', '')


def parse_allowed_users(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.split(','):
        part = part.strip()
        if part:
            try:
                ids.add(int(part))
            except ValueError:
                logger.warning(f"Ungültige User-ID ignoriert: {part}")
    return ids


intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)


@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        logger.info(f'{len(synced)} slash command(s) synchronized')
    except Exception as e:
        logger.error(f'Error syncing commands: {e}')


async def main():
    allowed_ids = parse_allowed_users(ALLOWED_USER_IDS_STR)
    set_allowed_users(allowed_ids)
    logger.info(f"Whitelist: {len(allowed_ids)} user(s)" if allowed_ids else "Whitelist: everyone allowed")

    bot.calendar_client = GoogleCalendarClient(CALENDAR_ID, CREDENTIALS_PATH)

    async with bot:
        await bot.load_extension('src.cogs.event_commands')
        await bot.load_extension('src.cogs.summary_commands')
        await bot.load_extension('src.cogs.poll_commands')
        await bot.start(DISCORD_TOKEN)
