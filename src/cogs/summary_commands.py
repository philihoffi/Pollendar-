import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.utils.helpers import TZ, is_allowed
from src.utils.storage import get_summary_channel_id, set_summary_channel_id

logger = logging.getLogger(__name__)


class SummaryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_summary.start()

    config_cmd = app_commands.Group(name="config", description="Bot-Einstellungen")

    @config_cmd.command(name="summary", description="Channel für die tägliche Zusammenfassung festlegen")
    @app_commands.describe(channel="Ziel-Channel (leer lassen = deaktivieren)")
    async def config_summary(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ):
        if not is_allowed(interaction):
            await interaction.response.send_message("🚫 Kein Zugriff.", ephemeral=True)
            return

        current_id = get_summary_channel_id()

        if channel is None:
            if current_id is None:
                await interaction.response.send_message(
                    "📋 Kein Channel eingestellt. `/config summary #channel` zum Festlegen.",
                    ephemeral=True,
                )
                return

            ch = self.bot.get_channel(current_id)
            name = ch.mention if ch else f"Unbekannt ({current_id})"
            set_summary_channel_id(None)
            await interaction.response.send_message(
                f"🛑 Tägliche Zusammenfassung deaktiviert (war: {name}).",
                ephemeral=True,
            )
            return

        set_summary_channel_id(channel.id)
        await interaction.response.send_message(
            f"✅ Tägliche Zusammenfassung wird ab jetzt um 8:00 Uhr in {channel.mention} gepostet.",
            ephemeral=True,
        )

    @tasks.loop(hours=24)
    async def daily_summary(self):
        await self._send_summary()

    @daily_summary.before_loop
    async def before_daily_summary(self):
        await self.bot.wait_until_ready()
        now = datetime.now(TZ)
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        logger.info("Summary: next run at %s (in %.0fs)", target.strftime("%H:%M"), wait)
        await asyncio.sleep(wait)

    async def _send_summary(self):
        channel_id = get_summary_channel_id()
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.warning("Summary channel %s not found or not accessible", channel_id)
                return

        if not channel:
            logger.warning("Summary channel %s not found", channel_id)
            return

        today = datetime.now(TZ).date()
        try:
            events = self.bot.calendar_client.list_events(today, today)
        except Exception:
            logger.exception("Failed to fetch events for summary")
            return

        if not events:
            await channel.send("🌅 **Guten Morgen!** Heute stehen keine Termine an – entspannter Tag!")
            return

        embed = discord.Embed(
            title="🌅 Guten Morgen! Heute anstehende Termine:",
            color=discord.Color.blue(),
        )
        for ev in events:
            try:
                dt = datetime.fromisoformat(ev["start"])
                zeile = f"🕐 {dt.astimezone(TZ).strftime('%H:%M')} Uhr"
            except (ValueError, TypeError):
                zeile = f"🕐 {ev['start']}"
            embed.add_field(name=ev["title"], value=zeile, inline=False)

        embed.set_footer(text=f"Insgesamt {len(events)} Termine heute")
        await channel.send(embed=embed)

    def cog_unload(self):
        self.daily_summary.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(SummaryCog(bot))
