import discord
import asyncio
import hashlib
from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest
import threading
import traceback
from flask_cors import CORS
import configparser
from datetime import datetime, timedelta
import time


discordapi = None
restapi = Flask(__name__)
cors = CORS(restapi)
restapi.config['JSON_AS_ASCII'] = False


class DiscordClient:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read("config.ini")
        self.token = config["DISCORD"]["TOKEN"]
        intents = discord.Intents.all()
        self.client = discord.Client(intents=intents)
        self.client.on_ready = self.on_ready
        self.members = []

    def get_member(self, user_id):
        for m in self.members:
            if str(m.id) == str(user_id):
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

    def get_infinite_task(self):
        return self.client.start(self.token)

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
