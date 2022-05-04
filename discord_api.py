import discord
import asyncio
import configparser


discordapi = None


class DiscordClient:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read("config.ini")
        self.token = config["DISCORD"]["TOKEN"]
        intents = discord.Intents.all()
        self.client = discord.Client(intents=intents)
        self.client.on_ready = self.on_ready
        self.client.on_voice_state_update = self.on_voice_state_update
        self.guild: discord.Guild = None
        self.members = []
        self.move_queue = []
        self.move_vc_callback = None

    def get_member(self, discord_id):
        for m in self.members:
            if str(m.id) == str(discord_id):
                return m
        return None

    def get_online_members(self):
        members = []
        for m in self.members:
            m: discord.Member = m
            if (m.status in [discord.Status.online, discord.Status.idle] and
                    m.display_name != "werewolf_bot"):
                members.append(m)
        return members

    def get_infinite_tasks(self):
        return [self.client.start(self.token), self.move_queue_processer()]

    async def on_ready(self):
        assert(len(self.client.guilds) == 1)
        self.guild = self.client.guilds[0]
        await self.update_member()
        print("Discord BOT ready")

    async def update_member(self):
        members = await self.guild.fetch_members().flatten()
        self.members = []
        for m in members:
            mm = self.client.guilds[0].get_member(m.id)
            self.members.append(mm)

    async def move_queue_processer(self):
        print("move_queue check start")
        while True:
            try:
                if len(self.move_queue) > 0:
                    d = self.move_queue.pop()
                    m: discord.Member = self.get_member(d["discord_id"])
                    vc = self.get_vc(d["room_key"])
                    await m.move_to(vc)
                else:
                    await asyncio.sleep(0.2)
            except Exception as e:
                print("move_queue processer error ", e)

    def move_member(self, discord_id, room_key):
        self.move_queue.append(
            {
                "discord_id": discord_id,
                "room_key": room_key
            }
        )

    async def on_voice_state_update(self, member, before, after):
        # 誰かがVCを移動すると呼ばれる
        await self.update_member()
        if self.move_vc_callback is not None:
            dic = {}
            for m in self.members:
                m: discord.Member = m
                v = None
                if m.voice is not None:
                    if m.voice.channel is not None:
                        v = m.voice.channel.name
                dic[str(m.id)] = v
            self.move_vc_callback(dic)

    def get_vc(self, key):
        config = configparser.ConfigParser()
        config.read("config.ini")
        name = ""
        if key == "conference":
            name = config["DISCORD"]["CONFERENCE_ROOM"]
        if key == "werewolf":
            name = config["DISCORD"]["WEREWOLF_ROOM"]
        if key == "fox":
            name = config["DISCORD"]["FOX_ROOM"]
        if key == "mason":
            name = config["DISCORD"]["MASON_ROOM"]
        if key == "ghost":
            name = config["DISCORD"]["GHOST_ROOM"]
        if "personal" in key:
            name = config["DISCORD"]["PERSONAL_ROOM"] + key[8:]
        if name != "":
            target_id = None
            for vc in self.guild.voice_channels:
                print(vc, vc.name, vc.id)
                if vc.name == name:
                    target_id = vc.id
            return self.guild.get_channel(target_id)
        return None
