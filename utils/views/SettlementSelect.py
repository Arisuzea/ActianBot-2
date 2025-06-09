import discord
from discord import ui, SelectOption, Interaction
from utils.location_data import LOCATION_DATA

class SettlementSelect(ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        region = self.parent_view.answers.get("region")
        province = self.parent_view.answers.get("province")
        selected_settlement = self.parent_view.answers.get("settlement")

        if region and province:
            settlements = LOCATION_DATA.get(region, {}).get(province, [])
            options = [
                SelectOption(label=s, value=s, default=(s == selected_settlement))
                for s in settlements
            ]
            disabled = False
        else:
            options = [SelectOption(label="Select a Settlement...", value="none", default=True)]
            disabled = True

        super().__init__(
            placeholder="Select a Settlement...",
            options=options,
            disabled=disabled
        )

    async def callback(self, interaction: Interaction):
        settlement = self.values[0]
        self.parent_view.answers["settlement"] = settlement

        self.parent_view.update_confirm_button()
        
        region = self.parent_view.answers.get("region")
        province = self.parent_view.answers.get("province")

        if region and province:
            settlements = LOCATION_DATA.get(region, {}).get(province, [])
        else:
            settlements = []

        self.options = [
            SelectOption(label=s, value=s, default=(s == settlement))
            for s in settlements
        ]

        await interaction.response.edit_message(view=self.parent_view)
