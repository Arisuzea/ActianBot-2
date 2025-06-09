import discord
from discord.ext import commands
import asyncio
from config import TOKEN
from keep_alive import keep_alive
from cogs.event_cog import EventCog

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="ab!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

async def main():
    await bot.add_cog(EventCog(bot))
    await bot.start(TOKEN)

keep_alive()
asyncio.run(main())
