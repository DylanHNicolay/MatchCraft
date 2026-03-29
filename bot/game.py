import discord
from discord import app_commands
from discord.ext import commands
from utils.db import db
from views.helpers import EmbedView

class Game(commands.Cog):
    group = app_commands.Group(name="game",description="Related to games")

    def __init__(self, bot) -> None:
        self.bot = bot
        self.adminCog=self.bot.get_cog("Admin")

    def verifyAdmin(self, user: discord.User):
        return self.adminCog.verifyAdmin(user)

    @group.command(name="create", description="Creates a new game")
    async def creategame(self, interaction: discord.Interaction, game_name : str, teams : int, players_per_team : int, role_based_matchmaking : bool, admin_role : discord.Role, access_role : discord.Role, num_roles : int | None):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)
        
        if players_per_team <= 0 or teams < 2:
            return await interaction.response.send_message(view=EmbedView(myText="Ensure that the number of teams is greater than 1 and there are players on each team"),ephemeral=True)
        
        # Check if number of roles is correctly specified for role based matchmaking
        if role_based_matchmaking and num_roles == None:
            return await interaction.response.send_message(view=EmbedView(myText="Please specify the number of roles for role based matchmaking, or disable role based matchmaking"),ephemeral=True)
        
        try:
            await db.connect()
            await db.execute("INSERT INTO game_configuration (game_name, channel_id, players_per_team, team_count, role_count) VALUES ($1, $2, $3, $4, $5);", game_name, interaction.channel_id, players_per_team, teams, num_roles if role_based_matchmaking else 1)
            await db.close()
        except:
            return await interaction.response.send_message(view=EmbedView(myText="Unable to add game to database"),ephemeral=True)
        
        # Create the channels
        """
        category_override = { # Ensures that the access role can see the category
            interaction.guild.default_role: discord.PermissionOverwrite(
                view_channel=False, 
                send_messages=False
            ),
            access_role: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=False
            ),
            admin_role: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True
            )
        }
        category = await interaction.guild.create_category(game_name, overwrites=category_override, reason=None)
        announcements_override = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                view_channel=False, 
                send_messages=False
            ),
            access_role: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=False
            ),
            admin_role: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True
            )
        }
        announcements_channel = await interaction.guild.create_text_channel(name = f"{game_name}-annnouncements", overwrites = announcements_override, category=category, reason=None)
        general_channel = await interaction.guild.create_text_channel(name = f"{game_name}-general", category=category, reason=None)
        """ 
        if not role_based_matchmaking:
            return await interaction.response.send_message(view=EmbedView(myText="Finished setting up game."),ephemeral=True)
        
        def check_user(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            await db.connect()
        except:
            return await interaction.response.send_message(view=EmbedView(myText="Couldn't re-connect to DB for role info."),ephemeral=True)

        await interaction.response.defer()
        for role_number in range(num_roles + 1):
            await interaction.followup.send(f"Send the name of role {role_number + 1}")
            user_reply = await self.bot.wait_for('message', check=check_user, timeout=30)
            
            try:
                await db.execute("INSERT INTO role_information (game_name, role_name) VALUES ($1, $2);", game_name, user_reply.content.strip())
            except:
                return await interaction.followup.send(view=EmbedView(myText="Unable to insert role information into database"),ephemeral=True)

        await db.close()
        await interaction.followup.send(view=EmbedView(myText="Finished setting up game."),ephemeral=True)
    
    # This command now works as intended. Nice!
    @group.command(name="delete", description="ADMINS ONLY: Stops given games in dropdown")
    async def deletegames(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)
        try:
            await db.connect()
            record = await db.execute("SELECT game_name FROM game_configuration WHERE channel_id = $1;",interaction.channel_id)
            await db.close()
        except:
            return await interaction.response.send_message(view=EmbedView(myText="Unable to delete game from database"),ephemeral=True)
        if len(record) == 0:
            return await interaction.response.send_message(view=EmbedView(myText="No games found in this channel."),ephemeral=True)
        
        class Dropdown(discord.ui.Select):
            def __init__(self):
                options = []
                for game in record:
                    options.append(discord.SelectOption(label=game['game_name']))
                super().__init__(placeholder="Choose a game to delete!",min_values=1,max_values=1,options=options)
            async def callback(self, interaction: discord.Interaction):
                await db.connect()
                await db.execute("DELETE FROM game_configuration WHERE game_name = $1;",self.values[0])
                await db.close()
                await interaction.response.send_message(view=EmbedView(myText="Removal succeeded!"),ephemeral=True)

        class DropdownView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.add_item(Dropdown())

        await interaction.response.send_message(view=DropdownView(),ephemeral=True,delete_after=60)
        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Game(bot))