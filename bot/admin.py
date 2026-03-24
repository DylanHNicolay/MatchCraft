import discord
from discord import app_commands
from discord.ext import commands
from utils.db import db
from views.helpers import EmbedView

class Admin(commands.Cog):
    group = app_commands.Group(name="admin",description="For pug admin use")
    group_game = app_commands.Group(name="config-game",description="Related to games")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.adminWhitelistRole=[]

    #async database setup
    #populate admin whitelist and queue dictionary with values from the database
    async def cog_load(self):
        await db.connect()
        adminRoles = await db.execute("SELECT role_id FROM administrative_roles;")
        await db.close()
        for role in adminRoles:
            self.adminWhitelistRole.append(role['role_id']) 

    def verifyAdmin(self, user: discord.User):
        for role in user.roles:
            if role.id in self.adminWhitelistRole:
                return True
        return False

    #Add the specified role to the pug admin whitelist
    @group.command(name="add",description="OWNER ONLY: Adds a role into the list of Admin Roles")
    async def addadminrole(self, interaction: discord.Interaction, role: discord.Role):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for the owner"),ephemeral=True)

        outMessage=role.name + " already has pug admin perms"
        if role.id not in self.adminWhitelistRole:
            self.adminWhitelistRole.append(role.id)
            outMessage=role.name + " now has pug admin perms"
            try:
                await db.connect()
                await db.execute("INSERT INTO administrative_roles (role_id) VALUES ($1);",role.id)
                await db.close()
            except: 
                return await interaction.response.send_message(view=EmbedView(myText="error adding {id} to the database".format(id=role.id)),ephemeral=True)
        await interaction.response.send_message(view=EmbedView(myText=outMessage),ephemeral=True)
            
    #Remove the specified role from the pug admin whitelist
    @group.command(name="remove",description="OWNER ONLY: Removes a role from the list of Admin Roles")
    async def removeadminrole(self, interaction: discord.Interaction, role: discord.Role):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for the owner"),ephemeral=True)

        outMessage=role.name + " does not have pug admin perms"
        if role.id in self.adminWhitelistRole:
            self.adminWhitelistRole.remove(role.id)
            outMessage=role.name + " no longer has pug admin perms"
            try:
                await db.connect()
                await db.execute("DELETE FROM administrative_roles WHERE role_id = $1;",role.id)
                await db.close()
            except: 
                return await interaction.response.send_message(view=EmbedView(myText="error removing {id} from the database".format(id=role.id)),ephemeral=True)
        await interaction.response.send_message(view=EmbedView(myText=outMessage),ephemeral=True)

    #display a message containing all the whitelisted roles for pug administration
    @group.command(name="list_roles",description="ADMINS ONLY: Displays all current Admin roles")
    async def getadminroles(self,interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)

        outMessage="The following roles have admin perms:\n"
        for x in self.adminWhitelistRole:
            outMessage += (interaction.guild.get_role(x).name + "\n")
        await interaction.response.send_message(view=EmbedView(myText=outMessage),ephemeral=True)

    @group.command(name="list",description="ADMINS ONLY: Displays all current Admin users")
    async def getadmins(self,interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)
        
        outMessage="The following users have admin perms:\n"
        for user in interaction.guild.members:
            for role in user.roles:
                if role.id in self.adminWhitelistRole:
                    outMessage += (user.mention + "\n")
                    break
        await interaction.response.send_message(view=EmbedView(myText=outMessage),ephemeral=True)

    # TODO: Move this elsewhere
    @group_game.command(name="create", description="Creates a new game")
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
            # NOW USES CHANNEL ID AS MAIN KEY
            await db.execute("INSERT INTO game_configuration (game_name, channel_id, players_per_team, team_count, role_count) VALUES ($1, $2, $3, $4, $5);", game_name, interaction.channel_id, players_per_team, teams, num_roles if role_based_matchmaking else 1)
            await db.close()
        except:
            return await interaction.response.send_message(view=EmbedView(myText="Unable to add game to database"),ephemeral=True)
        
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
    @group_game.command(name="delete", description="ADMINS ONLY: Stops given games in dropdown")
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
        
async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
