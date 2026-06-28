import logging
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput

from src.calendar_client import GoogleCalendarClient
from src.utils.helpers import (
    TZ,
    format_date,
    format_dt,
    is_allowed,
    parse_date,
    parse_time,
)

logger = logging.getLogger(__name__)


class EventCreateModal(Modal):
    def __init__(self):
        super().__init__(title='Neues Event erstellen')

        now = datetime.now(TZ)
        heute = now.strftime('%d.%m.%Y')
        naechste_volle_stunde = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        default_start = naechste_volle_stunde.strftime('%H:%M')

        self.titel_input = TextInput(
            label='Titel',
            placeholder='z. B. Meeting',
            max_length=100,
        )
        self.datum_input = TextInput(
            label='Datum (TT.MM.JJJJ)',
            placeholder='z. B. 24.12.2025',
            default=heute,
        )
        self.startzeit_input = TextInput(
            label='Startzeit (HH:MM)',
            placeholder='z. B. 15:00',
            default=default_start,
        )
        self.endzeit_input = TextInput(
            label='Endzeit (HH:MM) – optional',
            placeholder='leer lassen = 1 Stunde',
            required=False,
        )
        self.add_item(self.titel_input)
        self.add_item(self.datum_input)
        self.add_item(self.startzeit_input)
        self.add_item(self.endzeit_input)

    async def on_submit(self, interaction: discord.Interaction):
        titel = self.titel_input.value.strip()
        datum = self.datum_input.value.strip()
        startzeit = self.startzeit_input.value.strip()
        endzeit = self.endzeit_input.value.strip() or None

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

        calendar: GoogleCalendarClient = interaction.client.calendar_client
        try:
            full_id = calendar.add_event(titel, start_dt, end_dt)
            short_id = full_id[:8]
        except Exception:
            logger.exception("Error creating event")
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


class EventEditModal(Modal):
    def __init__(self, event_id: str, current_title: str, current_start: datetime, current_end: datetime):
        self.event_id = event_id
        super().__init__(title='Event bearbeiten')
        self.titel_input = TextInput(
            label='Titel',
            default=current_title,
            max_length=100,
        )
        self.datum_input = TextInput(
            label='Datum (TT.MM.JJJJ)',
            default=current_start.astimezone(TZ).strftime('%d.%m.%Y'),
        )
        self.startzeit_input = TextInput(
            label='Startzeit (HH:MM)',
            default=current_start.astimezone(TZ).strftime('%H:%M'),
        )
        self.endzeit_input = TextInput(
            label='Endzeit (HH:MM)',
            default=current_end.astimezone(TZ).strftime('%H:%M'),
        )
        self.add_item(self.titel_input)
        self.add_item(self.datum_input)
        self.add_item(self.startzeit_input)
        self.add_item(self.endzeit_input)

    async def on_submit(self, interaction: discord.Interaction):
        titel = self.titel_input.value.strip()
        datum = self.datum_input.value.strip()
        startzeit = self.startzeit_input.value.strip()
        endzeit = self.endzeit_input.value.strip() or None

        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return

        await interaction.response.defer()

        try:
            event_date = parse_date(datum)
            start_time = parse_time(startzeit)
            new_start = TZ.localize(datetime.combine(event_date, start_time))

            if endzeit:
                end_time = parse_time(endzeit)
                new_end = TZ.localize(datetime.combine(event_date, end_time))
                if new_end <= new_start:
                    new_end = new_start + timedelta(hours=1)
            else:
                new_end = new_start + timedelta(hours=1)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        calendar: GoogleCalendarClient = interaction.client.calendar_client
        try:
            calendar.update_event(self.event_id, title=titel, start_dt=new_start, end_dt=new_end)
        except Exception:
            logger.exception("Error updating event")
            await interaction.followup.send('❌ Fehler beim Aktualisieren des Events.', ephemeral=True)
            return

        embed = discord.Embed(
            title='✅ Event aktualisiert',
            color=discord.Color.green(),
        )
        embed.add_field(name='Titel', value=titel, inline=False)
        embed.add_field(name='Start', value=format_dt(new_start), inline=True)
        embed.add_field(name='Ende', value=format_dt(new_end), inline=True)
        embed.add_field(name='Kurz-ID', value=f'`{self.event_id}`', inline=False)

        await interaction.followup.send(embed=embed)


