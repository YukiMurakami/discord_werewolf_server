"""
discord_apiとnetwork、Gameを使用して
ゲーム全体の通信サーバーの役割をするモジュール
"""

from discord_api import DiscordClient
import discord
from network import Network
import asyncio
from game import Game
from util import Status


class Manager:
    def __init__(self):
        self.discordapi = None
        self.network = None
        self.game = Game(self.game_callback, self.move_vc)

    def start(self):
        print("backend start")

        self.discordapi = DiscordClient()
        self.discordapi.move_vc_callback = self.game.move_vc_callback
        self.network = Network(
            close_callback=self.network_close_callback,
            disconnected_callback=self.network_disconnected_callback,
            received_callback=self.network_received_callback
        )

        network_task = self.network.get_infinite_task()
        discord_tasks = self.discordapi.get_infinite_tasks()

        tasks = asyncio.gather(
            network_task, discord_tasks[0], discord_tasks[1]
        )
        asyncio.get_event_loop().run_until_complete(tasks)
        print("finish")

    def network_close_callback(a):
        print(a)

    def update_user_connect_status(self):
        # ゲームの各ユーザの接続状況をアップデートする
        for p in self.game.players:
            d_id = p.discord_id
            if d_id in list(self.network.users.values()):
                p.disconnect = False
                print(p.name, p.disconnect)
            else:
                p.disconnect = True
                print(p.name, p.disconnect)

    def network_disconnected_callback(self, discord_id):
        print("切断", discord_id)
        self.update_user_connect_status()
        self.send_game_status_all()

    def network_received_callback(self, discord_id, conn, data):
        print("received", discord_id, conn, data)
        if data["message"] == "get_free_account":
            accounts = self.get_free_account()
            self.network.send_to_conn(
                conn,
                {"message": "free_account", "accounts": accounts}
            )
        elif data["message"] == "login":
            # ゲームが進行中の場合は新規参加は許可しない
            if self.game.status != Status.SETTING:
                # ただしすでに参加済みの場合は復帰処理
                self.update_user_connect_status()
                self.send_game_status_all()
            else:
                m = self.discordapi.get_member(discord_id)
                avator_url = (str(m.avatar_url)).replace(
                    ".webp?size=1024", "")
                voice = "None"
                if m.voice is not None and m.voice.channel is not None:
                    voice = m.voice.channel.name
                self.game.add_player(
                    discord_id,
                    m.display_name,
                    avator_url,
                    voice
                )
                self.update_user_connect_status()
                self.send_game_status_all()
        elif ("start_speak:" in data["message"] or
                "end_speak:" in data["message"]):
            d_id = data["message"].split(":")[1]
            mes = data["message"].split(":")[0]
            p = self.game.get_player(d_id)
            if p is not None:
                p.speaking = (mes == "start_speak")
                self.game.callback()
        elif data["message"] == "logout":
            self.game.remove_player(discord_id)
            self.send_game_status_all()
        elif data["message"] in [
                "+villager", "-villager", "+werewolf", "-werewolf",
                "+seer", "-seer", "first_seer_no", "first_seer_free",
                "first_seer_random_white", "bodyguard_rule_no",
                "bodyguard_rule_yes", "+medium", "-medium",
                "+bodyguard", "-bodyguard",
                "+madman", "-madman",
                "+mason", "-mason", "+cultist", "-cultist",
                "+fox", "-fox"]:
            self.game.change_rule(data["message"])
            self.send_game_status_all()
        elif data["message"] == "game_start":
            if self.game.can_start():
                self.game.start()
        else:
            # のこりはアクション
            self.game.input_action(data["message"])

    def game_callback(self):
        """
        ゲームの状況が変化した際に呼ばれる
        """
        print("callback", self.game.status)
        self.update_user_connect_status()
        self.send_game_status_all()

    def move_vc(self, data):
        """
        data: discord_idとroom_keyのdict
        """
        for k, v in data.items():
            self.discordapi.move_member(
                k, v
            )

    # 入室済みプレイヤー全員にゲーム情報を送る
    def send_game_status_all(self):
        already_use_ids = self.network.get_online_ids()
        for p in self.game.players:
            if p.discord_id in already_use_ids:
                self.network.send_to_discord_id(
                    p.discord_id,
                    {"message": "game_status",
                        "status": self.game.get_status(p.discord_id)}
                )

    # 以降各処理の関数
    def get_free_account(self):
        members = self.discordapi.get_online_members()
        already_use_ids = self.network.get_online_ids()
        print("already", already_use_ids)
        result = []
        for m in members:
            m: discord.Member = m
            if (str(m.id) not in already_use_ids and m.bot is False and
                    m.display_name not in ["霊界の耳", "霊界の口"]):
                avator_url = (str(m.avatar_url)).replace(
                    ".webp?size=1024", "")
                name = m.display_name
                discriminator = m.discriminator
                result.append({
                    "name": name,
                    "discriminator": discriminator,
                    "avator_url": avator_url,
                    "discord_id": str(m.id)
                })
        return result


if __name__ == "__main__":
    manager = Manager()
    manager.start()
