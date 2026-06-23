import logging
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from src.calendar_client import GoogleCalendarClient
from src.utils.helpers import (
    parse_date, parse_time, format_dt, format_date, is_allowed, TZ,
)

logger = logging.getLogger(__name__)


class EventCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    event = app_commands.Group(name='event', description='Kalender-Events verwalten')

    @app_commands.command(name='hallo', description='Test – der Bot antwortet')
    async def hallo(self, interaction: discord.Interaction):
        await interaction.response.send_message('👋 Hallo!!!!!!')

    @event.command(name='add', description='Neues Event im Kalender anlegen')
    @app_commands.describe(
        titel='Titel des Events',
        datum='Datum (TT.MM.JJJJ, z. B. 24.12.2024)',
        startzeit='Startzeit (HH:MM, z. B. 14:00)',
        endzeit='Endzeit (HH:MM, optional – Standard: 1 Stunde)',
    )
    async def event_add(
        self,
        interaction: discord.Interaction,
        titel: str,
        datum: str,
        startzeit: str,
        endzeit: str = None,
    ):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return

        await interaction.response.defer()

        try:
            event_date = parse_date(datum)
            start_time = parse_time(startzeit)

            start_dt = TZ.localize(datetime.combine(event_date, start_time))

            if endzeit:
                end_time = parse_time(endzeit)
                end_dt = TZ.localize(datetime.combine(event_date, end_time))
                if end_dt <= start_dt:
                    end_dt = start_dt + timedelta(hours=1)
            else:
                end_dt = start_dt + timedelta(hours=1)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        calendar: GoogleCalendarClient = self.bot.calendar_client
        try:
            full_id = calendar.add_event(titel, start_dt, end_dt)
            short_id = full_id[:8]
        except Exception:
            logger.exception("Fehler beim Erstellen des Events")
            await interaction.followup.send('❌ Fehler beim Erstellen des Events in Google Calendar.', ephemeral=True)
            return

        embed = discord.Embed(
            title='✅ Event erstellt',
            color=discord.Color.green(),
        )
        embed.add_field(name='Titel', value=titel, inline=False)
        embed.add_field(name='Start', value=format_dt(start_dt), inline=True)
        embed.add_field(name='Ende', value=format_dt(end_dt), inline=True)
        embed.add_field(name='Kurz-ID', value=f'`{short_id}`', inline=False)
        embed.set_footer(text=f'Erstellt von {interaction.user.display_name}')

        await interaction.followup.send(embed=embed)

    @event.command(name='list', description='Bevorstehende Events auflisten')
    @app_commands.describe(bereich='Zeitraum der anzuzeigenden Events')
    @app_commands.choices(bereich=[
        app_commands.Choice(name='Heute', value='heute'),
        app_commands.Choice(name='Diese Woche', value='woche'),
        app_commands.Choice(name='Dieser Monat', value='monat'),
    ])
    async def event_list(
        self,
        interaction: discord.Interaction,
        bereich: str,
    ):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return

        await interaction.response.defer()

        today = datetime.now(TZ).date()
        if bereich == 'heute':
            start_date, end_date = today, today
        elif bereich == 'woche':
            start_date, end_date = today, today + timedelta(days=7)
        else:
            start_date, end_date = today, today + timedelta(days=30)

        calendar: GoogleCalendarClient = self.bot.calendar_client
        try:
            events = calendar.list_events(start_date, end_date)
        except Exception:
            logger.exception("Fehler beim Abrufen der Events")
            await interaction.followup.send('❌ Fehler beim Abrufen der Events aus Google Calendar.', ephemeral=True)
            return

        if not events:
            await interaction.followup.send(
                f'📭 Keine Events im Zeitraum {format_date(start_date)} – {format_date(end_date)}.'
            )
            return

        embed = discord.Embed(
            title=f'📅 Events {format_date(start_date)} – {format_date(end_date)}',
            color=discord.Color.blue(),
        )

        for ev in events:
            try:
                dt = datetime.fromisoformat(ev['start'])
                zeile = f"🕐 {format_dt(dt)} — ID: `{ev['id']}`"
            except (ValueError, TypeError):
                zeile = f"🕐 {ev['start']} — ID: `{ev['id']}`"
            embed.add_field(name=ev['title'], value=zeile, inline=False)

        await interaction.followup.send(embed=embed)

    @event.command(name='edit', description='Bestehendes Event bearbeiten')
    @app_commands.describe(
        event_id='8-stellige Kurz-ID des Events',
        titel='Neuer Titel (optional)',
        datum='Neues Datum TT.MM.JJJJ (optional)',
        startzeit='Neue Startzeit HH:MM (optional)',
        endzeit='Neue Endzeit HH:MM (optional)',
    )
    async def event_edit(
        self,
        interaction: discord.Interaction,
        event_id: str,
        titel: str = None,
        datum: str = None,
        startzeit: str = None,
        endzeit: str = None,
    ):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return

        await interaction.response.defer()

        if len(event_id) != 8:
            await interaction.followup.send('❌ Die Kurz-ID muss genau 8 Zeichen lang sein.', ephemeral=True)
            return

        calendar: GoogleCalendarClient = self.bot.calendar_client
        try:
            full_id = calendar._search_by_short_id(event_id)
            if not full_id:
                await interaction.followup.send(f'❌ Kein Event mit Kurz-ID `{event_id}` gefunden.', ephemeral=True)
                return

            current = calendar.get_event(full_id)
        except Exception:
            logger.exception("Fehler beim Abrufen des Events")
            await interaction.followup.send('❌ Fehler beim Abrufen des Events.', ephemeral=True)
            return

        try:
            start_str = current['start']['dateTime']
            end_str = current['end']['dateTime']
            current_start = datetime.fromisoformat(start_str)
            current_end = datetime.fromisoformat(end_str)

            new_title = titel if titel is not None else current.get('summary')
            new_start = current_start
            new_end = current_end

            if datum:
                event_date = parse_date(datum)
                new_start = TZ.localize(datetime.combine(event_date, current_start.astimezone(TZ).time()))
                new_end = TZ.localize(datetime.combine(event_date, current_end.astimezone(TZ).time()))

            if startzeit:
                st = parse_time(startzeit)
                new_start = TZ.localize(datetime.combine(new_start.astimezone(TZ).date(), st))

            if endzeit:
                et = parse_time(endzeit)
                new_end = TZ.localize(datetime.combine(new_end.astimezone(TZ).date(), et))

            if new_end <= new_start:
                new_end = new_start + timedelta(hours=1)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        try:
            calendar.update_event(event_id, title=new_title, start_dt=new_start, end_dt=new_end)
        except Exception:
            logger.exception("Fehler beim Aktualisieren des Events")
            await interaction.followup.send('❌ Fehler beim Aktualisieren des Events.', ephemeral=True)
            return

        embed = discord.Embed(
            title='✅ Event aktualisiert',
            color=discord.Color.green(),
        )
        embed.add_field(name='Titel', value=new_title, inline=False)
        embed.add_field(name='Start', value=format_dt(new_start), inline=True)
        embed.add_field(name='Ende', value=format_dt(new_end), inline=True)
        embed.add_field(name='Kurz-ID', value=f'`{event_id}`', inline=False)

        await interaction.followup.send(embed=embed)

    @event.command(name='del', description='Event löschen')
    @app_commands.describe(event_id='8-stellige Kurz-ID des Events')
    async def event_del(
        self,
        interaction: discord.Interaction,
        event_id: str,
    ):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return

        await interaction.response.defer()

        if len(event_id) != 8:
            await interaction.followup.send('❌ Die Kurz-ID muss genau 8 Zeichen lang sein.', ephemeral=True)
            return

        calendar: GoogleCalendarClient = self.bot.calendar_client
        try:
            title = calendar.delete_event(event_id)
        except ValueError as e:
            await interaction.followup.send(f'❌ {e}', ephemeral=True)
            return
        except Exception:
            logger.exception("Fehler beim Löschen des Events")
            await interaction.followup.send('❌ Fehler beim Löschen des Events.', ephemeral=True)
            return

        embed = discord.Embed(
            title='🗑️ Event gelöscht',
            description=f'**{title}** wurde gelöscht.',
            color=discord.Color.red(),
        )
        embed.add_field(name='Kurz-ID', value=f'`{event_id}`', inline=False)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventCog(bot))