class EventDeleteModal(Modal):
    def __init__(self, event_id: str, event_title: str):
        self.event_id = event_id
        self.event_title = event_title
        super().__init__(title='Event löschen?')
        self.confirm_input = TextInput(
            label=f'Bestätige: Tippe "{event_title}"',
            placeholder=event_title,
            max_length=100,
        )
        self.add_item(self.confirm_input)

    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm_input.value.strip() != self.event_title:
            await interaction.response.send_message(
                '❌ Der eingegebene Titel stimmt nicht überein. Löschen abgebrochen.',
                ephemeral=True,
            )
            return

        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return

        await interaction.response.defer()

        calendar: GoogleCalendarClient = interaction.client.calendar_client
        try:
            title = calendar.delete_event(self.event_id)
        except ValueError as e:
            await interaction.followup.send(f'❌ {e}', ephemeral=True)
            return
        except Exception:
            logger.exception("Error deleting event")
            await interaction.followup.send('❌ Fehler beim Löschen des Events.', ephemeral=True)
            return

        embed = discord.Embed(
            title='🗑️ Event gelöscht',
            description=f'**{title}** wurde gelöscht.',
            color=discord.Color.red(),
        )
        embed.add_field(name='Kurz-ID', value=f'`{self.event_id}`', inline=False)

        await interaction.followup.send(embed=embed)


class EventCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    event = app_commands.Group(name='event', description='Kalender-Events verwalten')

    @app_commands.command(name='hallo', description='Test – der Bot antwortet')
    async def hallo(self, interaction: discord.Interaction):
        await interaction.response.send_message('👋 Hallo!!!!!!')

    @event.command(name='add', description='Neues Event per Formular anlegen')
    async def event_add(self, interaction: discord.Interaction):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return
        await interaction.response.send_modal(EventCreateModal())

    @event.command(name='edit', description='Event per Formular bearbeiten')
    @app_commands.describe(event_id='8-stellige Kurz-ID des Events')
    async def event_edit(self, interaction: discord.Interaction, event_id: str):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return
        if len(event_id) != 8:
            await interaction.response.send_message('❌ Die Kurz-ID muss genau 8 Zeichen lang sein.', ephemeral=True)
            return
        calendar: GoogleCalendarClient = self.bot.calendar_client
        try:
            full_id = calendar._search_by_short_id(event_id)
            if not full_id:
                msg = f'❌ Kein Event mit Kurz-ID `{event_id}` gefunden.'
                await interaction.response.send_message(msg, ephemeral=True)
                return
            current = calendar.get_event(full_id)
        except Exception:
            logger.exception("Error fetching event")
            await interaction.response.send_message('❌ Fehler beim Abrufen des Events.', ephemeral=True)
            return
        current_title = current.get('summary', '')
        current_start = datetime.fromisoformat(current['start']['dateTime'])
        current_end = datetime.fromisoformat(current['end']['dateTime'])
        await interaction.response.send_modal(EventEditModal(event_id, current_title, current_start, current_end))

    @event.command(name='del', description='Event per Formular löschen')
    @app_commands.describe(event_id='8-stellige Kurz-ID des Events')
    async def event_del(self, interaction: discord.Interaction, event_id: str):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return
        if len(event_id) != 8:
            await interaction.response.send_message('❌ Die Kurz-ID muss genau 8 Zeichen lang sein.', ephemeral=True)
            return
        calendar: GoogleCalendarClient = self.bot.calendar_client
        try:
            full_id = calendar._search_by_short_id(event_id)
            if not full_id:
                msg = f'❌ Kein Event mit Kurz-ID `{event_id}` gefunden.'
                await interaction.response.send_message(msg, ephemeral=True)
                return
            current = calendar.get_event(full_id)
        except Exception:
            logger.exception("Error fetching event")
            await interaction.response.send_message('❌ Fehler beim Abrufen des Events.', ephemeral=True)
            return
        current_title = current.get('summary', '(kein Titel)')
        await interaction.response.send_modal(EventDeleteModal(event_id, current_title))

    @event.command(name='list', description='Bevorstehende Events auflisten')
    @app_commands.describe(bereich='Zeitraum der anzuzeigenden Events')
    @app_commands.choices(bereich=[
        app_commands.Choice(name='Heute', value='heute'),
        app_commands.Choice(name='Diese Woche', value='woche'),
        app_commands.Choice(name='Dieser Monat', value='monat'),
    ])
    async def event_list(self, interaction: discord.Interaction, bereich: str):
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
            logger.exception("Error fetching events from calendar")
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


async def setup(bot: commands.Bot):
    await bot.add_cog(EventCog(bot))
