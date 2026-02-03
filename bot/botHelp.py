import discord
from discord import app_commands
from discord.ext import commands
from views.helpers import EmbedView


class botHelp(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="help",description="Displays all commands of the bot")
    async def help(self, interaction: discord.Interaction):
        message = "Bot Command List:\n\n"
        try:
            for command in self.bot.tree.get_commands():
                message += ("/" + command.name + " - " + command.description + "\n")
            await interaction.response.send_message(view=EmbedView(myText=message),ephemeral=True)
        except:
            await interaction.response.send_message(view=EmbedView(myText="Command failed... try again later."),ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(botHelp(bot))