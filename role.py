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


class Role:
    def __init__(self):
        self.name = ""
        self.token = ""
        self.seer_result = SeerResult.NO_WEREWOLF
        self.medium_result = MediumResult.NO_WEREWOLF
        self.team_count = TeamCount.HUMAN
        self.team = Team.VILLAGER
        self.know_names = []

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
        if game.status == Status.VOTE:
            already_vote = False
            for action in game.decide_actions:
                if "vote:%s:" % player_discord_id in action:
                    already_vote = True
            if already_vote is False:
                can_vote = True
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
        if game.status == Status.NIGHT and game.day >= 1:
            already_attack = False
            for action in game.decide_actions:
                if "attack:" in action:
                    already_attack = True
            if already_attack is False:
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
        self.know_names = []
        self.first_id = None

    def get_actions(self, game, player_discord_id):
        if self.first_id is None:
            cands = []
            for p in game.players:
                if p.discord_id != player_discord_id:
                    if (p.role is not None and
                            p.role.get_team_count() != TeamCount.WEREWOLF):
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
                        if p.live and p.discord_id != player_discord_id:
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
        self.know_names = []

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
        self.know_names = []

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
        self.know_names = [self.name]


def eng2token(eng):
    dic = {
        "villager": "村",
        "werewolf": "狼",
        "seer": "占",
        "medium": "霊",
        "bodyguard": "狩",
        "madman": "狂",
        "mason": "共"
    }
    return dic[eng]


def token2role(token):
    dic = {
        "村": VillagerRole,
        "狼": WerewolfRole,
        "占": SeerRole,
        "霊": MediumRole,
        "狩": BodyguardRole,
        "狂": MadmanRole,
        "共": MasonRole,
    }
    return dic[token]
