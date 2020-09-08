#!/usr/bin/env python
# -*- encoding=utf-8 -*-
from colorlog import ColoredFormatter


class CusColoredFormatter(ColoredFormatter):
    def __init__(self, fmt=None, datefmt=None, style='%',
                 log_colors=None, reset=True,
                 secondary_log_colors=None):
        log_colors = {'DEBUG': 'reset',
            'INFO': 'reset',
            'WARNING': 'bold_yellow',
            'ERROR': 'bold_red',
            'CRITICAL': 'bold_red'}
        super(CusColoredFormatter, self).__init__(fmt, datefmt, style, log_colors, reset, secondary_log_colors)
