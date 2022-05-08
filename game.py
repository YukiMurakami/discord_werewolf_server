from configparser import ConfigParser
from util import Status, FirstSeerRule, BodyguardRule
from role import (
    Role,
    eng2token,
    token2role,
    TeamCount, Team
)
from random import shuffle
import threading
import time


class Player:
    def __init__(self):
        self.discord_id: str = ""
        self.avator_url: str = ""
        self.name: str = ""
        self.role: Role = None
        self.live: bool = True
        self.voted_count: int = 0
        self.already_vote: bool = False
        self.voice: str = None
        self.speaking: bool = False
        self.disconnect: bool = False
        self.skip: bool = False

    def reset(self):
        self.role = None
        self.live = True
        self.voted_count = 0
        self.already_vote = False
        self.skip = False

    def update_vote(self, game):
        self.voted_count = 0
        self.already_vote = False
        self.skip = False
        for action in game.decide_actions:
            div = action.split(":")
            if div[0] == "vote":
                if div[2] == self.discord_id:
                    self.voted_count += 1
                if div[1] == self.discord_id:
                    self.already_vote = True
            if div[0] == "skip" and div[1] == self.discord_id:
                self.skip = True

    def get_status(self, open_flag: bool, from_discord_id: str, game):
        """
        プレイヤー情報
        open_flag: 神視点かどうか
        from_discord_id: どのプレイヤーから見た情報か
        """
        role = "?"
        if self.role is not None:
            role = self.role.get_name()
            if open_flag is False:
                if self.discord_id == from_discord_id:
                    # 自分ならOpen
                    pass
                else:
                    from_role = game.get_player(from_discord_id).role
                    # 味方ならOpen
                    if self.role.get_name() in from_role.know_names:
                        pass
                    else:
                        role = "?"
        actions = []
        # 自分かつ生存ならアクション追加
        if self.discord_id == from_discord_id:
            if self.role is not None and self.live:
                actions = self.role.get_actions(game, self.discord_id)
            elif game.status == Status.SETTING:
                # 役職配布前なのでここで個別対応
                # 先頭プレイヤーはキック可能
                now_index = -1
                for i, p in enumerate(game.players):
                    if p.discord_id == self.discord_id:
                        now_index = i
                        break
                if now_index == 0:
                    for i, p in enumerate(game.players):
                        if i != 0:
                            actions.append("kick:%s" % p.discord_id)
        # 投票数集計
        self.update_vote(game)
        return {
            "name": self.name,
            "role": role,
            "live": self.live,
            "discord_id": self.discord_id,
            "actions": actions,
            "voted_count": self.voted_count,
            "already_vote": self.already_vote,
            "avator_url": self.avator_url,
            "voice": self.voice,
            "speaking": self.speaking,
            "disconnect": self.disconnect,
            "skip": self.skip,
        }


