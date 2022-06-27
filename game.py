from configparser import ConfigParser
from util import Status, FirstSeerRule, BodyguardRule
from role import (
    Role,
    eng2token,
    token2role,
    token2eng,
    TeamCount, Team
)
from random import shuffle
import threading
import time
import pickle
import datetime


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
        # voiceは移動先のVC名が入る
        self.to_voice: str = None
        # to_voiceに移動先を設定すると定期実行でserverが移動させる
        self.speaking: bool = False
        self.disconnect: bool = False
        self.skip: bool = False
        self.co_list :list = []
        self.hand: int = None
        self.first_victim: bool = False
        self.reveal_role: bool = False

    def reset(self):
        self.role = None
        self.live = True
        self.voted_count = 0
        self.already_vote = False
        self.skip = False
        self.hand = None
        self.co_list = []
        self.reveal_role = False

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
            if open_flag is False and self.reveal_role is False:
                if self.discord_id == from_discord_id:
                    # 自分ならOpen
                    pass
                else:
                    if "observe_" in from_discord_id or from_discord_id == "":
                        role = "?"
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
            if self.role is not None and self.live and self.first_victim is False:
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
                        if i != 0 and p.first_victim is False:
                            actions.append("kick:%s" % p.discord_id)
                # 手を挙げる
                if self.hand is None:
                    actions.append("hand_raise:%s" % self.discord_id)
                else:
                    actions.append("hand_down:%s" % self.discord_id)
        # 投票数集計
        self.update_vote(game)

        # 決選投票は全員の投票が完了するまでは0にする
        vote_count = self.voted_count
        if game.status == Status.VOTE and game.vote_count > 0:
            vote_count = 0
        
        hands = sorted([n.hand for n in game.players if n.hand is not None])
        hand = self.hand
        if self.hand is not None:
            hand = hands.index(hand) + 1
        return {
            "name": self.name,
            "role": role,
            "live": self.live,
            "discord_id": self.discord_id,
            "actions": actions,
            "voted_count": vote_count,
            "already_vote": self.already_vote,
            "avator_url": self.avator_url,
            "voice": self.voice,
            "speaking": self.speaking,
            "disconnect": self.disconnect,
            "skip": self.skip,
            "co_list": self.co_list,
            "hand": hand,
        }


class GameData:
    def __init__(self):
        self.players = []
        self.rule = {}
        self.minute = 0
        self.second = 0
        self.timer_flag = ""
        self.status = Status.SETTING
        self.decide_actions = []
        self.action_results = []
        self.logs = {}
        self.day = 0
        self.vote_count = 0
        self.vote_candidates = []
        self.excuted_id = None
        self.detective_id = None
        self.now_detective_answer = []
        self.win_detective_id = None
        self.companions = []
        self.last_guards = []
        self.hand_count = 0
        self.timer_stop = False
        self.waitmove_timer_stop = False


