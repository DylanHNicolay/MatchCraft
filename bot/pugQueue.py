import discord
from discord import app_commands
from discord.ext import commands
from views.helpers import EmbedView, EmbedPugView


class Queue(commands.Cog):
    group = app_commands.Group(name="queue",description="Related to pug queues")

    def __init__(self,bot) -> None:
        self.bot=bot
        self.queueDict={}
        self.inMatch={}
        self.adminCog=self.bot.get_cog("Admin")

    #Deletes the original queue message and reposts it any time a user posts in the queue channel so it is always visible     
    @commands.Cog.listener(name='on_message')  
    async def repostQueueMessage(self,message):
        channel=message.channel
        if channel.id in self.queueDict.keys() and not (message.author == self.bot.user) :
            temp= await channel.fetch_message(self.queueDict[channel.id]["queue_message_id"])
            await temp.delete()
            #await channel.send(view=EmbedPugView(myQueueName=self.queueDict[channel.id]["game"],myText=self.queueMessage,myQueue=self)) #does not work because view is not serializable
            initMessage = await channel.send(view=EmbedView(myText="{game} PUGs\n\n{message}\n\n/join to join queue\n/leave to leave queue".format(game=self.queueDict[channel.id]["game"],message=self.queueMessage(channel))))
            self.queueDict[channel.id]["queue_message_id"]=initMessage.id

    #####ADMIN_COMMANDS################################################################################

    # Verify Admin for this class: asks "Admin" Cog (which has the whitelist) to perform check
    # This allows database access to be limited to one Cog
    def verifyAdmin(self, user: discord.User):
        return self.adminCog.verifyAdmin(user)
        
    #Starts a queue if one does not exist in the current channel
    @group.command(name="start",description="ADMIN ONLY: Starts a queue if one does not exist in the current channel")
    async def startqueue(self, interaction: discord.Interaction, game: str, maxplayers: int):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)

        channel=interaction.channel
        if channel.id in self.queueDict.keys():
            return await interaction.response.send_message(view=EmbedView(myText="A queue already exists in this channel"),ephemeral=True)

        try:    
            self.queueDict.update({
                channel.id:{
                    "game" : game,
                    "max_players" : maxplayers,
                    "player_queue" : [],
                    "queue_message_id": None,
                    "active_matches" : []
                }
            })
            initMessage = await interaction.response.send_message(view=EmbedView(myText="{game} PUGs\n\n{message}\n\n/join to join queue\n/leave to leave queue".format(game=game,message=self.queueMessage(channel))))
            #initMessage = await interaction.response.send_message(view=EmbedPugView(myQueueName=game,myText=self.queueMessage,myQueue=self))
            #await interaction.response.send_message(view=EmbedPugView(myQueueName=game,myText=self.queueMessage,myQueue=self))
            self.queueDict[channel.id]["queue_message_id"]= initMessage.message_id
        except: 
            return await interaction.response.send_message(view=EmbedView(myText="error adding new queue [{id}] to active_queues".format(id=channel.id)))

    #Stops the queue in the current channel if one exists
    @group.command(name="end",description="ADMIN ONLY: Ends the queue in the current channel if one exists")
    async def stopqueue(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)

        channel=interaction.channel
        if channel.id not in self.queueDict.keys():
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"),ephemeral=True)

        try:
            mes = await channel.fetch_message(self.queueDict[channel.id]["queue_message_id"])
            await mes.edit(delete_after=0.0)
            del self.queueDict[channel.id]
            await interaction.response.send_message(view=EmbedView(myText="{name} is no longer a pug channel".format(name=channel.name)))
        except: 
            await interaction.response.send_message(view=EmbedView(myText="error removing queue [{id}] from active_queues".format(id=channel.id)))


    #Add a person to the waiting list
    @group.command(name="add",description="ADMIN ONLY: Adds the specified User (not already in queue) to the current queue")
    async def add(self, interaction: discord.Interaction, user: discord.User):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)

        channel=interaction.channel
        if channel.id not in self.queueDict.keys():
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"),ephemeral=True)

        name=user.name
        if name in self.queueDict[channel.id]["player_queue"]:
            output="that person is already in the queue\n" + self.queueMessage(channel)
            return await interaction.response.send_message(view=EmbedPugView(myQueueName=self.queueDict[channel.id]["game"],myText=output,myQueue=self),ephemeral=True)
        
        output="cannot add player to non-queue channel"
        failure = False

        self.queueDict[channel.id]["player_queue"].append(name)
        if len(self.queueDict[channel.id]["player_queue"])<self.queueDict[channel.id]["max_players"]:
            output=name + " joined the queue\n" + self.queueMessage(channel)
        else:
            failure = True
            self.__startMatch()

        await interaction.response.send_message(view=EmbedPugView(myQueueName=self.queueDict[channel.id]["game"],myText=output,myQueue=self),ephemeral=failure)

    #Remove a person from the waiting list
    @group.command(name="kick",description="ADMIN ONLY: Kicks the specified User (in the queue) from the current queue")
    async def remove(self, interaction: discord.Interaction, user: discord.User):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"),ephemeral=True)

        channel=interaction.channel

        if channel.id not in self.queueDict.keys():
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"),ephemeral=True)

        name=user.name
        output=""
        failure = False
    
        if(name in self.queueDict[channel.id]["player_queue"]):
            self.queueDict[channel.id]["player_queue"].remove(name)
            output=name + " left the queue\n" + self.queueMessage(channel)
        else: 
            failure = True
            output="that person is not in this queue"
        await interaction.response.send_message(view=EmbedPugView(myQueueName=self.queueDict[channel.id]["game"],myText=output,myQueue=self),ephemeral=failure)
    
        
    #########QUEUE_COMMANDS###################    
    
    #returns a string that lists how many players players are in the requested queue
    def queueMessage(self,channel):
        queueMessage="("
        for x in range (0,len(self.queueDict[channel.id]["player_queue"])):
            queueMessage=queueMessage+self.queueDict[channel.id]["player_queue"][x]
            if(x<len(self.queueDict[channel.id]["player_queue"])-1):
                queueMessage=queueMessage+","
        queueMessage=queueMessage + ")["+str(len(self.queueDict[channel.id]["player_queue"]))+"/"+str(self.queueDict[channel.id]["max_players"])+"]"
        return queueMessage
    
    #initial outline for match flow
    def __startMatch(self,channel):
        #announce match start
        matchParticipants=[]
        for x in range(0,self.queueDict[channel.id]["max_players"]):
          matchParticipants.append(self.queueDict[channel.id]["player_queue"].pop(0))
        for a in matchParticipants:
            self.inMatch.update({a : channel.id})
        print("a match started with the following participants: " + matchParticipants)
        #perform check-in
        #captain voting and team selection
        #outcome reporting
     
    #adds the player to the queue 
    @group.command(name="join",description="Join the queue in the current channel")
    async def join(self, interaction: discord.Interaction):
        channel=interaction.channel
        if channel.id not in self.queueDict.keys():
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"),ephemeral=True)

        name=interaction.user.name
        if name in self.queueDict[channel.id]["player_queue"]:
            output="you are already in the queue\n" + self.queueMessage(channel)
            return await interaction.response.send_message(view=EmbedPugView(myQueueName=self.queueDict[channel.id]["game"],myText=output,myQueue=self),ephemeral=True)
        
        output=""
        failure = False

        self.queueDict[channel.id]["player_queue"].append(name)
        if len(self.queueDict[channel.id]["player_queue"])<self.queueDict[channel.id]["max_players"]:
            output=name + " joined the queue\n" + self.queueMessage(channel)
        else:
            failure = True
            self.__startMatch()

        await interaction.response.send_message(view=EmbedPugView(myQueueName=self.queueDict[channel.id]["game"],myText=output,myQueue=self),ephemeral=failure)


    #removes the player from the queue
    @group.command(name="leave",description="Leave the queue in the current channel")
    async def leave(self, interaction: discord.Interaction):
        channel=interaction.channel
        if channel.id not in self.queueDict.keys():
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"),ephemeral=True)

        name=interaction.user.name
        output="cannot remove player from non-queue channel"
        failure = False
        
        if(name in self.queueDict[channel.id]["player_queue"]):
            self.queueDict[channel.id]["player_queue"].remove(name)
            output=name + " left the queue\n" + self.queueMessage(channel)
        else: 
            failure = True
            output="you are not in this queue"
        await interaction.response.send_message(view=EmbedPugView(myQueueName=self.queueDict[channel.id]["game"],myText=output,myQueue=self),ephemeral=failure)

    #displays how many players are in the queue
    @group.command(name="status",description="Displays the number of players currently in the queue")
    async def queuestatus(self, interaction: discord.Interaction):
        channel=interaction.channel
        output="cannot check queue in non-queue channel"
        if channel.id in self.queueDict.keys():
            output=self.queueMessage(channel)
        await interaction.response.send_message(view=EmbedView(myText=output))

#applies the cog to the bot on startup
async def setup(bot: commands.Bot)-> None:
    await bot.add_cog(Queue(bot))