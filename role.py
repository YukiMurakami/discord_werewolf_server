from enum import Enum
from util import Status, FirstSeerRule, BodyguardRule
import random


class SeerResult(Enum):
    NO_WEREWOLF = 1
    WEREWOLF = 2


class MediumResult(Enum):
    NO_WEREWOLF = 1
    WEREWOLF = 2


class TeamCount(Enum):
    HUMAN = 1
    WEREWOLF = 2
    NOTHING = 3


class Team(Enum):
    VILLAGER = 1
    WEREWOLF = 2
    FOX = 3
    DETECTIVE = 4


class Role:
    def __init__(self):
        self.name = ""
        self.token = ""
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.know_names = []
        self.upper = None

    def get_name(self):
        return self.name

    def get_token(self):
        return self.token

    def get_seer_result(self):
        return self.seer_result

    def get_medium_result(self):
        return self.medium_result

    def get_team_count(self):
        return self.team_count

    def get_team(self):
        return self.team

    def get_action_results(self, game, player_discord_id):
        """
        特定個人や役職しか知らない行動結果を返す
        """
        action_results = []
        return action_results

    def get_actions(self, game, player_discord_id):
        # 共通アクション
        actions = []
        # 投票
        already_vote = False
        can_vote = True
        if game.status == Status.VOTE:
            for action in game.decide_actions:
                if "vote:%s:" % player_discord_id in action:
                    already_vote = True
            if already_vote is False:
                # 決選投票判定
                live_player_n = len([p for p in game.players if p.live])
                if live_player_n != len(game.vote_candidates):
                    # 決戦。対象なら投票権なし
                    if player_discord_id in game.vote_candidates:
                        can_vote = False
                if can_vote:
                    # 自分以外に投票
                    # アクションは vote:voter_discord_id:target_discord_id
                    for cand in game.vote_candidates:
                        if cand != player_discord_id:
                            actions.append(
                                "vote:%s:%s" % (
                                    player_discord_id, cand
                                )
                            )
        # 処刑時遺言確認
        if game.status == Status.EXCUTION:
            already_excute = False
            for action in game.decide_actions:
                if "excution:" in action:
                    already_excute = True
            if already_excute is False:
                if player_discord_id == game.excuted_id:
                    actions.append(
                        "excution:%s" % player_discord_id
                    )
        # お昼スキップ
        if game.status == Status.AFTERNOON:
            already_skip = False
            for action in game.decide_actions:
                if "skip:%s" % player_discord_id in action:
                    already_skip = True
            if already_skip is False:
                actions.append("skip:%s" % player_discord_id)
        # 役職COと撤回
        # 昼時間は自由、投票での発言中はOK（投票したら不可）、決選投票は対象者のみOK（弁明時のCO）
        # 処刑時の遺言はOK
        players = [p for p in game.players if p.discord_id == player_discord_id]
        if len(players) == 1:
            co_flag = False
            if game.status == Status.AFTERNOON:
                co_flag = True
            elif game.status == Status.VOTE:
                if game.vote_count == 0:
                    if already_vote is False:
                        co_flag = True
                else:
                    if already_vote is False and can_vote is False:
                        co_flag = True
            elif game.status == Status.EXCUTION:
                if game.excuted_id is not None and game.excuted_id == player_discord_id:
                    co_flag = True
            if co_flag:
                player = players[0]
                now_co_list = player.co_list
                for role, count in game.rule["roles"].items():
                    role_eng = token2eng(role)
                    if count > 0:
                        if role_eng in now_co_list:
                            actions.append("noco:%s:%s" % (role_eng, player_discord_id))
                        else:
                            actions.append("co:%s:%s" % (role_eng, player_discord_id))
        # 手を挙げる、下げる
        if len(players) == 1:
            if game.status in [Status.AFTERNOON, Status.VOTE]:
                player = players[0]
                if player.hand is None:
                    actions.append("hand_raise:%s" % player_discord_id)
                else:
                    actions.append("hand_down:%s" % player_discord_id)

        return actions


class VillagerRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "村人"
        self.token = "村"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.know_names = [token2role("女")().name]


class WerewolfRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "人狼"
        self.token = "狼"
        self.seer_result = SeerResult.WEREWOLF
        self.medium_result = MediumResult.WEREWOLF
        self.team_count = TeamCount.WEREWOLF
        self.team = Team.WEREWOLF
        self.know_names = [self.name]

    def get_actions(self, game, player_discord_id):
        actions = super().get_actions(game, player_discord_id)
        # 夜フェイズで初日以外
        if game.status == Status.NIGHT:
            already_attack = False
            for action in game.decide_actions:
                if "attack:" in action:
                    already_attack = True
            if already_attack is False:
                if game.day >= 1:
                    # 生きている味方以外を一人噛む
                    # アクションは attack:attacker_discord_id:attacked_discord_id
                    for p in game.players:
                        if p.live:
                            if p.role.get_team_count() != TeamCount.WEREWOLF:
                                actions.append(
                                    "attack:%s:%s" % (
                                        player_discord_id, p.discord_id
                                    )
                                )
                    return actions
                else:
                    # 初日夜
                    for p in game.players:
                        if p.live and p.first_victim:
                            if p.role.get_team_count() != TeamCount.WEREWOLF:
                                actions.append(
                                    "attack:%s:%s" % (
                                        player_discord_id, p.discord_id
                                    )
                                )
                    return actions
        return actions

    def get_action_results(self, game, player_discord_id):
        """
        特定個人や役職しか知らない行動結果を返す
        """
        action_results = super().get_action_results(game, player_discord_id)
        # 夜フェイズに噛んだ場合は噛み先を表示
        for action in game.decide_actions:
            div = action.split(":")
            if div[0] == "attack":
                action_results.append(action)
        return action_results


class SeerRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "占い師"
        self.token = "占"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.first_id = None
        self.know_names = [token2role("女")().name]

    def get_actions(self, game, player_discord_id):
        if self.first_id is None:
            cands = []
            for p in game.players:
                if p.discord_id != player_discord_id and p.first_victim is False:
                    if (p.role is not None and
                            p.role.get_team_count() not in [
                                TeamCount.WEREWOLF, TeamCount.NOTHING]):
                        cands.append(p.discord_id)
            if len(cands) > 0:
                random.shuffle(cands)
                self.first_id = cands[0]

        actions = super().get_actions(game, player_discord_id)
        # 夜フェイズで初日自由 or ２日目以降
        if game.status == Status.NIGHT:
            if game.day >= 1 or game.rule["first_seer"] == FirstSeerRule.FREE:
                already = False
                for action in game.decide_actions:
                    if "seer:%s" % player_discord_id in action:
                        already = True
                if already is False:
                    # 生きている自分以外を占う
                    # アクションは seer:my_discord_id:target_discord_id
                    for p in game.players:
                        if (p.live and p.discord_id != player_discord_id and
                                p.first_victim is False):
                            actions.append(
                                "seer:%s:%s" % (
                                    player_discord_id, p.discord_id
                                )
                            )
        return actions

    def get_action_results(self, game, player_discord_id):
        """
        特定個人や役職しか知らない行動結果を返す
        """
        action_results = super().get_action_results(game, player_discord_id)
        # 夜フェイズの占い結果を表示
        day = game.day
        if game.status in [Status.NIGHT, Status.MORNING]:
            if game.status == Status.MORNING:
                day -= 1
            mode = "no"
            if day == 0:
                if game.rule["first_seer"] == FirstSeerRule.RANDOM_WHITE:
                    mode = "random_white"
                elif game.rule["first_seer"] == FirstSeerRule.FREE:
                    mode = "free"
            else:
                mode = "free"
            if mode == "random_white":
                action_results.append(
                    "seer:%s:%s:%s" % (
                        player_discord_id, self.first_id,
                        game.get_player(
                            self.first_id).role.get_seer_result().name
                    )
                )
                if "0-NIGHT" not in game.logs:
                    game.logs["0-NIGHT"] = []
                log = "seer:%s:%s" % (player_discord_id, self.first_id)
                if log not in game.logs["0-NIGHT"]:
                    game.logs["0-NIGHT"].append(log)
            elif mode == "free":
                target_id = None
                for action in game.decide_actions:
                    div = action.split(":")
                    if div[0] == "seer":
                        if div[1] == player_discord_id:
                            target_id = div[2]
                if target_id is not None:
                    action_results.append(
                        "seer:%s:%s:%s" % (
                            player_discord_id, target_id,
                            game.get_player(
                                target_id).role.get_seer_result().name
                        )
                    )
        return action_results


class MediumRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "霊媒師"
        self.token = "霊"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.know_names = [token2role("女")().name]

    def get_actions(self, game, player_discord_id):
        actions = super().get_actions(game, player_discord_id)
        return actions

    def get_action_results(self, game, player_discord_id):
        """
        特定個人や役職しか知らない行動結果を返す
        """
        action_results = super().get_action_results(game, player_discord_id)
        # 夜フェイズの霊媒結果を表示
        if game.status in [Status.NIGHT, Status.MORNING]:
            if game.excuted_id is not None:
                action_results.append(
                    "medium:%s:%s:%s" % (
                        player_discord_id, game.excuted_id,
                        game.get_player(
                            game.excuted_id).role.get_medium_result().name
                    )
                )
        return action_results


class BodyguardRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "狩人"
        self.token = "狩"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.know_names = [token2role("女")().name]

    def get_actions(self, game, player_discord_id):
        actions = super().get_actions(game, player_discord_id)
        # 夜フェイズで２日目以降
        if game.status == Status.NIGHT:
            if game.day >= 1:
                already = False
                for action in game.decide_actions:
                    if "bodyguard:%s" % player_discord_id in action:
                        already = True
                if already is False:
                    lastguard_id = None
                    print("lastguard", game.last_guards)
                    rule = game.rule["bodyguard"]
                    if rule == BodyguardRule.CANNOT_CONSECUTIVE_GUARD:
                        for lastguard in game.last_guards:
                            # discord_id:target_discord_id:day
                            div = lastguard.split(":")
                            if player_discord_id == div[0] and int(
                                    div[2]) == game.day - 1:
                                lastguard_id = div[1]
                    # 生きている自分以外を守る
                    # アクションは bodyguard:my_discord_id:target_discord_id
                    for p in game.players:
                        if p.live and p.discord_id != player_discord_id:
                            if (lastguard_id is None or
                                    lastguard_id != p.discord_id):
                                actions.append(
                                    "bodyguard:%s:%s" % (
                                        player_discord_id, p.discord_id
                                    )
                                )
        return actions

    def get_action_results(self, game, player_discord_id):
        """
        特定個人や役職しか知らない行動結果を返す
        """
        action_results = super().get_action_results(game, player_discord_id)
        # 夜フェイズの守り先
        for action in game.decide_actions:
            div = action.split(":")
            if div[0] == "bodyguard":
                action_results.append(action)
        return action_results


class MadmanRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "狂人"
        self.token = "狂"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.WEREWOLF


class MasonRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "共有者"
        self.token = "共"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.know_names = [self.name, token2role("女")().name]


class CultistRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "狂信者"
        self.token = "信"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.WEREWOLF
        self.know_names = [token2role("狼")().name]


class FoxRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "妖狐"
        self.token = "狐"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.NOTHING
        self.team = Team.FOX
        self.know_names = [self.name]


class BakerRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "パン屋"
        self.token = "パ"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.know_names = [token2role("女")().name]


class CatRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "猫又"
        self.token = "猫"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.know_names = [token2role("女")().name]


class ImmoralistRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "背徳者"
        self.token = "背"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.FOX
        self.know_names = [token2role("狐")().name]


class QueenRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "女王"
        self.token = "女"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.upper = 1


class DetectiveRole(Role):
    def __init__(self):
        super().__init__()
        self.name = "名探偵"
        self.token = "探"
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.DETECTIVE

    def get_actions(self, game, player_discord_id):
        actions = super().get_actions(game, player_discord_id)
        # 昼フェイズに推理ショーをするか選択
        if game.status == Status.AFTERNOON:
            already_show = False
            for action in game.decide_actions:
                if "detective_show:%s" % player_discord_id in action:
                    already_show = True
            if already_show is False:
                actions.append("detective_show:%s" % player_discord_id)
        return actions

    def get_action_results(self, game, player_discord_id):
        """
        特定個人や役職しか知らない行動結果を返す
        """
        action_results = super().get_action_results(game, player_discord_id)
        # 昼フェイズに推理ショー表明はそれを表示
        for action in game.decide_actions:
            div = action.split(":")
            if div[0] == "detective_show" and div[1] == player_discord_id:
                action_results.append(action)
        return action_results


def eng2token(eng):
    dic = {
        "villager": "村",
        "werewolf": "狼",
        "seer": "占",
        "medium": "霊",
        "bodyguard": "狩",
        "madman": "狂",
        "mason": "共",
        "cultist": "信",
        "fox": "狐",
        "baker": "パ",
        "cat": "猫",
        "immoralist": "背",
        "queen": "女",
        "detective": "探",
    }
    # front川のrole_menu.jsを変更すること
    return dic[eng]


def token2eng(token):
    dic = {
        "村": "villager",
        "狼": "werewolf",
        "占": "seer",
        "霊": "medium",
        "狩": "bodyguard",
        "狂": "madman",
        "共": "mason",
        "信": "cultist",
        "狐": "fox",
        "パ": "baker",
        "猫": "cat",
        "背": "immoralist",
        "女": "queen",
        "探": "detective",
    }
    # front川のrole_menu.jsを変更すること
    return dic[token]


def token2role(token):
    dic = get_role_dic()
    return dic[token]


def get_role_dic():
    dic = {
        "村": VillagerRole,
        "狼": WerewolfRole,
        "占": SeerRole,
        "霊": MediumRole,
        "狩": BodyguardRole,
        "狂": MadmanRole,
        "共": MasonRole,
        "信": CultistRole,
        "狐": FoxRole,
        "パ": BakerRole,
        "猫": CatRole,
        "背": ImmoralistRole,
        "女": QueenRole,
        "探": DetectiveRole,
    }
    return dic
