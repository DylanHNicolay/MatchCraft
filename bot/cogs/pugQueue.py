import discord
from discord import app_commands
from discord.ext import commands
from views.helpers import EmbedView, EmbedPugView

class Queue(commands.Cog):
    group = app_commands.Group(name="queue",description="Related to pug queues")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.adminCog = bot.get_cog("Admin")
        self.gameCog = bot.get_cog("Game")
        self.queueDict = {}

    # returns a string of all the users in current channel's queue
    def getmsg(self, channel: discord.TextChannel) -> str:
        if len(self.queueDict[channel.id]["players"]) == 0:
            return "\nNo one is in this queue\n"
        
        msg = "The following users are in the queue:\n"
        for x in range(len(self.queueDict[channel.id]["players"])):
            msg += (self.queueDict[channel.id]["players"][x]).mention
            if(x != len(self.queueDict[channel.id]["players"])-1):
                msg += "\n"

        # this line adds a display of how "full" the queue is
        return (msg+("\n["+str(len(self.queueDict[channel.id]["players"]))+"/"+str(self.queueDict[channel.id]["max"])+"]"))
    
    # edits the queue message to reflect changes
    async def editMessage(self, channel: discord.TextChannel) -> None:
        if channel.id in self.queueDict.keys():
            msg = await channel.fetch_message(self.queueDict[channel.id]["msg_id"])
            await msg.edit(view=EmbedPugView(myQueueName=self.queueDict[channel.id]["name"],myText=self.getmsg(channel),myQueue=self))

    # adds/removes the player from the queue if conditions are met (removes duplicate code)
    async def accessDict(self, interaction: discord.Interaction, user: discord.User, add) -> None:
        cur_channel = interaction.channel
        if cur_channel.id not in self.queueDict.keys():
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"),ephemeral=True)

        if add == (user in self.queueDict[cur_channel.id]["players"]): # this does one thing for add, the other for remove
            return await interaction.response.send_message(view=EmbedView(myText=(f"{user.mention} is " + ("already" if add else "not") + " in the queue")),ephemeral=True)
        
        if len(self.queueDict[cur_channel.id]["players"]) == self.queueDict[cur_channel.id]["max"]:
            return await interaction.response.send_message(view=EmbedView(myText="The queue is already full"),ephemeral=True)
        
        if self.queueDict[cur_channel.id]["start"]:
            return await interaction.response.send_message(view=EmbedView(myText="The queue has already started"),ephemeral=True)
        
        self.queueDict[cur_channel.id]["players"].append(user) if add else self.queueDict[cur_channel.id]["players"].remove(user)
        
        await interaction.response.send_message(view=EmbedView(myText=("Successfully " + ("added" if add else "removed") + " player")),ephemeral=True)

        return await self.editMessage(cur_channel)


    # we ask the admin cog to verify admins for us
    def verifyAdmin(self, user: discord.User) -> bool:
        return self.adminCog.verifyAdmin(user)
    
    # ADMIN ONLY COMMANDS

    # creates queue
    @group.command(name="create",description="ADMIN ONLY: Starts a queue if one does not exist in the current game channel")
    async def startqueue(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user): # admin check
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)
        
        record = await self.gameCog.getGame(interaction.channel.category.id)
        if len(record) == 0:
            return await interaction.response.send_message(view=EmbedView(myText="This channel is not a game channel"),ephemeral=True)

        cur_channel = interaction.channel
        if cur_channel.id in self.queueDict.keys(): # make sure the channel does not have queue
            return await interaction.response.send_message(view=EmbedView(myText="A queue already exists in this channel"),ephemeral=True)
        
        game_name = ""
        maxplayers = 0

        for game in record:
            game_name = game['game_name']
            maxplayers = int(game['players_per_team']) * int(game['team_count'])
            break

        
        # add the queue to the dictionary
        self.queueDict[cur_channel.id] = {
            "name": game_name,
            "max": maxplayers,
            "players": [],
            "msg_id": None,
            "vc": None,
            "start": False
        }

        msg = await cur_channel.send(view=EmbedPugView(myQueueName=game_name,myText=self.getmsg(cur_channel),myQueue=self))
        self.queueDict[cur_channel.id]["msg_id"] = msg.id

        await interaction.response.send_message(view=EmbedView(myText="Queue creation success!"),ephemeral=True)

    @group.command(name="resend",description="ADMIN ONLY: Re-sends the queue message if one exists in the channel")
    async def sendqueue(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user): # admin check
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)

        cur_channel = interaction.channel
        if cur_channel.id not in self.queueDict.keys(): # make sure the channel does not have queue
            return await interaction.response.send_message(view=EmbedView(myText="A queue does not exist in this channel"),ephemeral=True)
        
        if self.queueDict[cur_channel.id]["start"]:
            return await interaction.response.send_message(view=EmbedView(myText="The queue has already started"),ephemeral=True)
        
        msg = await cur_channel.fetch_message(self.queueDict[cur_channel.id]["msg_id"])
        await msg.delete()

        newmsg = await cur_channel.send(view=EmbedPugView(myQueueName=self.queueDict[cur_channel.id]["name"],myText=self.getmsg(cur_channel),myQueue=self))
        self.queueDict[cur_channel.id]["msg_id"] = newmsg.id
        
        await interaction.response.send_message(view=EmbedView(myText="Resend success!"),ephemeral=True)


    # stops queue
    @group.command(name="end",description="ADMIN ONLY: Ends the queue in the current channel if one exists")
    async def stopqueue(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)

        cur_channel = interaction.channel
        if cur_channel.id not in self.queueDict.keys():
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"),ephemeral=True)

        try: # remove queue from dictionary and delete original queue message
            if ((msgid := self.queueDict[cur_channel.id]["msg_id"]) != None):
                msg = await cur_channel.fetch_message(msgid)
                await msg.delete()
            if ((vc := self.queueDict[cur_channel.id]["vc"]) != None):
                await vc.delete()
            del self.queueDict[cur_channel.id]
            await interaction.response.send_message(view=EmbedView(myText=f"The queue in this channel has ended"))
        except: 
            await interaction.response.send_message(view=EmbedView(myText="Error in removing queue from this channel"),ephemeral=True)
    
    # add a user to the queue if not full
    @group.command(name="add",description="ADMIN ONLY: Adds the specified User (not already in queue) to the current queue")
    async def add(self, interaction: discord.Interaction, user: discord.User):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)
        
        return await self.accessDict(interaction,user,True)
    
    # kick a user from the queue
    @group.command(name="kick",description="ADMIN ONLY: Kicks the specified User (in the queue) from the current queue")
    async def remove(self, interaction: discord.Interaction, user: discord.User):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)

        return await self.accessDict(interaction,user,False)
    
    # TODO: start the game
    @group.command(name="start",description="ADMIN ONLY: Immediately starts the game")
    async def start(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)
        
        cur_channel = interaction.channel
        if cur_channel.id not in self.queueDict.keys():
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"),ephemeral=True)

        if len(self.queueDict[cur_channel.id]["players"]) == 0:
            return await interaction.response.send_message(view=EmbedView(myText="There is no one in the queue"),ephemeral=True)
        
        overwrite = {}
        overwrite[interaction.guild.default_role] = discord.PermissionOverwrite(view_channel=False)
        for player in self.queueDict[cur_channel.id]["players"]:
            overwrite[player] = discord.PermissionOverwrite(
                view_channel = True,
                speak = True
            )
        
        vc = await interaction.guild.create_voice_channel(name=self.queueDict[cur_channel.id]["name"],overwrites=overwrite,category=interaction.channel.category)
        self.queueDict[cur_channel.id]["vc"] = vc
        self.queueDict[cur_channel.id]["start"] = True

        msg = await cur_channel.fetch_message(self.queueDict[cur_channel.id]["msg_id"])
        await msg.delete()
        self.queueDict[cur_channel.id]["msg_id"] = None

        invite = await vc.create_invite()

        await interaction.response.defer()

        for player in self.queueDict[cur_channel.id]["players"]:
            dm = await player.create_dm()
            await dm.send(content=invite.url)

        await interaction.followup.send(view=EmbedView(myText="Start success!"),ephemeral=True)  

    # Below are commands which anyone can use

    # join the queue
    @group.command(name="join",description="Join the queue in the current channel")
    async def join(self, interaction: discord.Interaction):
        return await self.accessDict(interaction,interaction.user,True)
    
    # leave the queue
    @group.command(name="leave",description="Leave the queue in the current channel")
    async def remove(self, interaction: discord.Interaction):
        return await self.accessDict(interaction,interaction.user,False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Queue(bot))