import discord
from discord import ui, SelectOption, Interaction


class ChannelSelect(ui.Select):
    def __init__(self, channels: list[discord.TextChannel], guild: discord.Guild):
        self.guild = guild
        opts = [
            SelectOption(label=ch.name, value=str(ch.id))
            for ch in channels if ch.type == discord.ChannelType.text
        ]
        super().__init__(
            placeholder="Choose a channel…",
            options=opts,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: Interaction):
        ch_id = int(self.values[0])
        self.view.selected_channel = self.guild.get_channel(ch_id)
        await interaction.response.send_message(
            f"Channel set to {self.view.selected_channel.mention}.",
            ephemeral=True
        )
        self.view.stop()

class ChannelSelectView(ui.View):

    def __init__(self, channels, guild):
        super().__init__()
        self.selected_channel: discord.TextChannel | None = None
        self.add_item(ChannelSelect(channels, guild))