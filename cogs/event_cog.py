import re
import asyncio
import contextlib
import discord
from discord.ext import commands

from utils.form_template import FORM_TEMPLATE
from utils.views.ChannelSelect import ChannelSelectView
from utils.views.Confirm import ConfirmView
from utils.views.LocationSelect import LocationSelectView


class EventCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.input_channels = {}
        self.active_events = {}

    async def ask_input(self, channel, user, prompt, validate=None, error_msg=None, timeout=300, max_retries=3):
        for _ in range(max_retries):
            prompt_msg = await channel.send(prompt)

            try:
                msg = await self.bot.wait_for(
                    "message",
                    check=lambda m: m.author == user and m.channel == channel,
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                await prompt_msg.delete()
                await channel.send("Timeout. Setup cancelled.", delete_after=10)
                return None

            content = msg.content.strip()
            if validate:
                valid, result = validate(content)
                if valid:
                    await prompt_msg.delete()
                    await msg.delete()
                    return result
                else:
                    await msg.delete()
                    await channel.send(error_msg or "Invalid input, please try again.", delete_after=10)
                    await prompt_msg.delete()
                    continue
            else:
                await prompt_msg.delete()
                await msg.delete()
                return content

        await channel.send("Too many invalid attempts. Setup cancelled.", delete_after=10)
        return None

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setchannel(self, ctx, channel: discord.TextChannel):
        self.input_channels[ctx.guild.id] = channel.id
        await ctx.send(f"Input channel set to {channel.mention}", delete_after=10)

    @commands.command()
    async def event(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.input_channels:
            return await ctx.send("Input channel not set. Use ab!setchannel #channel first.", delete_after=10)

        input_channel = self.bot.get_channel(self.input_channels[guild_id])
        if input_channel is None:
            return await ctx.send("Configured input channel not found.", delete_after=10)

        ch_view = ChannelSelectView(ctx.guild.text_channels, ctx.guild)
        view_msg = await ctx.send("Select the channel to post the event announcement:", view=ch_view)
        await ch_view.wait()
        await view_msg.delete()
        if ch_view.selected_channel is None:
            return await ctx.send("No announcement channel selected. Setup cancelled.", delete_after=10)
        announcement_channel = ch_view.selected_channel

        # Clean bot messages
        try:
            async for m in input_channel.history(limit=50):
                if m.author == self.bot.user:
                    with contextlib.suppress(discord.Forbidden):
                        await m.delete()
        except discord.Forbidden:
            pass

        answers = {}

        def validate_mention(content):
            return (bool(re.fullmatch(r"<@!?\d+>", content)), content if re.fullmatch(r"<@!?\d+>", content) else None)

        def validate_mentions(content):
            parts = [p.strip() for p in content.split(",")]
            return (all(re.fullmatch(r"<@!?\d+>", p) for p in parts), content if all(re.fullmatch(r"<@!?\d+>", p) for p in parts) else None)

        def validate_nonempty(content):
            return (len(content) > 0, content)

        def validate_timestamp(content):
            match = re.search(r"<t:(\d+):\w>", content)
            return (bool(match), int(match.group(1)) if match else None)

        answers["host"] = await self.ask_input(input_channel, ctx.author, "Enter **Host** mention (@User):", validate_mention, "Please mention a valid single user.")
        if answers["host"] is None: return

        answers["cohosts"] = await self.ask_input(
            input_channel, ctx.author,
            "Enter **Co-Hosts** mention(s) (comma separated, or 'none'):",
            validate=lambda c: (True, c) if c.lower() == "none" else validate_mentions(c),
            error_msg="Please enter valid mentions separated by commas or 'none'."
        )
        if answers["cohosts"] is None: return
        if answers["cohosts"].lower() == "none": answers["cohosts"] = ""

        answers["event"] = await self.ask_input(input_channel, ctx.author, "Enter **Event**:", validate_nonempty, "Event name cannot be empty.")
        if answers["event"] is None: return

        ts = await self.ask_input(input_channel, ctx.author, "Enter **Time** (This accepts a timestamp only, generate a timestamp here: [**CLICK ME!**](https://discordtimestamp.com)):", validate_timestamp, "Invalid format. Use <t:...:...> timestamp.")
        if ts is None: return
        answers["time"] = f"<t:{ts}:R>"
        answers["__ts__"] = ts

        location_view = LocationSelectView(answers)
        loc_msg = await input_channel.send("Please select **Region**, **Province**, and **Settlement**:", view=location_view)
        await location_view.wait()
        await loc_msg.delete()

        if not all(k in answers for k in ("region", "province", "settlement")):
            return await input_channel.send("Location selection incomplete. Setup cancelled.", delete_after=10)

        for field in ["site", "in-Game Area", "link"]:
            val = await self.ask_input(input_channel, ctx.author, f"Enter **{field.capitalize()}**:", validate=validate_nonempty, error_msg=f"{field.capitalize()} cannot be empty.")
            if val is None: return
            answers[field] = val
        
        def validate_min_attendees(content):
            return (content.isdigit() and int(content) >= 0, int(content) if content.isdigit() and int(content) >= 0 else None)

        min_attendees = await self.ask_input(input_channel, ctx.author, "Enter **Minimum Attendees** (0 or more):", validate_min_attendees, "Enter a valid non-negative number.")
        if min_attendees is None:
            return
        answers["__min_attendees__"] = min_attendees


        filled = FORM_TEMPLATE.format(**answers)
        form_msg = await input_channel.send(f"Here’s your filled form:\n{filled}")

        conf_view = ConfirmView()
        confirm_msg = await input_channel.send("Confirm?", view=conf_view)
        await conf_view.wait()
        await confirm_msg.delete()
        await form_msg.delete()

        if not conf_view.value:
            return await input_channel.send("Setup cancelled.", delete_after=10)

        pre_msg = await announcement_channel.send(f"<@&1362122887003115792>\n\nEvent {answers['time']}\nHost: {answers['host']}")
        for emoji in ["✅", "❌", "❓"]:
            await pre_msg.add_reaction(emoji)

        delay = answers["__ts__"] - int(discord.utils.utcnow().timestamp())
        countdown_msg = await input_channel.send(f"⏳ Event starts <t:{answers['__ts__']}:R>" if delay > 0 else "⏰ Event is due now!")

        if delay > 0:
            await asyncio.sleep(delay)

        try:
            pre_msg = await announcement_channel.fetch_message(pre_msg.id)
            reaction = discord.utils.get(pre_msg.reactions, emoji="✅")
            users = [u async for u in reaction.users() if not u.bot] if reaction else []
            attendees = [u.mention for u in users]

            if len(attendees) < answers["__min_attendees__"]:
                await announcement_channel.send("❌ Minimum attendees not met, event cancelled.")
                await pre_msg.delete()
                await countdown_msg.delete()
                return
        except Exception:
            await announcement_channel.send("❌ Error fetching attendee reactions. Event cancelled.")
            await pre_msg.delete()
            await countdown_msg.delete()
            return


        await pre_msg.delete()

        answers["time"] = "**NOW :red_circle:**"
        final_form = FORM_TEMPLATE.format(**answers)
        announcement = await announcement_channel.send(f"**EVENT ANNOUNCEMENT:** Event has started! :tada:\n\n{final_form}")
        attendee_msg = await announcement_channel.send(
            "**Users that reacted: Attending**\n" + "\n".join(f"- {u}" for u in attendees) if attendees else "- *(None)*"
        )

        self.active_events[guild_id] = {
            "input_channel_id": input_channel.id,
            "announcement_channel_id": announcement_channel.id,
            "announcement_message_id": announcement.id,
            "attendee_message_id": attendee_msg.id,
            "countdown_message_id": countdown_msg.id,
        }

        await asyncio.sleep(30)
        await countdown_msg.delete()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def eventend(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.active_events:
            await ctx.send("There is no active event to end.", delete_after=10)
            with contextlib.suppress(discord.Forbidden, discord.NotFound):
                await ctx.message.delete()
            return

        data = self.active_events[guild_id]
        input_channel = self.bot.get_channel(data["input_channel_id"])
        announcement_channel = self.bot.get_channel(data["announcement_channel_id"])

        try:
            async for m in input_channel.history(limit=100):
                if m.author == self.bot.user:
                    await m.delete()

            for msg_id in [
                data.get("announcement_message_id"),
                data.get("attendee_message_id"),
                data.get("countdown_message_id"),
            ]:
                if msg_id:
                    with contextlib.suppress(Exception):
                        msg = await announcement_channel.fetch_message(msg_id)
                        await msg.delete()

            await ctx.send(
                f"Event ended and cleaned in {input_channel.mention} / {announcement_channel.mention}.",
                delete_after=10
            )
            del self.active_events[guild_id]

        except Exception as e:
            await ctx.send(f"Error ending event: {e}", delete_after=10)

        # Delete the user's command message
        with contextlib.suppress(discord.Forbidden, discord.NotFound):
            await ctx.message.delete()

