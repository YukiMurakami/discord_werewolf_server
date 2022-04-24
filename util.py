from enum import Enum


class Status(Enum):
    SETTING = 1
    ROLE_CHECK = 2
    NIGHT = 3
    MORNING = 4
    AFTERNOON = 5
    VOTE = 6
    EXCUTION = 7
    RESULT = 8


class FirstSeerRule(Enum):
    FREE = 1
    RANDOM_WHITE = 2
    NO = 3


class BodyguardRule(Enum):
    CONSECUTIVE_GUARD = 1
    CANNOT_CONSECUTIVE_GUARD = 2
