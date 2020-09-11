# -*- encoding=utf-8 -*-
import abc
import inspect
import logging
import os

from src.ac.framework.ac_result import SUCCESS, WARNING, FAILED

logger = logging.getLogger("ac")


class BaseCheck(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, workspace, repo, conf=None):
        """

        :param repo:
        :param workspace:
        :param conf:
        """
        self._repo = repo
        self._workspace = workspace
        self._conf = conf

        self._work_dir = os.path.join(workspace, repo)

    @abc.abstractmethod
    def __call__(self, *args, **kwargs):
        raise NotImplementedError("subclasses must override __call__!")

    def start_check_with_order(self, *items):
        """
        按照items中顺序运行
        """
        result = SUCCESS
        for name in items:
            try:
                logger.debug("check {}".format(name))
                method = getattr(self, "check_{}".format(name))
                rs = method()
                logger.debug("{} -> {}".format(name, rs))
            except Exception as e:
                # 忽略代码错误
                logger.exception("internal error: {}".format(e))
                continue

            ignored = True if self._conf and name in self._conf.get("ignored", []) else False
            logger.debug("{} ignore: {}".format(name, ignored))

            if rs is SUCCESS:
                logger.info("check {:<30}pass".format(name))
            elif rs is WARNING:
                logger.warning("check {:<30}warning{}".format(name, " [ignored]" if ignored else ""))
            elif rs is FAILED:
                logger.error("check {:<30}fail{}".format(name, " [ignored]" if ignored else ""))
            else:
                # never here
                logger.exception("check {:<30}exception{}".format(name, " [ignored]" if ignored else ""))
                continue

            if not ignored:
                result += rs

        return result

    def start_check(self):
        """
        运行所有check_开头的函数
        """
        members = inspect.getmembers(self, inspect.ismethod)
        items = [member[0].replace("check_", "") for member in members if member[0].startswith("check_")]
        logger.debug("check items: {}".format(items))

        return self.start_check_with_order(*items)
