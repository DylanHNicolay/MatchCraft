import discord
from discord import ui
from discord.ext import commands

# Forward declaration of Queue class
class Queue(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

#standard embed view for sending messages with the bot
class EmbedView(ui.LayoutView):
    def __init__(self, *, myText: str) -> None:
        super().__init__(timeout=None)
        self.text = ui.TextDisplay(myText)
        container = ui.Container(self.text, accent_color=discord.Color.red())
        self.add_item(container)

#embed view that makes use of buttons to add and remove the user from the queue
class EmbedPugView(ui.LayoutView):
    def __init__(self, *, myQueueName: str, myText: str, myQueue: Queue) -> None:
        super().__init__()
        self.myQueue=myQueue
        self.queueName = ui.TextDisplay("Queue for " + myQueueName)
        self.text = ui.TextDisplay(myText)
        self.sep=ui.Separator(visible=True)
        self.row=MyActionRow(myQueue)
        container = ui.Container(self.queueName, self.sep, self.text, self.sep, self.row, accent_color=discord.Color.red())
        self.add_item(container)

#button template from discord.py api
class MyActionRow(ui.ActionRow):
    def __init__(self, queue: Queue) -> None:
        super().__init__()
        self.queue=queue
    
    #Adds player to the queue when the press the add button
    @ui.button(label='Join', style=discord.ButtonStyle.green)
    async def add(self, interaction: discord.Interaction, button: discord.Button):
        return await self.queue.accessDict(interaction,interaction.user,True)

    #Removes the player from the queue when they press the remove button
    @ui.button(label='Leave',style=discord.ButtonStyle.red)
    async def remove(self, interaction: discord.Interaction, button: discord.Button):
        return await self.queue.accessDict(interaction,interaction.user,False)