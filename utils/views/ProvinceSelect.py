import discord
from discord import ui, SelectOption, Interaction
from utils.location_data import LOCATION_DATA
from utils.views.SettlementSelect import SettlementSelect

class ProvinceSelect(ui.Select):
    def __init__(self, parent_view):
        selected_province = parent_view.answers.get("province")
        super().__init__(
            placeholder="Select a Province...",
            options=[SelectOption(label="Select a Province...", value="none", default=True)],
            disabled=True
        )
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        province = self.values[0]
        self.parent_view.answers["province"] = province
        # Reset dependent answer
        self.parent_view.answers["settlement"] = None

        region = self.parent_view.answers.get("region")
        if not region:
            await interaction.response.send_message("Please select a region first.", ephemeral=True)
            return

        settlements = LOCATION_DATA[region][province]

        # Rebuild SettlementSelect
        self.parent_view.remove_item(self.parent_view.settlement_select)
        self.parent_view.settlement_select = SettlementSelect(self.parent_view)
        self.parent_view.settlement_select.options = [
            SelectOption(label=s, value=s, default=False) for s in settlements
        ]
        self.parent_view.settlement_select.disabled = False
        self.parent_view.add_item(self.parent_view.settlement_select)

        self.parent_view.update_confirm_button()

        self.options = [
            SelectOption(label=p, value=p, default=(p == province))
            for p in LOCATION_DATA[region].keys()
        ]

        await interaction.response.edit_message(view=self.parent_view)
