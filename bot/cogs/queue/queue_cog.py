import discord
from discord import app_commands
from discord.ext import commands

from views.helpers import EmbedView, EmbedPugView

from .state import PHASE_CLOSING, PHASE_OPEN, PHASE_STARTED, QueueState, QueueStore


class Queue(commands.Cog):
    group = app_commands.Group(name="queue", description="Related to pug queues")

    def __init__(self, bot) -> None:
        self.bot = bot
        self.adminCog = bot.get_cog("Admin")
        self.gameCog = bot.get_cog("Game")
        self.store = QueueStore()

    def _can_edit_roster(self, queue: QueueState) -> bool:
        return queue.phase == PHASE_OPEN

    def getmsg(self, channel: discord.TextChannel):
        queue = self.store.get_queue(channel.id)
        if queue is None or len(queue.players) == 0:
            return "\nNo one is in this queue\n"

        msg = "The following users are in the queue:\n"
        for idx, player in enumerate(queue.players):
            msg += player.mention
            if idx != len(queue.players) - 1:
                msg += "\n"

        return msg + "\n[" + str(len(queue.players)) + "/" + str(queue.max_players) + "]"

    async def editMessage(self, channel: discord.TextChannel):
        queue = self.store.get_queue(channel.id)
        if queue is None or queue.phase == PHASE_STARTED:
            return

        view = EmbedPugView(myQueueName=queue.name, myText=self.getmsg(channel), myQueue=self)
        if queue.msg_id is not None:
            try:
                msg = await channel.fetch_message(queue.msg_id)
                await msg.edit(view=view)
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        newmsg = await channel.send(view=view)
        queue.msg_id = newmsg.id
        queue.bump_revision()

    async def accessDict(self, interaction: discord.Interaction, user: discord.User, add: bool):
        cur_channel = interaction.channel
        channel_id = cur_channel.id
        lock = self.store.get_lock(channel_id)

        async with lock:
            queue = self.store.get_queue(channel_id)
            if queue is None:
                return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"), ephemeral=True)

            if not self._can_edit_roster(queue):
                return await interaction.response.send_message(view=EmbedView(myText="The queue is no longer accepting roster changes"), ephemeral=True)

            if add == (user in queue.players):
                return await interaction.response.send_message(
                    view=EmbedView(myText=(f"{user.mention} is " + ("already" if add else "not") + " in the queue")),
                    ephemeral=True,
                )

            if add and len(queue.players) == queue.max_players:
                return await interaction.response.send_message(view=EmbedView(myText="The queue is already full"), ephemeral=True)

            queue.players.append(user) if add else queue.players.remove(user)
            queue.bump_revision()

        await interaction.response.send_message(
            view=EmbedView(myText=("Successfully " + ("added" if add else "removed") + " player")),
            ephemeral=True,
        )
        return await self.editMessage(cur_channel)

    def verifyAdmin(self, user: discord.User):
        return self.adminCog.verifyAdmin(user)

    @group.command(name="create", description="ADMIN ONLY: Starts a queue if one does not exist in the current game channel")
    async def startqueue(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"), ephemeral=True)

        record = await self.gameCog.getGame(interaction.channel.category.id)
        if len(record) == 0:
            return await interaction.response.send_message(view=EmbedView(myText="This channel is not a game channel"), ephemeral=True)

        game_name = ""
        maxplayers = 0
        for game in record:
            game_name = game["game_name"]
            maxplayers = int(game["players_per_team"]) * int(game["team_count"])
            break

        cur_channel = interaction.channel
        channel_id = cur_channel.id
        queue = await self.store.create_queue(channel_id, game_name, maxplayers)
        if queue is None:
            return await interaction.response.send_message(view=EmbedView(myText="A queue already exists in this channel"), ephemeral=True)

        msg = await cur_channel.send(view=EmbedPugView(myQueueName=game_name, myText=self.getmsg(cur_channel), myQueue=self))
        queue.msg_id = msg.id
        queue.bump_revision()

        await interaction.response.send_message(view=EmbedView(myText="Game creation success!"), ephemeral=True)

    @group.command(name="resend", description="ADMIN ONLY: Re-sends the queue message if one exists in the channel")
    async def sendqueue(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"), ephemeral=True)

        cur_channel = interaction.channel
        channel_id = cur_channel.id
        if not self.store.has_queue(channel_id):
            return await interaction.response.send_message(view=EmbedView(myText="A queue does not exist in this channel"), ephemeral=True)

        lock = self.store.get_lock(channel_id)
        async with lock:
            queue = self.store.get_queue(channel_id)
            if queue is None:
                return await interaction.response.send_message(view=EmbedView(myText="A queue does not exist in this channel"), ephemeral=True)

            if queue.phase != PHASE_OPEN:
                return await interaction.response.send_message(view=EmbedView(myText="The queue is no longer in an editable phase"), ephemeral=True)

            if queue.msg_id is not None:
                try:
                    msg = await cur_channel.fetch_message(queue.msg_id)
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

            newmsg = await cur_channel.send(view=EmbedPugView(myQueueName=queue.name, myText=self.getmsg(cur_channel), myQueue=self))
            queue.msg_id = newmsg.id
            queue.bump_revision()

        await interaction.response.send_message(view=EmbedView(myText="Resend success!"), ephemeral=True)

    @group.command(name="end", description="ADMIN ONLY: Ends the queue in the current channel if one exists")
    async def stopqueue(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"), ephemeral=True)

        cur_channel = interaction.channel
        channel_id = cur_channel.id
        if not self.store.has_queue(channel_id):
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"), ephemeral=True)

        lock = self.store.get_lock(channel_id)
        async with lock:
            queue = self.store.get_queue(channel_id)
            if queue is None:
                return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"), ephemeral=True)

            if queue.phase == PHASE_CLOSING:
                return await interaction.response.send_message(view=EmbedView(myText="Queue shutdown is in progress; try again shortly"), ephemeral=True)

            queue.phase = PHASE_CLOSING
            queue.bump_revision()

        try:
            queue = self.store.get_queue(channel_id)
            if queue is None:
                return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"), ephemeral=True)

            if queue.msg_id is not None:
                try:
                    msg = await cur_channel.fetch_message(queue.msg_id)
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

            if queue.vc is not None:
                try:
                    await queue.vc.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

            self.store.remove_queue(channel_id)
            await interaction.response.send_message(view=EmbedView(myText="The queue in this channel has ended"))
        except Exception:
            queue = self.store.get_queue(channel_id)
            if queue is not None:
                async with lock:
                    queue = self.store.get_queue(channel_id)
                    if queue is not None:
                        queue.phase = PHASE_OPEN
                        queue.bump_revision()
            await interaction.response.send_message(view=EmbedView(myText="Error in removing queue from this channel"), ephemeral=True)

    @group.command(name="add", description="ADMIN ONLY: Adds the specified User (not already in queue) to the current queue")
    async def add(self, interaction: discord.Interaction, user: discord.User):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"), ephemeral=True)

        return await self.accessDict(interaction, user, True)

    @group.command(name="kick", description="ADMIN ONLY: Kicks the specified User (in the queue) from the current queue")
    async def remove(self, interaction: discord.Interaction, user: discord.User):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"), ephemeral=True)

        return await self.accessDict(interaction, user, False)

    @group.command(name="start", description="ADMIN ONLY: Immediately starts the game")
    async def start(self, interaction: discord.Interaction):
        if not self.verifyAdmin(interaction.user):
            return await interaction.response.send_message(view=EmbedView(myText="This command is reserved for administrators"), ephemeral=True)

        cur_channel = interaction.channel
        channel_id = cur_channel.id
        if not self.store.has_queue(channel_id):
            return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"), ephemeral=True)

        lock = self.store.get_lock(channel_id)
        async with lock:
            queue = self.store.get_queue(channel_id)
            if queue is None:
                return await interaction.response.send_message(view=EmbedView(myText="There is no queue in this channel"), ephemeral=True)

            if queue.phase != PHASE_OPEN:
                return await interaction.response.send_message(view=EmbedView(myText="This queue is already transitioning or started"), ephemeral=True)

            if len(queue.players) == 0:
                return await interaction.response.send_message(view=EmbedView(myText="There is no one in the queue"), ephemeral=True)

            queue.phase = PHASE_CLOSING
            queue.bump_revision()

            players = list(queue.players)
            queue_name = queue.name
            msg_id = queue.msg_id

        await interaction.response.defer(ephemeral=True)

        vc = None
        try:
            overwrite = {interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False)}
            for player in players:
                overwrite[player] = discord.PermissionOverwrite(view_channel=True, speak=True)

            vc = await interaction.guild.create_voice_channel(name=queue_name, overwrites=overwrite, category=interaction.channel.category)

            if msg_id is not None:
                try:
                    msg = await cur_channel.fetch_message(msg_id)
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

            invite = await vc.create_invite()

            dm_failures = 0
            for player in players:
                try:
                    dm = await player.create_dm()
                    await dm.send(content=invite.url)
                except (discord.Forbidden, discord.HTTPException):
                    dm_failures += 1

            async with lock:
                queue = self.store.get_queue(channel_id)
                if queue is None:
                    return await interaction.followup.send(view=EmbedView(myText="Queue was removed during startup"), ephemeral=True)

                queue.vc = vc
                queue.msg_id = None
                queue.start = True
                queue.phase = PHASE_STARTED
                queue.bump_revision()

            if dm_failures > 0:
                return await interaction.followup.send(
                    view=EmbedView(myText=f"Start success, but {dm_failures} player(s) could not be DM'd"),
                    ephemeral=True,
                )

            await interaction.followup.send(view=EmbedView(myText="Start success!"), ephemeral=True)
        except Exception:
            if vc is not None:
                try:
                    await vc.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

            async with lock:
                queue = self.store.get_queue(channel_id)
                if queue is not None:
                    queue.phase = PHASE_OPEN
                    queue.bump_revision()

            await interaction.followup.send(view=EmbedView(myText="Queue start failed and was rolled back"), ephemeral=True)

    @group.command(name="join", description="Join the queue in the current channel")
    async def join(self, interaction: discord.Interaction):
        return await self.accessDict(interaction, interaction.user, True)

    @group.command(name="leave", description="Leave the queue in the current channel")
    async def leave(self, interaction: discord.Interaction):
        return await self.accessDict(interaction, interaction.user, False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Queue(bot))