class Game:
    def __init__(self, callback, move_vc):
        self.callback = callback
        self.players = []
        self.minute = 0
        self.second = 0
        self.timer_flag = ""
        self.move_vc_func = move_vc
        self.config = ConfigParser()
        self.config.read("config.ini")
        self.init_rule()
        self.reset()
        th = threading.Thread(target=self.timer)
        th.setDaemon(True)
        th.start()

    def init_rule(self):
        self.rule = {
            "roles": {"村": 2, "狼": 1},
            "first_seer": FirstSeerRule.FREE,
            "bodyguard": BodyguardRule.CONSECUTIVE_GUARD,
        }

    def reset(self):
        for p in self.players:
            p.reset()
        self.status = Status.SETTING
        self.decide_actions = []
        self.minute = 0
        self.second = 0
        self.action_results = []
        self.day = 0
        self.vote_candidates = []
        self.excuted_id = None
        self.last_guards = []
        self.timer_flag = ""

        last_rule = {}
        for key in ["roles", "first_seer", "bodyguard"]:
            last_rule[key] = self.rule[key]
        self.rule = {
            "night_seconds": int(self.config["GAME"]["NIGHT_SECONDS"]),
            "day_seconds": int(self.config["GAME"]["DAY_MAX_SECONDS"]),
            "min_day_seconds": int(self.config["GAME"]["DAY_MIN_SECONDS"]),
            "day_minus_seconds": int(self.config["GAME"]["DAY_DIFF_SECONDS"])
        }
        for key in ["roles", "first_seer", "bodyguard"]:
            self.rule[key] = last_rule[key]

    def timer(self):
        while True:
            time.sleep(1)
            print(self.minute, self.second, self.timer_flag, self.status)
            if self.timer_flag == "":
                continue
            self.second -= 1
            if self.second < 0:
                self.minute -= 1
                self.second = 59
            if self.minute <= 0 and self.second <= 0:
                self.minute = 0
                self.second = 0
                self.timer_end_callback(self.timer_flag)
            else:
                self.callback()

    def timer_end_callback(self, timer_flag):
        self.timer_flag = ""
        print("timer end", timer_flag)
        if timer_flag == "role_checking" and self.status == Status.ROLE_CHECK:
            self.start_night()
        elif timer_flag == "night" and self.status == Status.NIGHT:
            rest_actions = self.get_live_player_rest_actions()
            if len(rest_actions) <= 0:
                self.start_morning()
            else:
                self.set_timer("night", 0, 1)
        elif timer_flag == "morning" and self.status == Status.MORNING:
            # 勝利判定後に昼開始
            if self.get_winner_team() is None:
                self.start_afternoon()
            else:
                print("FINISH", self.get_winner_team())
                self.start_result()
        elif timer_flag == "afternoon" and self.status == Status.AFTERNOON:
            self.start_vote()

    def move_vc_callback(self, dic):
        # vc移動で呼ばれる
        print(dic)
        for p in self.players:
            if p.discord_id in dic:
                p.voice = dic[p.discord_id]
        print([n.get_status(True, "", self) for n in self.players])
        # 玄関にいるプレイヤーがいれば移動させる
        exist_firstroom = False
        firstroom_name = self.config["DISCORD"]["FIRST_ROOM"]
        for p in self.players:
            if p.voice == firstroom_name:
                exist_firstroom = True
        if exist_firstroom:
            self.move_members()
        self.callback()

    def get_live_player_rest_actions(self):
        rest_actions = []
        for p in self.players:
            if p.live:
                rest_actions += p.role.get_actions(self, p.discord_id)
        return rest_actions

    def move_members(self):
        dic = {}
        if self.status in [Status.RESULT, Status.SETTING]:
            # 全員会議室
            for i in range(len(self.players)):
                discord_id = self.players[i].discord_id
                dic[discord_id] = "conference"
        if self.status in [Status.ROLE_CHECK, Status.MORNING]:
            # 個別部屋へ
            for i in range(len(self.players)):
                discord_id = self.players[i].discord_id
                live = self.players[i].live
                if live:
                    dic[discord_id] = "personal%d" % i
                else:
                    dic[discord_id] = "ghost"
        if self.status == Status.NIGHT:
            # 夜行動へ
            for i in range(len(self.players)):
                discord_id = self.players[i].discord_id
                live = self.players[i].live
                token = self.players[i].role.get_token()
                if live:
                    if eng2token("werewolf") == token:
                        dic[discord_id] = "werewolf"
                    elif eng2token("mason") == token:
                        dic[discord_id] = "mason"
                    elif eng2token("fox") == token:
                        dic[discord_id] = "fox"
                    else:
                        dic[discord_id] = "personal%d" % i
                else:
                    dic[discord_id] = "ghost"
        if self.status in [Status.AFTERNOON, Status.EXCUTION, Status.VOTE]:
            # 昼行動へ
            for i in range(len(self.players)):
                discord_id = self.players[i].discord_id
                live = self.players[i].live
                if live:
                    dic[discord_id] = "conference"
                else:
                    dic[discord_id] = "ghost"

        self.move_vc_func(dic)

    def start_night(self):
        self.action_results = []
        self.decide_actions = []
        self.status = Status.NIGHT
        self.move_members()
        self.set_timer(
            "night",
            self.rule["night_seconds"] // 60,
            self.rule["night_seconds"] % 60
        )

    def start_morning(self):
        self.day += 1
        self.status = Status.MORNING
        self.move_members()
        self.set_timer("morning", 0, 10)
        # 犠牲者セット
        victim_ids = []
        # 噛まれた人が死ぬ
        for action in self.decide_actions:
            div = action.split(":")
            if div[0] == "attack":
                victim_token = self.get_player(div[2]).role.get_token()
                if victim_token not in [eng2token("fox")]:
                    # 妖狐以外が噛める
                    victim_ids.append(div[2])
        victim_ids = list(set(victim_ids))
        # 守られた人は死なない
        for action in self.decide_actions:
            div = action.split(":")
            if div[0] == "bodyguard":
                src_id = div[1]
                dist_id = div[2]
                day = self.day - 1
                self.last_guards.append("%s:%s:%d" % (
                    src_id, dist_id, day
                ))
                if dist_id in victim_ids:
                    victim_ids.remove(dist_id)
        # 占われた妖狐は死ぬ
        for action in self.decide_actions:
            div = action.split(":")
            if div[0] == "seer":
                src_id = div[1]
                dist_id = div[2]
                dist_token = self.get_player(dist_id).role.get_token()
                if dist_token in [eng2token("fox")]:
                    if dist_id not in victim_ids:
                        victim_ids.append(dist_id)
        victim_ids = list(set(victim_ids))
        shuffle(victim_ids)
        for victim_id in victim_ids:
            self.action_results.append("victim:%s" % victim_id)
            self.get_player(victim_id).live = False
        self.callback()

    def start_afternoon(self):
        self.decide_actions = []
        seconds = self.rule["day_seconds"]
        seconds -= self.rule["day_minus_seconds"] * (self.day - 1)
        if seconds < self.rule["min_day_seconds"]:
            seconds = self.rule["min_day_seconds"]
        self.status = Status.AFTERNOON
        self.move_members()
        self.set_timer("afternoon", seconds // 60, seconds % 60)
        self.callback()

    def start_vote(self):
        self.decide_actions = []
        if self.status != Status.VOTE:
            # 初回は全員が投票対象
            self.vote_candidates = [
                p.discord_id for p in self.players if p.live]
        self.status = Status.VOTE
        self.move_members()
        self.callback()

    def start_excution(self):
        # 集計
        max_point = -1
        max_ids = []
        for p in self.players:
            p: Player = p
            p.update_vote(self)
            if max_point <= p.voted_count:
                if max_point == p.voted_count:
                    max_ids.append(p.discord_id)
                if max_point < p.voted_count:
                    max_point = p.voted_count
                    max_ids = [p.discord_id]
        excuted_id = None
        if len(max_ids) >= 2:
            # 決戦
            latest_candidates = sorted(self.vote_candidates)
            now_candidates = sorted(max_ids)
            if latest_candidates == now_candidates:
                # 投票しても結果が変わらない -> ランダム処刑
                shuffle(now_candidates)
                excuted_id = now_candidates[0]
            else:
                # 決選投票
                self.vote_candidates = max_ids
                self.start_vote()
                return
        else:
            assert len(max_ids) == 1
            excuted_id = max_ids[0]
        self.excuted_id = excuted_id
        self.decide_actions = []
        self.status = Status.EXCUTION
        self.move_members()
        self.callback()

    def start_result(self):
        """
        結果表示
        """
        self.status = Status.RESULT
        self.move_members()
        self.callback()

    def start_role_check(self):
        self.status = Status.ROLE_CHECK
        self.move_members()
        self.callback()
        self.set_timer("role_checking", 0, 10)

    def set_timer(self, timer_flag, minute, second):
        self.timer_flag = timer_flag
        self.minute = minute
        self.second = second

    def get_winner_team(self):
        werewolf_count = 0
        human_count = 0
        fox_count = 0
        if self.status == Status.SETTING:
            for k, v in self.rule["roles"].items():
                if token2role(k)().get_team_count() == TeamCount.WEREWOLF:
                    werewolf_count += v
                if token2role(k)().get_team_count() == TeamCount.HUMAN:
                    human_count += v
        else:
            for p in self.players:
                if p.live:
                    if p.role.get_team_count() == TeamCount.WEREWOLF:
                        werewolf_count += 1
                    if p.role.get_team_count() == TeamCount.HUMAN:
                        human_count += 1
                    if p.role.get_team() == Team.FOX:
                        fox_count += 1
        # 人狼がいなければ村かち
        if werewolf_count <= 0 and human_count <= 0:
            return None
        if werewolf_count <= 0:
            if fox_count > 0:
                return Team.FOX
            return Team.VILLAGER
        if werewolf_count >= human_count:
            if fox_count > 0:
                return Team.FOX
            return Team.WEREWOLF
        return None

    def can_start(self):
        """
        役職設定がゲーム終了条件を満たしていない
        役職設定がプレイ人数と合っている
        の両方を満たした時開始可能
        """
        winner_team = self.get_winner_team()
        if winner_team is not None:
            return False
        role_sum = 0
        for k, v in self.rule["roles"].items():
            role_sum += v
        if role_sum != len(self.players):
            return False
        return True

    def start(self):
        if self.status != Status.SETTING:
            return
        self.set_roles()
        self.start_role_check()

    def set_roles(self):
        """
        役職配布
        """
        roles = []
        for k, v in self.rule["roles"].items():
            for _ in range(v):
                roles.append(token2role(k)())
        shuffle(roles)
        for i in range(len(self.players)):
            self.players[i].role = roles[i]

    def add_player(self, discord_id, name, avator_url, voice):
        if self.get_player(discord_id) is not None:
            return
        p = Player()
        p.discord_id = discord_id
        p.avator_url = avator_url
        p.name = name
        p.voice = voice
        self.players.append(p)
        self.move_members()

    def remove_player(self, discord_id):
        if self.get_player(discord_id) is None:
            return
        for p in self.players:
            if p.discord_id == discord_id:
                self.players.remove(p)
                return

    def get_player(self, discord_id):
        for p in self.players:
            if p.discord_id == discord_id:
                return p
        return None

    def input_action(self, action):
        if action not in self.decide_actions:
            self.decide_actions.append(action)
            self.callback()

        # アクション後に確認が必要なケースの対応
        # 投票完了
        if self.status == Status.VOTE:
            rest_actions = self.get_live_player_rest_actions()
            if len(rest_actions) <= 0:
                self.start_excution()
        # スキップ完了
        if self.status == Status.AFTERNOON:
            rest_actions = self.get_live_player_rest_actions()
            if len(rest_actions) <= 0:
                self.minute = 0
                self.second = 5
        # 遺言完了
        if self.status == Status.EXCUTION:
            rest_actions = self.get_live_player_rest_actions()
            if len(rest_actions) <= 0:
                # 処刑者を死亡処理して勝利判定後に夜開始
                for p in self.players:
                    if p.discord_id == self.excuted_id:
                        p.live = False
                if self.get_winner_team() is None:
                    self.start_night()
                else:
                    print("FINISH", self.get_winner_team())
                    self.start_result()
        # 結果完了
        if self.status == Status.RESULT:
            if "result:" in action:
                self.reset()
                self.move_members()
                self.callback()

    def change_rule(self, message: str):
        """
        特定文字列を受け取り、ルールの変更をする
        """
        if len(message) > 0:
            if message[0] in ["+", "-"]:
                role_str = message[1:]
                token = eng2token(role_str)
                if message[0] == "-":
                    if token in self.rule["roles"]:
                        if self.rule["roles"][token] == 1:
                            del self.rule["roles"][token]
                        else:
                            self.rule["roles"][token] -= 1
                else:
                    if token in self.rule["roles"]:
                        self.rule["roles"][token] += 1
                    else:
                        self.rule["roles"][token] = 1
            if "first_seer_" in message:
                if message == "first_seer_no":
                    self.rule["first_seer"] = FirstSeerRule.NO
                if message == "first_seer_free":
                    self.rule["first_seer"] = FirstSeerRule.FREE
                if message == "first_seer_random_white":
                    self.rule["first_seer"] = FirstSeerRule.RANDOM_WHITE
            if "bodyguard_rule_" in message:
                if message == "bodyguard_rule_no":
                    self.rule[
                        "bodyguard"] = BodyguardRule.CANNOT_CONSECUTIVE_GUARD
                if message == "bodyguard_rule_yes":
                    self.rule["bodyguard"] = BodyguardRule.CONSECUTIVE_GUARD

    def get_status(self, from_discord_id):
        open_flag = False
        if self.status == Status.RESULT:
            open_flag = True
        action_results = list(self.action_results)
        # 個人分を追加
        for p in self.players:
            if p.discord_id == from_discord_id:
                if p.role is not None:
                    action_results += p.role.get_action_results(
                        self, from_discord_id
                    )
        result = self.get_winner_team()
        if result is not None:
            result = result.name
        return {
            "status": self.status.name,
            "players": [
                n.get_status(
                    open_flag, from_discord_id, self) for n in self.players
            ],
            "rule": {
                "roles": self.rule["roles"],
                "first_seer": self.rule["first_seer"].name,
                "bodyguard": self.rule["bodyguard"].name
            },
            "minute": self.minute,
            "second": self.second,
            "day": self.day,
            "action_results": action_results,
            "excution": self.excuted_id,
            "result": result
        }
