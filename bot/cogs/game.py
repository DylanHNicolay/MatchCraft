import discord
from discord import app_commands
from discord.ext import commands
from utils.db import db
from views.helpers import EmbedView

class Game(commands.Cog):
    group = app_commands.Group(name="game",description="Related to games")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.adminCog=self.bot.get_cog("Admin")

    def verifyAdmin(self, user: discord.Member) -> bool:
        return self.adminCog.verifyAdmin(user)
    
    async def getGame(self, category_id: int):
        await db.connect()
        retval = await db.execute("SELECT * FROM game_configuration WHERE category = $1;", category_id)
        await db.close()
        return retval

    @group.command(name="create", description="ADMIN ONLY: Creates a new game")
    async def creategame(self, interaction: discord.Interaction, game_name : str, teams : int, players_per_team : int, role_based_matchmaking : bool, admin_role : discord.Role, access_role : discord.Role, num_roles : int | None):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)
        
        if players_per_team < 1 or teams < 1:
            return await interaction.response.send_message(view=EmbedView(myText="Ensure that the number of teams is at least 1 and there are players on each team"),ephemeral=True)
        
        # Check if number of roles is correctly specified for role based matchmaking
        if role_based_matchmaking and num_roles == None:
            return await interaction.response.send_message(view=EmbedView(myText="Please specify the number of roles for role based matchmaking, or disable role based matchmaking"),ephemeral=True)
        
        try:
            await db.connect()
            record = await db.execute("SELECT game_name FROM game_configuration WHERE game_name = $1 AND guild = $2;",game_name,interaction.guild_id)
            await db.close()
            if len(record) != 0:
                return await interaction.response.send_message(view=EmbedView(myText="A game with that name already exists in the server"),ephemeral=True)
        except:
            return await interaction.response.send_message(view=EmbedView(myText="Database access failed"),ephemeral=True)

        await interaction.response.defer()
        # Create the channels
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
        general_override = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                view_channel=False, 
                send_messages=False
            ),
            access_role: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True
            ),
            admin_role: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True
            )
        }

        await interaction.guild.create_text_channel(name = f"{game_name}-annnouncements", category=category)
        await interaction.guild.create_text_channel(name = f"{game_name}-general", overwrites = general_override, category=category)

        try:
            await db.connect()
            await db.execute("INSERT INTO game_configuration (game_name, guild, category, players_per_team, team_count, role_count) VALUES ($1, $2, $3, $4, $5, $6);", game_name, interaction.guild_id, category.id, players_per_team, teams, num_roles if role_based_matchmaking else 1)
            await db.close()
        except:
            return await interaction.followup.send(view=EmbedView(myText="Unable to add game to database"),ephemeral=True)

        if not role_based_matchmaking:
            return await interaction.followup.send(view=EmbedView(myText="Finished setting up game."),ephemeral=True)
        
        def check_user(m: discord.Message) -> bool:
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            await db.connect()
        except:
            return await interaction.followup.send(view=EmbedView(myText="Couldn't re-connect to DB for role info."),ephemeral=True)

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
    @group.command(name="delete", description="ADMIN ONLY: Stops given games in dropdown. The dropdown lasts for 60 seconds")
    async def deletegames(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)
        try:
            await db.connect()
            record = await db.execute("SELECT * FROM game_configuration WHERE guild = $1;",interaction.guild_id)
            await db.close()
        except:
            return await interaction.response.send_message(view=EmbedView(myText="Accessing database failed."),ephemeral=True)
        if len(record) == 0:
            return await interaction.response.send_message(view=EmbedView(myText="No games found in this server."),ephemeral=True)
        
        class Dropdown(discord.ui.Select):
            def __init__(self) -> None:
                options = []
                for game in record:
                    options.append(discord.SelectOption(label=game['game_name']))
                super().__init__(placeholder="Choose a game to delete!",min_values=1,max_values=1,options=options)
            async def callback(self, interaction: discord.Interaction) -> None:
                for game in record:
                    if game['game_name'] != self.values[0]:
                        continue
                    try:
                        category = await interaction.guild.fetch_channel(game['category'])
                        for channel in category.channels:
                            await channel.delete()
                        await category.delete()
                    except:
                        return await interaction.response.send_message(view=EmbedView(myText="Removal failed."),ephemeral=True)
                    break
                await db.connect()
                await db.execute("DELETE FROM game_configuration WHERE game_name = $1;",self.values[0])
                await db.close()
                await interaction.response.send_message(view=EmbedView(myText="Removal succeeded!"),ephemeral=True)

        class DropdownView(discord.ui.View):
            def __init__(self) -> None:
                super().__init__(timeout=180)
                self.add_item(Dropdown())

        await interaction.response.send_message(view=DropdownView(),ephemeral=True,delete_after=60)
        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Game(bot))