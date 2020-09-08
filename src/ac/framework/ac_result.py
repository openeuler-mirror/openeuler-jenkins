# -*- encoding=utf-8 -*-
"""
Use this variables (FAILED, WARNING, SUCCESS) at most time,
and don't new ACResult unless you have specific needs.
"""


class ACResult(object):
    """
    ac test result
    """
    def __init__(self, val):
        self._val = val

    def __add__(self, other):
        return self if self.val >= other.val else other

    def __str__(self):
        return self.hint

    def __repr__(self):
        return self.__str__()

    @classmethod
    def get_instance(cls, val):
        if isinstance(val, int):
            return {0: SUCCESS, 1: WARNING, 2: FAILED}.get(val)
        if isinstance(val, bool):
            return {True: SUCCESS, False: FAILED}.get(val)

        try:
            val = int(val)
            return {0: SUCCESS, 1: WARNING, 2: FAILED}.get(val)
        except ValueError:
            return {"success": SUCCESS, "fail": FAILED, "failed": FAILED, "failure": FAILED,
                    "warn": WARNING, "warning": WARNING}.get(val.lower(), FAILED)

    @property
    def val(self):
        return self._val

    @property
    def hint(self):
        return ["SUCCESS", "WARNING", "FAILED"][self.val]

    @property
    def emoji(self):
        return [":white_check_mark:", ":bug:", ":x:"][self.val]


FAILED = ACResult(2)
WARNING = ACResult(1)
SUCCESS = ACResult(0)
