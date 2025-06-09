import discord
from discord import ui
from utils.views.RegionSelect import RegionSelect
from utils.views.ProvinceSelect import ProvinceSelect
from utils.views.SettlementSelect import SettlementSelect

class LocationSelectView(ui.View):
    def __init__(self, answers):
        super().__init__(timeout=300)
        self.answers = answers
        self.confirm_button = ui.Button(label="Confirm", style=discord.ButtonStyle.green, disabled=True)
        self.confirm_button.callback = self.confirm_callback

        # Initialize selects with the view itself as parent_view
        self.region_select = RegionSelect(self)
        self.province_select = ProvinceSelect(self)
        self.settlement_select = SettlementSelect(self)

        # Add items to the view
        self.add_item(self.region_select)
        self.add_item(self.province_select)
        self.add_item(self.settlement_select)
        self.add_item(self.confirm_button)

        # Initial button state update
        self.update_confirm_button()

    def update_confirm_button(self):
        # Enable confirm only if all answers are selected and not default placeholders
        enabled = all(
            self.answers.get(k) and self.answers[k] != "none"
            for k in ("region", "province", "settlement")
        )
        self.confirm_button.disabled = not enabled

    async def confirm_callback(self, interaction: discord.Interaction):
        # Confirm logic here
        await interaction.response.send_message("Location confirmed!", ephemeral=True)
        self.stop()
