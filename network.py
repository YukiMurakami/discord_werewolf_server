"""
ゲームのソケット通信を担うモジュール
"""

from configparser import ConfigParser
import websockets
import json
import traceback
import asyncio
import ssl


class Network:
    def __init__(self, close_callback, disconnected_callback,
                 received_callback):
        self.close_callback = close_callback  # サーバ側がダウンした時に呼ばれる
        self.disconnected_callback = disconnected_callback  # ユーザが切断した時に呼ばれる
        self.received_callback = received_callback  # ユーザから受信した時に呼ばれる

        self.users = {}  # connをキーにuserIdを引くテーブル
        self.socket = None
        self.message_queue = []
        self.send_ids = {}

        config = ConfigParser()
        config.read("config.ini")
        self.host = config["API"]["HOST"]
        self.port = config["API"]["PORT"]
        self.sslfile = config["API"]["SSL_FILE"]

        self.observe_id = 0

    def get_infinite_task(self):
        if self.sslfile != "":
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(self.sslfile)
            self.socket = websockets.serve(
                self.get_new_client, self.host, self.port, ssl=ssl_context)
            print("secure mode socket")
        else:
            self.socket = websockets.serve(
                self.get_new_client, self.host, self.port)
            print("no secure mode socket")
        asyncio.get_event_loop().run_until_complete(self.socket)
        return self.send_coroutine()

    async def get_new_client(self, websocket, path):
        while True:
            try:
                data = await websocket.recv()
                print("receive:", data, type(data))

                jsondata = {}
                try:
                    jsondata = json.loads(data)
                    print("received", jsondata)
                except Exception as e:
                    print(e)
                    print("no json data", data)
                self.received(websocket, jsondata)
            except Exception as e:
                print(e)
                print(traceback.format_exc())
                print("disconnect")
                self.disconnected(websocket)
                break

    def get_online_ids(self):
        return list(self.users.values())

    def received(self, conn, data):
        """
        すでにDiscordと紐づいている場合はdiscord_idを返す
        紐づいてなければNoneで返す
        """
        if "discord_id" not in data:
            self.received_callback(None, conn, data)
        else:
            if data["message"] == "logout":
                discord_id = data["discord_id"]
                self.disconnected(conn)
                self.received_callback(discord_id, conn, data)
                asyncio.get_event_loop().run_until_complete(conn.close())
            else:
                if data["message"] == "login":
                    discord_id = data["discord_id"]
                    if discord_id in self.users.values():
                        # ２重ログインは拒否
                        return
                    self.users[conn] = discord_id
                elif data["message"] == "observe":
                    self.users[conn] = "observe_%d" % self.observe_id
                    self.observe_id += 1
                discord_id = self.users[conn]
                self.received_callback(discord_id, conn, data)

    async def send_coroutine(self):
        print("socket ready", self.host, self.port)
        while True:
            try:
                if len(self.message_queue) > 0:
                    d = self.message_queue.pop()
                    conn = None
                    if "conn" in d:
                        conn = d["conn"]
                    else:
                        for k, v in self.users.items():
                            if v == d["discord_id"]:
                                conn = k
                    if conn is not None:
                        sendMes = json.dumps(d["data"])
                        await conn.send(sendMes)
                else:
                    await asyncio.sleep(0.2)
            except Exception as e:
                print("send_coroutine error ", e)
                print(traceback.format_exc())
                break

    def send_to_conn(self, conn, data):
        self.message_queue.append({
            "data": data,
            "conn": conn
        })

    def send_to_discord_id(self, discord_id, data):
        send_id = 0
        if discord_id in self.send_ids:
            self.send_ids[discord_id] += 1
            send_id = self.send_ids[discord_id]
        else:
            self.send_ids[discord_id] = 0
        data["send_id"] = send_id
        self.message_queue.append({
            "discord_id": discord_id,
            "data": data
        })

    def disconnected(self, conn):
        print("116 きり")
        userId = ""
        if conn in self.users:
            userId = self.users[conn]
            # 切断されたら、ユーザ辞書更新が必要
            del(self.users[conn])
        self.disconnected_callback(userId)
