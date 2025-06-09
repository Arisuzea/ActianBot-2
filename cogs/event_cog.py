import re
import asyncio
import contextlib
import discord
import logging
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
            prompt_msg = await channel.send(prompt)  # Save bot message

            try:
                msg = await self.bot.wait_for(
                    "message",
                    check=lambda m: m.author == user and m.channel == channel,
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                await prompt_msg.delete()
                await channel.send("Timeout. Setup cancelled.")
                return None

            content = msg.content.strip()
            if validate:
                valid, result = validate(content)
                if valid:
                    await prompt_msg.delete()
                    await msg.delete()
                    return result
                else:
                    await channel.send(error_msg or "Invalid input, please try again.")
                    await msg.delete()
                    continue
            else:
                await prompt_msg.delete()
                await msg.delete()
                return content

        await channel.send("Too many invalid attempts. Setup cancelled.")
        return None


    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setchannel(self, ctx, channel: discord.TextChannel):
        self.input_channels[ctx.guild.id] = channel.id
        await ctx.send(f"Input channel set to {channel.mention}")

    @commands.command()
    async def event(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.input_channels:
            return await ctx.send("Input channel not set. Use ab!setchannel #channel first.")

        input_channel = self.bot.get_channel(self.input_channels[guild_id])
        if input_channel is None:
            return await ctx.send("Configured input channel not found.")

        # Select announcement channel
        ch_view = ChannelSelectView(ctx.guild.text_channels, ctx.guild)
        await ctx.send("Select the channel to post the event announcement:", view=ch_view)
        await ch_view.wait()
        if ch_view.selected_channel is None:
            return await ctx.send("No announcement channel selected. Setup cancelled.")
        announcement_channel = ch_view.selected_channel

        # Clear bot messages from input channel (optional cleanup)
        try:
            async for m in input_channel.history(limit=50):
                if m.author == self.bot.user:
                    with contextlib.suppress(discord.Forbidden):
                        await m.delete()
        except discord.Forbidden:
            pass

        answers = {}

        # Validation helpers
        def validate_mention(content):
            # Accept a single mention like <@1234567890>
            if re.fullmatch(r"<@!?\d+>", content):
                return True, content
            return False, None

        def validate_mentions(content):
            # Accept comma-separated mentions
            parts = [p.strip() for p in content.split(",")]
            if all(re.fullmatch(r"<@!?\d+>", p) for p in parts):
                return True, content
            return False, None

        def validate_nonempty(content):
            return (len(content) > 0, content)

        def validate_timestamp(content):
            match = re.search(r"<t:(\d+):\w>", content)
            if match:
                ts = int(match.group(1))
                return True, ts
            return False, None

        # Ask inputs one by one with validation
        answers["host"] = await self.ask_input(
            input_channel,
            ctx.author,
            "Enter **Host** mention (@User):",
            validate=validate_mention,
            error_msg="Please mention a valid single user.",
        )
        if answers["host"] is None:
            return

        answers["cohosts"] = await self.ask_input(
            input_channel,
            ctx.author,
            "Enter **Co-Hosts** mention(s) (comma separated, or 'none'):",
            validate=lambda c: (True, c) if c.lower() == "none" else validate_mentions(c),
            error_msg="Please enter valid mentions separated by commas or 'none'.",
        )
        if answers["cohosts"] is None:
            return
        if answers["cohosts"].lower() == "none":
            answers["cohosts"] = ""

        answers["event"] = await self.ask_input(
            input_channel,
            ctx.author,
            "Enter **Event**:",
            validate=validate_nonempty,
            error_msg="Event name cannot be empty.",
        )
        if answers["event"] is None:
            return

        ts = await self.ask_input(
            input_channel,
            ctx.author,
            "Enter **Time** (use timestamp format, e.g. <t:1234567890:R>):",
            validate=validate_timestamp,
            error_msg="Invalid format. Use <t:...:...> timestamp.",
        )
        if ts is None:
            return
        answers["time"] = f"<t:{ts}:R>"
        answers["__ts__"] = ts

        # === INTEGRATED LocationSelectView for region/province/settlement ===
        location_view = LocationSelectView(answers)
        await input_channel.send("Please select **Region**, **Province**, and **Settlement**:", view=location_view)
        await location_view.wait()

        if not all(k in answers for k in ("region", "province", "settlement")):
            return await input_channel.send("Location selection incomplete. Setup cancelled.")

        # Validate selection completed
        if not all(k in answers for k in ("region", "province", "settlement")):
            return await input_channel.send("Location selection incomplete. Setup cancelled.")

        # Remaining inputs with basic non-empty validation
        for field in ["site", "area", "link"]:
            val = await self.ask_input(
                input_channel,
                ctx.author,
                f"Enter **{field.capitalize()}**:",
                validate=validate_nonempty,
                error_msg=f"{field.capitalize()} cannot be empty.",
            )
            if val is None:
                return
            answers[field] = val

        # Show filled form
        filled = FORM_TEMPLATE.format(**answers)
        await input_channel.send(f"Here’s your filled form:\n{filled}")

        # Confirmation
        conf_view = ConfirmView()
        await input_channel.send("Confirm?", view=conf_view)
        await conf_view.wait()
        if not conf_view.value:
            return await input_channel.send("Setup cancelled.")

        # Post initial announcement with reactions
        pre_msg = await announcement_channel.send(
            f"@RP Event Ping\n\nEvent {answers['time']}\nHost: {answers['host']}"
        )
        for emoji in ["✅", "❌", "❓"]:
            await pre_msg.add_reaction(emoji)

        delay = answers["__ts__"] - int(discord.utils.utcnow().timestamp())
        countdown_msg = await input_channel.send(
            f"⏳ Event starts <t:{answers['__ts__']}:R>" if delay > 0 else "⏰ Event is due now!"
        )
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            pre_msg = await announcement_channel.fetch_message(pre_msg.id)
            reaction = discord.utils.get(pre_msg.reactions, emoji="✅")
            users = [user async for user in reaction.users() if not user.bot] if reaction else []
            attendees = [u.mention for u in users]
        except Exception:
            attendees = []

        await pre_msg.delete()

        answers["time"] = "**NOW :red_circle:**"
        final_form = FORM_TEMPLATE.format(**answers)
        announcement = await announcement_channel.send(
            f"**EVENT ANNOUNCEMENT:** Event has started! :tada:\n\n{final_form}"
        )

        attendee_list = (
            "**Users that reacted: Attending**\n" + "\n".join(f"- {u}" for u in attendees)
            if attendees else "- *(None)*"
        )
        attendee_msg = await announcement_channel.send(attendee_list)

        confirmation = await input_channel.send(
            f"Event posted in {announcement_channel.mention}."
        )

        self.active_events[guild_id] = {
            "input_channel_id": input_channel.id,
            "announcement_channel_id": announcement_channel.id,
            "announcement_message_id": announcement.id,
            "attendee_message_id": attendee_msg.id,
            "confirmation_message_id": confirmation.id,
            "countdown_message_id": countdown_msg.id,
        }

        await asyncio.sleep(30)
        await countdown_msg.delete()
        await confirmation.delete()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def eventend(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.active_events:
            return await ctx.send("There is no active event to end.")

        data = self.active_events[guild_id]
        input_channel = self.bot.get_channel(data["input_channel_id"])
        announcement_channel = self.bot.get_channel(data["announcement_channel_id"])

        try:
            # Clear bot messages in input channel
            async for m in input_channel.history(limit=None):
                if m.author == self.bot.user:
                    await m.delete()
            # Delete messages stored from the event
            for msg_id in [
                data.get("announcement_message_id"),
                data.get("attendee_message_id"),
                data.get("confirmation_message_id"),
                data.get("countdown_message_id"),
            ]:
                if msg_id:
                    try:
                        msg = await announcement_channel.fetch_message(msg_id)
                        await msg.delete()
                    except Exception:
                        pass

            await ctx.send(
                f"Event ended and cleaned in {input_channel.mention} / {announcement_channel.mention}."
            )
            del self.active_events[guild_id]

        except Exception as e:
            await ctx.send(f"Error ending event: {e}")



logger = logging.getLogger('EventCog')
logging.basicConfig(level=logging.DEBUG)