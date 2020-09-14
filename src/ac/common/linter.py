# -*- encoding=utf-8 -*-
import re
import logging

from src.utils.shell_cmd import shell_cmd_live

logger = logging.getLogger("ac")


class LinterCheck(object):
    """
    run linter check code
    """
    PYLINTRESULTPREFIX = ["C", "R", "W", "E", "F"]

    @classmethod
    def get_summary_of_pylint(cls, message):
        """
        parser message for summary and details
        """
        summary = {}
        for prefix in cls.PYLINTRESULTPREFIX:
            m = re.findall("{}: *[0-9]+, *[0-9]+:".format(prefix), "\n".join(message))
            summary[prefix] = len(m)

        return summary

    @classmethod
    def get_summary_of_golint(cls, message):
        """
        所有都当作WARNING
        """
        m = re.findall("\.go:[0-9]+:[0-9]+:", "\n".join(message))
        return {"W": len(m)}

    @classmethod
    def get_summary_of_splint(cls, message):
        """
        parser message for summary
        """
        logger.debug(message)
        summary = {}
        # summary["W"] = summary["W"] + message.count("Use -preproc to inhibit warning")
        # summary["W"] = summary["W"] + message.count("Use -nestcomment to inhibit warning")

        return summary

    @classmethod
    def check_python(cls, filepath):
        """
        Check python script by pylint
        Using the default text output, the message format is :
        MESSAGE_TYPE: LINE_NUM:[OBJECT:] MESSAGE
        There are 5 kind of message types :
        * (C) convention, for programming standard violation
        * (R) refactor, for bad code smell
        * (W) warning, for python specific problems
        * (E) error, for probable bugs in the code
        * (F) fatal, if an error occurred which prevented pylint from doing
        """
        logger.debug("check python file: {}".format(filepath))
        pylint_cmd = "pylint3 {}".format(filepath)
        ret, out, _ = shell_cmd_live(pylint_cmd, cap_out=True, verbose=True)

        if ret:
            logger.debug("pylint ret, {}".format(ret))

        return cls.get_summary_of_pylint(out)

    @classmethod
    def check_golang(cls, filepath):
        """
        Check golang code by golint
        """
        logger.debug("check go file: {}".format(filepath))
        golint_cmd = "golint {}".format(filepath)
        ret, out, _ = shell_cmd_live(golint_cmd, cap_out=True, verbose=True)

        if ret:
            logger.debug("golint error, {}".format(ret))
            return {}

        return cls.get_summary_of_golint(out)

    @classmethod
    def check_c_cplusplus(cls, filepath):
        """
        Check c/c++ code by splint
        """
        logger.debug("check c/c++ file: {}".format(filepath))
        splint_cmd = "splint {}".format(filepath)
        ret, out, _ = shell_cmd_live(splint_cmd, cap_out=True, verbose=True)

        if ret:
            logger.debug("splint error, {}".format(ret))
            return {}

        return cls.get_summary_of_splint(out)
