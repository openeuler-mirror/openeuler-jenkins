# -*- encoding=utf-8 -*-
import re
import logging

from src.ac.common.pyrpm import Spec, replace_macros

logger = logging.getLogger("ac")


class RPMSpecAdapter(object):
    """
    rpm spec file object
    """
    def __init__(self, fp):
        if isinstance(fp, str):
            with open(fp, "r") as fp:
                self._adapter = Spec.from_string(fp.read())
        else:
            self._adapter = Spec.from_string(fp.read())
            fp.close()

    def __getattr__(self, item):
        """

        :param item:
        :return
        """
        value = getattr(self._adapter, item)
        if isinstance(value, list):
            return [replace_macros(item, self._adapter) for item in value]

        return replace_macros(value, self._adapter) if value else ""

    def include_x86_arch(self):
        """
        check include x86-64
        :return
        """
        try:
            value = self.buildarch
            logger.debug("build arch: {}".format(value))
            if "x86_64" in value.lower():
                return True

            return False
        except AttributeError:
            return True

    def include_aarch64_arch(self):
        """
        check include aarch64
        :return
        """
        try:
            value = self.buildarch
            logger.debug("build arch: {}".format(value))
            if "aarch64" in value.lower():
                return True

            return False
        except AttributeError:
            return True

    @staticmethod
    def compare_version(version_n, version_o):
        """
        :param version_n:
        :param version_o:
        :return: 0~eq, 1~gt, -1~lt
        """
        # replace continued chars to dot
        version_n = re.sub("[a-zA-Z_-]+", ".", version_n).strip().strip(".")
        version_o = re.sub("[a-zA-Z_-]+", ".", version_o).strip().strip(".")
        # replace continued dots to a dot
        version_n = re.sub("\.+", ".", version_n)
        version_o = re.sub("\.+", ".", version_o)
        # same partitions with ".0" padding
        # "..." * -n = ""
        version_n = "{}{}".format(version_n, '.0' * (len(version_o.split('.')) - len(version_n.split('.'))))
        version_o = "{}{}".format(version_o, '.0' * (len(version_n.split('.')) - len(version_o.split('.'))))

        logger.debug("compare versions: {} vs {}".format(version_n, version_o))
        z = zip(version_n.split("."), version_o.split("."))

        for p in z:
            try:
                if int(p[0]) < int(p[1]):
                    return -1
                elif int(p[0]) > int(p[1]):
                    return 1
            except ValueError as exc:
                logger.debug("check version exception, {}".format(exc))
                continue

        return 0

    def compare(self, other):
        """
        比较spec的版本号和发布号
        :param other:
        :return: 0~eq, 1~gt, -1~lt
        """
        if self.__class__.compare_version(self.version, other.version) == 1:
            return 1
        if self.__class__.compare_version(self.version, other.version) == -1:
            return -1

        if self.__class__.compare_version(self.release, other.release) == 1:
            return 1
        if self.__class__.compare_version(self.release, other.release) == -1:
            return -1

        return 0

    def __lt__(self, other):
        return -1 == self.compare(other)

    def __eq__(self, other):
        return 0 == self.compare(other)

    def __gt__(self, other):
        return 1 == self.compare(other)
