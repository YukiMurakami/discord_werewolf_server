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
        self.game = Game(self.game_callback)

    def start(self):
        print("backend start")

        self.discordapi = DiscordClient()
        self.network = Network(
            close_callback=self.network_close_callback,
            disconnected_callback=self.network_disconnected_callback,
            received_callback=self.network_received_callback
        )

        network_task = self.network.get_infinite_task()
        discord_task = self.discordapi.get_infinite_task()

        tasks = asyncio.gather(
            network_task, discord_task
        )
        asyncio.get_event_loop().run_until_complete(tasks)
        print("finish")

    def network_close_callback(a):
        print(a)

    def network_disconnected_callback(self, discord_id):
        print("切断", discord_id)

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
                self.send_game_status_all()
            else:
                self.game.add_player(
                    discord_id,
                    self.discordapi.get_member(discord_id).display_name
                )
                self.send_game_status_all()
        elif data["message"] == "logout":
            self.game.remove_player(discord_id)
            self.send_game_status_all()
        elif data["message"] in [
                "+villager", "-villager", "+werewolf", "-werewolf",
                "+seer", "-seer", "first_seer_no", "first_seer_free",
                "first_seer_random_white", "bodyguard_rule_no",
                "bodyguard_rule_yes", "+medium", "-medium"]:
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
        self.send_game_status_all()

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
            if str(m.id) not in already_use_ids:
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
