import discord
from discord import app_commands
from discord.ext import commands
from utils.db import db
from views.helpers import EmbedView

class Admin(commands.Cog):
    group = app_commands.Group(name="admin",description="For pug admin use")

    def __init__(self, bot) -> None:
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

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
