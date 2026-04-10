import discord
from discord import app_commands
from discord.ext import commands
from views.helpers import EmbedView


class botHelp(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help",description="Displays all commands of the bot")
    async def help(self, interaction: discord.Interaction):
        message = "Bot Command List:\n\n"
        try:
            for cog in self.bot.cogs.values():
                commands = cog.get_app_commands()
                for command in commands:
                    if (isinstance(command,app_commands.Group)):
                        for actual_command in command.walk_commands():
                            message += (f"/{command.name} {actual_command.name} - {actual_command.description}\n")
                    else:
                        message += (f"/{command.name} - {command.description}\n")
            await interaction.response.send_message(view=EmbedView(myText=message),ephemeral=True)
        except:
            await interaction.response.send_message(view=EmbedView(myText="Command failed... try again later."),ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(botHelp(bot))