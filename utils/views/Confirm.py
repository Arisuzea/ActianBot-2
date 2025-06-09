import discord
from discord import ui, SelectOption, Interaction


class ConfirmView(ui.View):

    def __init__(self):
        super().__init__(timeout=60)
        self.value: bool | None = None

    @ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: Interaction, _):
        self.value = True
        await interaction.response.send_message("Form confirmed.",
                                                ephemeral=True)
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: Interaction, _):
        self.value = False
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.stop()