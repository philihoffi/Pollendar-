import logging
import random
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput

from src.calendar_client import GoogleCalendarClient
from src.utils.helpers import TZ, is_allowed, parse_date, parse_time
from src.utils.storage import (
    add_poll_entry,
    get_unfinalized_polls,
    mark_poll_finalized,
)

logger = logging.getLogger(__name__)


class EventPollModal(Modal):
    def __init__(self):
        super().__init__(title="Termin-Umfrage erstellen")

        self.titel_input = TextInput(
            label="Event-Titel",
            placeholder="z. B. Team-Meeting",
            max_length=100,
        )
        self.optionen_input = TextInput(
            label="Termin-Optionen (eine pro Zeile)",
            placeholder="TT.MM.JJJJ HH:MM",
            style=discord.TextStyle.paragraph,
            max_length=500,
        )
        self.dauer_input = TextInput(
            label="Umfrage-Dauer (Stunden)",
            placeholder="z. B. 24",
            default="24",
            max_length=3,
        )
        self.add_item(self.titel_input)
        self.add_item(self.optionen_input)
        self.add_item(self.dauer_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return

        titel = self.titel_input.value.strip()
        roh_optionen = self.optionen_input.value.strip().splitlines()
        dauer_raw = self.dauer_input.value.strip()

        if not titel:
            await interaction.response.send_message('❌ Bitte einen Titel eingeben.', ephemeral=True)
            return

        optionen = [z.strip() for z in roh_optionen if z.strip()]
        if len(optionen) < 2:
            await interaction.response.send_message('❌ Bitte mindestens 2 Termin-Optionen angeben.', ephemeral=True)
            return
        if len(optionen) > 10:
            await interaction.response.send_message('❌ Maximal 10 Termin-Optionen erlaubt.', ephemeral=True)
            return

        try:
            dauer = int(dauer_raw)
            if dauer < 1 or dauer > 168:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                '❌ Dauer muss eine ganze Zahl zwischen 1 und 168 sein.', ephemeral=True
            )
            return

        geparste_optionen = []
        for opt in optionen:
            try:
                date_str, time_str = opt.split(maxsplit=1)
                d = parse_date(date_str)
                t = parse_time(time_str)
                dt = TZ.localize(datetime.combine(d, t))
                if dt <= datetime.now(TZ):
                    await interaction.response.send_message(
                        f'❌ "{opt}" liegt in der Vergangenheit.', ephemeral=True
                    )
                    return
                geparste_optionen.append(dt)
            except ValueError:
                await interaction.response.send_message(
                    f'❌ Ungültiges Format: "{opt}". Erwartet: TT.MM.JJJJ HH:MM', ephemeral=True
                )
                return

        labels = [dt.strftime('%d.%m.%Y %H:%M') for dt in geparste_optionen]

        await interaction.response.defer(ephemeral=True)

        poll = discord.Poll(
            question=f'Wann soll "{titel}" stattfinden?',
            duration=timedelta(hours=dauer),
        )
        for lbl in labels:
            poll.add_answer(text=lbl)

        try:
            msg = await interaction.channel.send(poll=poll)
        except Exception:
            logger.exception("Fehler beim Senden des Polls")
            await interaction.followup.send('❌ Fehler beim Erstellen der Umfrage.', ephemeral=True)
            return

        add_poll_entry(
            message_id=msg.id,
            channel_id=interaction.channel_id,
            title=titel,
            options=labels,
            duration_hours=dauer,
        )

        embed = discord.Embed(
            title="🗳️ Umfrage erstellt",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Event", value=titel, inline=False)
        embed.add_field(name="Optionen", value="\n".join(labels), inline=False)
        embed.add_field(name="Dauer", value=f"{dauer} Std.", inline=True)
        embed.add_field(name="Nachricht", value=f"[Link]({msg.jump_url})", inline=True)
        embed.set_footer(text=f"Von {interaction.user.display_name}")

        await interaction.followup.send(embed=embed, ephemeral=True)


class PollCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_ended_polls.start()

    event_poll = app_commands.Group(name="event", description="Termin-Umfragen verwalten")

    @event_poll.command(name="create", description="Neue Termin-Umfrage erstellen")
    async def poll_create(self, interaction: discord.Interaction):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return
        await interaction.response.send_modal(EventPollModal())

    @event_poll.command(name="finalize", description="Umfrage vorzeitig beenden und auswerten")
    @app_commands.describe(message_id="ID der Umfrage-Nachricht")
    async def poll_finalize(self, interaction: discord.Interaction, message_id: str):
        if not is_allowed(interaction):
            await interaction.response.send_message('🚫 Kein Zugriff.', ephemeral=True)
            return

        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message('❌ Ungültige Nachrichten-ID.', ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            msg = await interaction.channel.fetch_message(msg_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await interaction.followup.send('❌ Nachricht nicht gefunden.', ephemeral=True)
            return

        p = msg.poll
        if not p:
            await interaction.followup.send('❌ Diese Nachricht enthält keine Umfrage.', ephemeral=True)
            return

        if not p.is_finalized():
            try:
                await p.end()
            except Exception:
                logger.exception("Fehler beim vorzeitigen Beenden")
                await interaction.followup.send('❌ Konnte Umfrage nicht beenden.', ephemeral=True)
                return

        await self._do_finalize_by_msg(interaction.channel, msg, interaction.user)
        await interaction.followup.send('✅ Umfrage ausgewertet.', ephemeral=True)

    @tasks.loop(minutes=5)
    async def check_ended_polls(self):
        polls = get_unfinalized_polls()
        now = datetime.now(TZ)
        for p in polls:
            created = datetime.fromisoformat(p["created_at"])
            expiry = created + timedelta(hours=p["duration_hours"])
            if now >= expiry:
                channel = self.bot.get_channel(p["channel_id"])
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(p["channel_id"])
                    except Exception:
                        logger.warning("Channel %s not found for poll %s", p["channel_id"], p["message_id"])
                        mark_poll_finalized(p["message_id"])
                        continue

                try:
                    msg = await channel.fetch_message(p["message_id"])
                except Exception:
                    logger.warning("Message %s not found for poll", p["message_id"])
                    mark_poll_finalized(p["message_id"])
                    continue

                await self._do_finalize_by_msg(channel, msg)

    @check_ended_polls.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def _do_finalize_by_msg(
        self,
        channel: discord.TextChannel,
        msg: discord.Message,
        user: discord.User | None = None,
    ):
        p = msg.poll
        if not p or not p.is_finalized():
            return

        poll_data = None
        for pd in get_unfinalized_polls():
            if pd["message_id"] == msg.id:
                poll_data = pd
                break

        if not poll_data:
            return

        all_answers = p.answers
        if not all_answers:
            mark_poll_finalized(msg.id)
            return

        max_votes = max(a.vote_count for a in all_answers)

        if max_votes == 0:
            embed = discord.Embed(
                title="📅 Umfrage beendet",
                color=discord.Color.orange(),
            )
            embed.add_field(name="Event", value=poll_data["title"], inline=False)
            embed.add_field(name="Ergebnis", value="Keine Stimmen abgegeben – kein Event erstellt.", inline=False)
            await channel.send(embed=embed)
            mark_poll_finalized(msg.id)
            return

        winners = [a for a in all_answers if a.vote_count == max_votes]

        if len(winners) == 1:
            await self._create_event(channel, poll_data, winners[0])
            mark_poll_finalized(msg.id)
            return

        if poll_data.get("runoff"):
            choice = random.choice(winners)
            embed = discord.Embed(
                title="🎲 Stichwahl entschieden",
                color=discord.Color.green(),
            )
            embed.add_field(name="Event", value=poll_data["title"], inline=False)
            embed.add_field(
                name="Ergebnis",
                value="Stichwahl erneut unentschieden – der Würfel entscheidet!",
                inline=False,
            )
            await channel.send(embed=embed)
            await self._create_event(channel, poll_data, choice)
            mark_poll_finalized(msg.id)
            return

        winner_labels = [w.text for w in winners]
        runoff_duration = min(2, poll_data["duration_hours"])

        embed = discord.Embed(
            title="📅 Umfrage – Stichwahl gestartet 🗳️",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Event", value=poll_data["title"], inline=False)
        stimmen_text = "\n".join(f"• {w.text} ({w.vote_count} Stimmen)" for w in winners)
        embed.add_field(name="Gleichstand zwischen", value=stimmen_text, inline=False)
        embed.add_field(name="Stichwahl", value=f"Neue Abstimmung läuft ({runoff_duration} Std.)", inline=True)
        await channel.send(embed=embed)

        runoff_poll = discord.Poll(
            question=f'Stichwahl: Wann soll "{poll_data["title"]}" stattfinden?',
            duration=timedelta(hours=runoff_duration),
        )
        for lbl in winner_labels:
            runoff_poll.add_answer(text=lbl)

        try:
            runoff_msg = await channel.send(poll=runoff_poll)
        except Exception:
            logger.exception("Fehler beim Erstellen der Stichwahl")
            return

        add_poll_entry(
            message_id=runoff_msg.id,
            channel_id=channel.id,
            title=poll_data["title"],
            options=winner_labels,
            duration_hours=runoff_duration,
            runoff=True,
            runoff_parent=msg.id,
        )
        mark_poll_finalized(msg.id)

    async def _create_event(
        self,
        channel: discord.TextChannel,
        poll_data: dict,
        winner: discord.PollAnswer,
    ):
        winner_text = winner.text
        try:
            date_str, time_str = winner_text.split(maxsplit=1)
            event_date = parse_date(date_str)
            event_time = parse_time(time_str)
            start_dt = TZ.localize(datetime.combine(event_date, event_time))
        except ValueError:
            logger.exception("Konnte Gewinner nicht parsen: %s", winner_text)
            await channel.send(f'❌ Konnte Gewinner "{winner_text}" nicht als Datum parsen.')
            return

        calendar: GoogleCalendarClient = self.bot.calendar_client
        try:
            full_id = calendar.add_event(poll_data["title"], start_dt)
            short_id = full_id[:8]
        except Exception:
            logger.exception("Fehler beim Erstellen des Calendar-Events")
            embed = discord.Embed(
                title="❌ Umfrage beendet – Fehler",
                color=discord.Color.red(),
            )
            embed.add_field(name="Event", value=poll_data["title"], inline=False)
            embed.add_field(name="Gewinner", value=winner_text, inline=True)
            embed.add_field(name="Status", value="Google Calendar Fehler – Event wurde nicht erstellt.", inline=False)
            await channel.send(embed=embed)
            return

        embed = discord.Embed(
            title="📅 Umfrage beendet – Termin steht!",
            color=discord.Color.green(),
        )
        embed.add_field(name="Event", value=poll_data["title"], inline=False)
        votes_text = f"{winner_text} ({winner.vote_count} Stimmen)"
        embed.add_field(name="Gewinner", value=votes_text, inline=True)
        embed.add_field(name="Kurz-ID", value=f"`{short_id}`", inline=True)
        await channel.send(embed=embed)

    def cog_unload(self):
        self.check_ended_polls.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(PollCog(bot))