class Game:
    def __init__(self, callback):
        self.callback = callback
        self.players = []
        self.minute = 0
        self.second = 0
        self.timer_stop = False
        self.waitmove_timer_stop = False
        self.timer_flag = ""
        self.all_moved_flag = True
        self.config = ConfigParser()
        self.config.read("config.ini")
        self.first_victim_id = "first_victim"
        self.first_victim_name = self.config["GAME"]["FIRST_VICTIM_NAME"]
        self.init_rule()
        self.reset()
        self.first_hand_discord_id = None
        th = threading.Thread(target=self.timer)
        th.setDaemon(True)
        th.start()

    def save(self, filename):
        gamedata = GameData()
        gamedata.players = self.players
        gamedata.rule = self.rule
        gamedata.minute = self.minute
        gamedata.second = self.second
        gamedata.timer_flag = self.timer_flag
        gamedata.status = self.status
        gamedata.decide_actions = self.decide_actions
        gamedata.action_results = self.action_results
        gamedata.logs = self.logs
        gamedata.day = self.day
        gamedata.vote_count = self.vote_count
        gamedata.vote_candidates = self.vote_candidates
        gamedata.excuted_id = self.excuted_id
        gamedata.detective_id = self.detective_id
        gamedata.now_detective_answer = self.now_detective_answer
        gamedata.win_detective_id = self.win_detective_id
        gamedata.last_guards = self.last_guards
        gamedata.hand_count = self.hand_count
        gamedata.timer_stop = self.timer_stop
        gamedata.companions = self.companions
        gamedata.waitmove_timer_stop = self.waitmove_timer_stop
        with open(filename, "wb") as f:
            pickle.dump(gamedata, f)

    def load(self, filename=""):
        if filename == "":
            filename = "game.pickle"
        with open(filename, "rb") as f:
            gamedata = pickle.load(f)
            self.players = gamedata.players
            self.rule = gamedata.rule
            self.minute = gamedata.minute
            self.second = gamedata.second
            self.timer_flag = gamedata.timer_flag
            self.status = gamedata.status
            self.decide_actions = gamedata.decide_actions
            self.action_results = gamedata.action_results
            self.logs = gamedata.logs
            self.day = gamedata.day
            self.vote_count = gamedata.vote_count
            self.vote_candidates = gamedata.vote_candidates
            self.excuted_id = gamedata.excuted_id
            self.detective_id = gamedata.detective_id
            self.now_detective_answer = gamedata.now_detective_answer
            self.win_detective_id = gamedata.win_detective_id
            self.last_guards = gamedata.last_guards
            self.hand_count = gamedata.hand_count
            self.timer_stop = gamedata.timer_stop
            self.companions = gamedata.companions
            self.waitmove_timer_stop = gamedata.waitmove_timer_stop

    def init_rule(self):
        self.rule = {
            "roles": {"狼": 3, "狂": 1, "占": 1, "霊": 1, "狩": 1, "共": 2, "村": 6, "狐": 1},
            "first_seer": FirstSeerRule.FREE,
            "bodyguard": BodyguardRule.CONSECUTIVE_GUARD,
            "first_victim": False,
        }

    def reset(self):
        for p in self.players:
            p.reset()
        self.status = Status.SETTING
        self.decide_actions = []
        self.minute = 0
        self.second = 0
        self.action_results = []
        self.logs = {}
        self.day = 0
        self.vote_count = 0
        self.vote_candidates = []
        self.excuted_id = None
        self.detective_id = None
        self.now_detective_answer = []
        self.win_detective_id = None
        self.companions = []
        self.last_guards = []
        self.timer_flag = ""
        self.hand_count = 0
        self.timer_stop = False
        self.waitmove_timer_stop = False

        last_rule = {}
        for key in ["roles", "first_seer", "bodyguard", "first_victim"]:
            last_rule[key] = self.rule[key]
        self.rule = {
            "night_seconds": int(self.config["GAME"]["NIGHT_SECONDS"]),
            "day_seconds": int(self.config["GAME"]["DAY_MAX_SECONDS"]),
            "min_day_seconds": int(self.config["GAME"]["DAY_MIN_SECONDS"]),
            "day_minus_seconds": int(self.config["GAME"]["DAY_DIFF_SECONDS"]),
            "morning_seconds": int(self.config["GAME"]["MORNING_SECONDS"]),
            "vote_seconds": int(self.config["GAME"]["VOTE_SECONDS"]),
            "will_seconds": int(self.config["GAME"]["WILL_SECONDS"])
        }
        for key in ["roles", "first_seer", "bodyguard", "first_victim"]:
            self.rule[key] = last_rule[key]

    def timer(self):
        while True:
            time.sleep(1)
            print(self.minute, self.second, self.timer_flag, self.status, self.timer_stop, self.waitmove_timer_stop)
            self.save("game.pickle")
            if self.timer_flag == "":
                continue
            if self.status != Status.AFTERNOON:
                self.timer_stop = False
            if self.timer_stop is False and self.waitmove_timer_stop is False:
                self.second -= 1
            if self.second < 0:
                self.minute -= 1
                self.second = 59
            if self.minute < 0:
                self.minute = 0
                self.second = 0
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
            # 名探偵推理ショーがあればそちらを優先
            detective_show = None
            for action in self.decide_actions:
                if "detective_show:" in action:
                    div = action.split(":")
                    detective_id = div[1]
                    detective_p = self.get_player(detective_id)
                    if detective_p.live:
                        detective_show = detective_id
                        break
            if detective_show is None:
                self.detective_id = None
                self.now_detective_answer = []
                self.start_vote()
            else:
                self.detective_id = detective_show
                self.start_detective_show()
        elif timer_flag == "detective_ready" and self.status == Status.DETECTIVE_READY:
            # 名探偵の推理ショーの回答まちが終了
            # 答え合わせ
            check = True
            for i in range(len(self.players)):
                predict_role = self.now_detective_answer[i]
                ans_role = token2eng(self.players[i].role.get_token())
                if predict_role != ans_role:
                    check = False
                    break
            if check:
                # 名探偵勝利
                self.win_detective_id = self.detective_id
                self.add_log("detectivewin:%s" % self.detective_id)
                self.start_result()
            else:
                # 恥ずか死
                self.add_log("companion:detective:%s" % self.detective_id)
                self.get_player(self.detective_id).live = False
                # 勝利条件チェック
                if self.get_winner_team():
                    self.start_result()
                else:
                    # 他の名探偵チェック
                    detective_show = None
                    for action in self.decide_actions:
                        if "detective_show:" in action:
                            div = action.split(":")
                            detective_id = div[1]
                            detective_p = self.get_player(detective_id)
                            if detective_p.live:
                                detective_show = detective_id
                                break
                    if detective_show is None:
                        self.detective_id = None
                        self.now_detective_answer = []
                        self.start_vote()
                    else:
                        self.detective_id = detective_show
                        self.start_detective_show()



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
            if p.live and p.first_victim is False:
                actions = p.role.get_actions(self, p.discord_id)
                for action in actions:
                    if len(action) >= 3 and action[:3] == "co:":
                        continue
                    if len(action) >= 5 and action[:5] == "noco:":
                        continue
                    if len(action) >= 5 and action[:5] == "hand_":
                        continue
                    if len(action) >= 15 and action[:15] == "detective_show:":
                        continue
                    rest_actions.append(action)
        return rest_actions

    def move_members(self):
        dic = {}
        if self.status in [Status.RESULT, Status.SETTING]:
            # 全員会議室
            for i in range(len(self.players)):
                self.players[i].to_voice = "conference"
        if self.status in [Status.ROLE_CHECK, Status.MORNING]:
            # 個別部屋へ
            for i in range(len(self.players)):
                live = self.players[i].live
                if live:
                    self.players[i].to_voice = "personal%d" % i
                else:
                    self.players[i].to_voice = "ghost"
        if self.status == Status.NIGHT:
            # 夜行動へ
            for i in range(len(self.players)):
                live = self.players[i].live
                token = self.players[i].role.get_token()
                if live:
                    if eng2token("werewolf") == token:
                        self.players[i].to_voice = "werewolf"
                    elif eng2token("mason") == token:
                        self.players[i].to_voice = "mason"
                    elif eng2token("fox") == token:
                        self.players[i].to_voice = "fox"
                    else:
                        self.players[i].to_voice = "personal%d" % i
                else:
                    self.players[i].to_voice = "ghost"
        if self.status in [Status.AFTERNOON, Status.EXCUTION, Status.VOTE]:
            # 昼行動へ
            for i in range(len(self.players)):
                live = self.players[i].live
                if live:
                    self.players[i].to_voice= "conference"
                else:
                    self.players[i].to_voice = "ghost"

    def start_detective_show(self):
        self.status = Status.DETECTIVE
        self.get_player(self.detective_id).reveal_role = True
        self.now_detective_answer = []
        # 初期配役をルールからセット
        for k, v in self.rule["roles"].items():
            for _ in range(v):
                self.now_detective_answer.append(token2eng(k))
        # 目安として３分をタイマーセット
        self.set_timer(
            "detective",
            3,
            0
        )
        self.callback()

    def start_detective_ready(self):
        self.status = Status.DETECTIVE_READY
        # 結果を焦らす
        self.set_timer(
            "detective_ready",
            0,
            5
        )
        self.callback()

    def start_night(self):
        self.timer_stop = False
        for p in self.players:
            p.hand = None
        self.action_results = []
        self.decide_actions = []
        self.status = Status.NIGHT
        if self.config["GAME"]["WAIT_MOVE"] in ["True", "true"]:
            self.waitmove_timer_stop = True
            self.all_moved_flag = False
        self.move_members()
        self.set_timer(
            "night",
            self.rule["night_seconds"] // 60,
            self.rule["night_seconds"] % 60
        )

    def start_morning(self):
        self.timer_stop = False
        self.day += 1
        self.status = Status.MORNING
        self.move_members()
        self.set_timer("morning", 0, self.rule["morning_seconds"])
        # 犠牲者セット
        victim_ids = []
        # 噛まれた人が死ぬ
        attack_wolf = None
        for action in self.decide_actions:
            div = action.split(":")
            if div[0] == "attack":
                attack_wolf = div[1]
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
        # 噛まれて死亡した猫又は噛んだ人狼を道連れに
        for victim_id in victim_ids:
            victim_role = self.get_player(victim_id).role
            if victim_role is not None and victim_role.get_token() == "猫":
                if attack_wolf is not None:
                    victim_ids.append(attack_wolf)
                    self.add_log("companion:cat:%s" % attack_wolf)
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
        # 妖狐が全滅していたら背徳者は全部後追い
        live_fox_ids = []
        for p in self.players:
            if p.live and p.discord_id not in victim_ids and p.role.get_token() == "狐":
                live_fox_ids.append(p.discord_id)
        if len(live_fox_ids) <= 0:
            for p in self.players:
                if p.live and p.role.get_token() == "背":
                    self.add_log("companion:immoralist:%s" % p.discord_id)
                    victim_ids.append(p.discord_id)
        # 女王が死亡（最大一人）した場合人間カウントが全部後追い
        live_queen = True
        for p in self.players:
            if p.role.get_token() == "女" and (p.discord_id in victim_ids or p.live is False):
                live_queen = False
        if live_queen is False:
            for p in self.players:
                if p.live and p.role.get_team_count() == TeamCount.HUMAN:
                    if p.discord_id not in victim_ids:
                        self.add_log("companion:queen:%s" % p.discord_id)
                        victim_ids.append(p.discord_id)
        victim_ids = list(set(victim_ids))
        shuffle(victim_ids)
        for victim_id in victim_ids:
            self.action_results.append("victim:%s" % victim_id)
            self.get_player(victim_id).live = False
        self.callback()

    def start_afternoon(self):
        self.timer_stop = False
        self.decide_actions = []
        seconds = self.rule["day_seconds"]
        seconds -= self.rule["day_minus_seconds"] * (self.day - 1)
        if seconds < self.rule["min_day_seconds"]:
            seconds = self.rule["min_day_seconds"]
        self.status = Status.AFTERNOON
        self.vote_count = 0
        if self.config["GAME"]["WAIT_MOVE"] in ["True", "true"]:
            self.waitmove_timer_stop = True
            self.all_moved_flag = False
        self.move_members()
        self.set_timer("afternoon", seconds // 60, seconds % 60)
        self.callback()

    def start_vote(self):
        self.timer_stop = False
        for p in self.players:
            p.hand = None
        self.decide_actions = []
        if self.status != Status.VOTE:
            # 初回は全員が投票対象
            self.vote_candidates = [
                p.discord_id for p in self.players if p.live]
        self.status = Status.VOTE
        self.move_members()
        self.callback()

    def start_excution(self):
        self.timer_stop = False
        for p in self.players:
            p.hand = None
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
                self.vote_count += 1
                self.start_vote()
                return
        else:
            assert len(max_ids) == 1
            excuted_id = max_ids[0]
        self.excuted_id = excuted_id
        # self.decide_actions = []
        self.status = Status.EXCUTION
        self.move_members()
        self.callback()
        # 遺言タイマー
        self.set_timer("excution", 0, self.rule["will_seconds"])

    def start_result(self):
        """
        結果表示
        """
        self.second = 0
        self.minute = 0
        self.timer_stop = False
        self.status = Status.RESULT
        self.move_members()
        self.callback()

    def start_role_check(self):
        self.timer_stop = False
        self.status = Status.ROLE_CHECK
        self.move_members()
        self.callback()
        self.set_timer("role_checking", 0, self.rule["morning_seconds"])

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
        # 名探偵の推理が当たっていたら名探偵勝利
        if self.win_detective_id is not None:
            return Team.DETECTIVE
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
        役かけに配布可能な役職があるかどうか
        """
        winner_team = self.get_winner_team()
        if winner_team is not None:
            return False
        first_victim_role = 0
        for k, v in self.rule["roles"].items():
            if k not in ["狼", "狐", "猫", "女", "探"]:
                first_victim_role += v
        if self.rule["first_victim"]:
            if first_victim_role <= 0:
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
        役かけには尻尾のある役職は渡さない
        """
        roles = []
        for k, v in self.rule["roles"].items():
            for _ in range(v):
                roles.append(token2role(k)())
        for n in range(1000000):
            shuffle(roles)
            if self.rule["first_victim"] is False:
                break
            if roles[-1].get_token() not in ["狼", "狐", "猫", "女", "探"]:
                break
            if n >= 999999:
                print("役職配布エラー")
                assert False
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
        p.to_voice = None
        if len(self.players) > 0 and self.players[-1].first_victim:
            self.players.insert(-1, p)
        else:
            self.players.append(p)
        self.move_members()

    def remove_player(self, discord_id):
        if self.get_player(discord_id) is None:
            return
        for p in self.players:
            if p.discord_id == discord_id:
                self.players.remove(p)
                return

    def add_first_victim_player(self):
        if self.get_player(self.first_victim_id) is not None:
            return
        p = Player()
        p.discord_id = self.first_victim_id
        p.avator_url = None
        p.name = self.first_victim_name
        p.voice = ""
        p.to_voice = None
        p.first_victim = True
        self.players.append(p)
        self.move_members()

    def get_player(self, discord_id):
        for p in self.players:
            if p.discord_id == discord_id:
                return p
        return None

    def get_raise_hand_n(self):
        count = 0
        for p in self.players:
            if p.hand is not None:
                count += 1
        return count

    def input_action(self, action):
        if action != "":
            if action not in self.decide_actions:
                self.decide_actions.append(action)
                self.add_log(action)
                self.callback()
        print("input_action", "'" + action + "'", self.status)

        # アクション後に確認が必要なケースの対応
        # 投票完了
        if self.status == Status.VOTE:
            # 投票したら手を自動で下げる
            if "vote:" in action:
                div = action.split(":")
                for p in self.players:
                    if p.discord_id == div[1] and p.hand is not None:
                        p.hand = None
            rest_actions = self.get_live_player_rest_actions()
            if len(rest_actions) <= 0:
                self.start_excution()
        # スキップ完了
        if self.status == Status.AFTERNOON:
            rest_actions = self.get_live_player_rest_actions()
            if len(rest_actions) <= 0:
                self.minute = 0
                self.second = 5
        # CO
        if len(action) >= 5 and (action[:3] == "co:" or action[:5] == "noco:"):
            role = action.split(":")[1]
            discord_id = action.split(":")[2]
            coflag = True
            if "noco:" in action:
                coflag = False
            p = self.get_player(discord_id)
            if coflag and role not in p.co_list:
                p.co_list.append(role)
                self.callback()
            elif coflag is False and role in p.co_list:
                p.co_list.remove(role)
                self.callback()
        # 手を挙げる、下げる
        if len(action) >= 5 and action[:5] == "hand_":
            discord_id = action.split(":")[1]
            p = self.get_player(discord_id)
            if "hand_raise" in action:
                if self.status != Status.VOTE or self.get_raise_hand_n() < 2:
                    p.hand = self.hand_count
                    self.hand_count += 1
                    self.callback()
            elif "hand_down" in action:
                p.hand = None
                self.callback()
        # １番手の更新
        hands = sorted([n.hand for n in self.players if n.hand is not None])
        if len(hands) > 0:
            min_hand = hands[0]
            first_hand_discord_id = None
            for n in self.players:
                if n.hand is not None and n.hand == min_hand:
                    first_hand_discord_id = n.discord_id
            if first_hand_discord_id is not None:
                if self.status == Status.VOTE:
                    if self.first_hand_discord_id != first_hand_discord_id:
                        # 投票タイマー
                        self.set_timer("vote", 0, self.rule["vote_seconds"])
                self.first_hand_discord_id = first_hand_discord_id
        # 遺言完了
        if self.status == Status.EXCUTION:
            rest_actions = self.get_live_player_rest_actions()
            if len(rest_actions) <= 0:
                # 処刑者を死亡処理して勝利判定後に夜開始
                for p in self.players:
                    if p.discord_id == self.excuted_id:
                        p.live = False
                # 勝利判定前に道連れ処理
                self.companions = []
                if self.excuted_id is not None:
                    excuted_role = self.get_player(self.excuted_id).role.get_token()
                    if excuted_role == "猫":
                        # 猫又のランダム道連れ
                        candidates = []
                        for p in self.players:
                            if p.live and p.role.get_team() == Team.VILLAGER:
                                candidates.append(p.discord_id)
                        if len(candidates) > 0:
                            shuffle(candidates)
                            self.companions.append("cat:%s" % candidates[0])
                            self.add_log("companion:cat:%s" % candidates[0])
                            for p in self.players:
                                if p.discord_id == candidates[0]:
                                    p.live = False
                    if excuted_role == "狐":
                        # 背徳者の後追い自殺
                        live_fox_ids = []
                        for p in self.players:
                            if p.live and p.role.get_name() == "妖狐":
                                live_fox_ids.append(p.discord_id)
                        if len(live_fox_ids) <= 0:
                            # 妖狐全滅
                            for p in self.players:
                                if p.live and p.role.get_name() == "背徳者":
                                    self.companions.append("immoralist:%s" % p.discord_id)
                                    self.add_log("companion:immoralist:%s" % p.discord_id)
                                    p.live = False
                    # 道連れ処理のあと、女王が死亡していたら人間判定は全員後追い
                    live_queen = True
                    for p in self.players:
                        if p.role.get_token() == "女" and p.live is False:
                            live_queen = False
                    if live_queen is False:
                        for p in self.players:
                            if p.live and p.role.get_team_count() == TeamCount.HUMAN:
                                self.companions.append("queen:%s" % p.discord_id)
                                self.add_log("companion:queen:%s" % p.discord_id)
                                p.live = False
                if self.get_winner_team() is None:
                    self.start_night()
                else:
                    print("FINISH", self.get_winner_team())
                    self.second = 0
                    self.minute = 0
                    self.start_result()
        # 結果完了
        if self.status == Status.RESULT:
            if "result:" in action:
                # ゲーム結果を保存
                dt_now = datetime.datetime.now()
                filename = "game" + dt_now.strftime('%Y%m%d-%H%M%S') + ".pickle"
                self.save(filename)
                self.reset()
                self.move_members()
                self.callback()
        # 名探偵の推理
        if self.status == Status.DETECTIVE:
            if "now_detective_answer:" in action:
                div = action.split(":")
                detective_id = div[1]
                answer = div[2].split(",")
                if self.detective_id == detective_id:
                    self.now_detective_answer = answer
                    self.callback()
            if "detective_complete:" in action:
                self.second = 0
                self.minute = 0
                self.start_detective_ready()

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
                        upper = token2role(token)().upper
                        if upper is None or upper >= self.rule["roles"][token] + 1:
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
            if "first_victim_" in message:
                self.rule["first_victim"] = (message == "first_victim_yes")
                if self.rule["first_victim"]:
                    self.add_first_victim_player()
                else:
                    self.remove_player(self.first_victim_id)

    def get_status(self, from_discord_id):
        open_flag = False
        log_open_flag = False
        if self.status == Status.RESULT:
            open_flag = True
            log_open_flag = True
        action_results = list(self.action_results)
        # 個人分を追加 & 行動履歴開示条件（死亡しているか）の確認
        for p in self.players:
            if p.discord_id == from_discord_id:
                if p.role is not None and p.first_victim is False:
                    action_results += p.role.get_action_results(
                        self, from_discord_id
                    )
                if p.live is False:
                    log_open_flag = True
        result = self.get_winner_team()
        if result is not None:
            result = result.name
        roles = {}
        if log_open_flag:
            for p in self.players:
                if p.role is not None:
                    roles[p.discord_id] = p.role.get_name()
        # パン屋生存有無
        live_baker = "no_baker"
        live_flag = False
        for p in self.players:
            if p.role is not None and p.role.get_name() == "パン屋":
                live_baker = "dead"
                if p.live:
                    live_flag = True
        if live_flag:
            live_baker = "live"
        return {
            "status": self.status.name,
            "players": [
                n.get_status(
                    open_flag, from_discord_id, self) for n in self.players
            ],
            "rule": {
                "roles": self.rule["roles"],
                "first_seer": self.rule["first_seer"].name,
                "bodyguard": self.rule["bodyguard"].name,
                "first_victim": self.rule["first_victim"],
            },
            "minute": self.minute,
            "second": self.second,
            "day": self.day,
            "action_results": action_results,
            "excution": self.excuted_id,
            "result": result,
            "log": self.get_logs(log_open_flag),
            "vote": self.vote_count,
            "vote_candidates": self.vote_candidates,
            "roles": roles,
            "timer_stop": self.timer_stop or self.waitmove_timer_stop,
            "all_moved_flag": self.all_moved_flag,
            "live_baker_flag": live_baker,
            "companions": self.companions,
            "detective": self.detective_id,
            "now_detective_answer": self.now_detective_answer,
        }

    def add_log(self, action):
        """
        行動ログの管理をする
        原則として、アクションの合法確認は実施しない
        何日目のどのフェーズでのアクションかを区別する
        {
            "0-NIGHT": ["vote:12345678:12345679", "..."]
        }
        """
        key = "%d-%s" % (self.day, self.status.name)
        if self.status == Status.VOTE:
            key += "-%d" % self.vote_count
        if key not in self.logs:
            self.logs[key] = []
        if action not in self.logs[key]:
            self.logs[key].append(action)

    def get_logs(self, all_flag):
        """
        ログを取得
        all_flag: True 非公開情報も含めて全てか（神視点）
        Falseなら投票履歴のみ

        vote:id:id
        excution:id
        skip:id
        attack:id:id
        bodyguard:id:id
        seer:id:id
        """
        result = {}
        for k, v in self.logs.items():
            if k not in result:
                result[k] = []
            for vv in v:
                div = vv.split(":")
                # 投票についてはall_flagに関係なく含める
                # ただし、決選投票についてはそれが完了するまで含めない
                # 投票のフェーズ day-VOTE-count
                include_flag = False
                if div[0] == "vote":
                    key_div = k.split("-")
                    if key_div[1] != "VOTE":
                        include_flag = True
                    else:
                        if self.status != Status.VOTE:
                            include_flag = True
                        elif self.vote_count == 0:
                            include_flag = True
                        elif self.day != int(key_div[0]) or self.vote_count != int(key_div[2]):
                            include_flag = True
                else:
                    include_flag = False
                if all_flag:
                    include_flag = True
                if include_flag:
                    result[k].append(vv)
        return result
