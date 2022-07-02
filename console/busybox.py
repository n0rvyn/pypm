#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2021 by ZHANG ZHIJIE.
# All rights reserved.

# Last Modified Time: 2022/1/10 11:12
# Author: ZHANG ZHIJIE
# Email: norvyn@norvyn.com
# File Name: busybox.py
# Tools: PyCharm

"""
---Short description of this Python module---

"""
import os
import logging
import sys


class ColorLogFormatter(logging.Formatter):
    def __init__(self, level):
        color = {'info': '\033[0;37m',
                 'debug': '\033[0;32m',
                 'warn': '\033[0;33m',
                 'error': '\033[0;31m',
                 'critical': '\033[1;31m'}
        COLOR_EOL = '\033[0m'
        try:
            fmt = f'%(asctime)s [%(name)s]: {color[level]}%(levelname)8s{COLOR_EOL}: %(message)s'
        except KeyError:
            raise TypeError('Wrong log level, must be debug, info, warn, error or critical.')

        logging.Formatter.__init__(self, fmt=fmt, datefmt='%Y-%m-%d %H:%M')

    def formatter(self, name, msg, level):
        record = logging.LogRecord(name=name, level=level, pathname='.', lineno=1, msg=msg, args=(), exc_info=None)
        return self.format(record)


class ColorLogger(logging.Logger):
    def __init__(self, name, filename, display=True):
        logging.Logger.__init__(self, name=name, level=logging.DEBUG)
        self.name = name
        self.display = display
        if self.display:
            screen = logging.StreamHandler(sys.stdout)
            self.addHandler(screen)
        logFile = logging.FileHandler(filename)
        self.addHandler(logFile)

    def colorlog(self, msg, level):
        formatter = ColorLogFormatter(level)
        loglevel = {'debug': logging.DEBUG, 'info': logging.INFO, 'warn': logging.WARN,
                    'error': logging.ERROR, 'critical': logging.CRITICAL}
        try:
            self.info(formatter.formatter(self.name, msg, loglevel[level]))
        except KeyError:
            raise TypeError('Wrong log level!')


def read_value(key, configfile,
                 val_is_int=False,
                 val_is_bool=False,
                 val_is_list=False,
                 key_delim=None,
                 list_delim=None):
    key_delim = '=' if key_delim is None else key_delim
    list_delim = ',' if list_delim is None else list_delim
    value = ''
    try:
        with open(configfile, 'r+') as f:
            for line in f.readlines():
                _line_list = line.split(key_delim) if '=' == key_delim else line.split()
                # print(_line_list)
                try:
                    _key, _value = _line_list
                    _key = _key.strip().strip('"').strip("'")
                    _value = _value.strip().strip('"').strip("'")
                    if _key == key:
                        value = _value
                        break
                except ValueError:
                    continue

    except FileNotFoundError as e:
        raise e
    except TypeError as e:
        raise e

    if val_is_int:
        try:
            value = int(value)
        except ValueError:
            pass
    elif val_is_bool:
        if value == 'True':
            return True
        else:
            return False
    elif val_is_list:
        value = list(map(str, value.split(list_delim)))
    return value


def log_cleaner(filename: str, max_size: int):
    try:
        file_size = int(os.path.getsize(filename)) // 1024 // 1024
    except FileNotFoundError:
        return False
    if file_size >= max_size:
        return open(filename, 'w').close()


if __name__ == '__main__':
    pass

