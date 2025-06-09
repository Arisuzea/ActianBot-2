import discord
from discord import ui, SelectOption, Interaction
from utils.location_data import LOCATION_DATA
from utils.views.ProvinceSelect import ProvinceSelect
from utils.views.SettlementSelect import SettlementSelect

class RegionSelect(ui.Select):
    def __init__(self, parent_view):
        selected_region = parent_view.answers.get("region")
        options = [
            SelectOption(label=region, value=region, default=(region == selected_region))
            for region in LOCATION_DATA.keys()
        ]
        super().__init__(placeholder="Select a Region...", options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        region = self.values[0]
        self.parent_view.answers["region"] = region
        # Reset dependent answers
        self.parent_view.answers["province"] = None
        self.parent_view.answers["settlement"] = None

        provinces = LOCATION_DATA[region].keys()

        # Rebuild ProvinceSelect
        self.parent_view.remove_item(self.parent_view.province_select)
        self.parent_view.province_select = ProvinceSelect(self.parent_view)
        self.parent_view.province_select.options = [
            SelectOption(label=p, value=p, default=False) for p in provinces
        ]
        self.parent_view.province_select.disabled = False
        self.parent_view.add_item(self.parent_view.province_select)

        # Reset SettlementSelect
        self.parent_view.remove_item(self.parent_view.settlement_select)
        self.parent_view.settlement_select = SettlementSelect(self.parent_view)
        self.parent_view.settlement_select.disabled = True
        self.parent_view.add_item(self.parent_view.settlement_select)

        self.parent_view.update_confirm_button()

        self.options = [
            SelectOption(label=r, value=r, default=(r == region))
            for r in LOCATION_DATA.keys()
        ]

        await interaction.response.edit_message(view=self.parent_view)
