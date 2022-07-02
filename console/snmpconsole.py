#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2022 by ZHANG ZHIJIE.
# All rights reserved.

# Last Modified Time: 11/18/21 12:03
# Author: ZHANG ZHIJIE
# Email: norvyn@norvyn.com
# File Name: snmpconsole.py
# Tools: PyCharm

"""
---Short description of this Python module---

"""
import subprocess
import os
try:
    import busybox
except ModuleNotFoundError:
    from . import busybox


# windows platform has no command 'which'
# _SNMPWALK_ = subprocess.getoutput('which snmpwalk')
# _SNMPGET_ = subprocess.getoutput('which snmpget')
# _SNMPTABLE_ = subprocess.getoutput('which snmptable')

_SNMPWALK_ = 'snmpwalk'
_SNMPGET_ = 'snmpget'
_SNMPTABLE_ = 'snmptable'

_HOME_ = os.path.abspath(os.path.dirname(__file__))
_ROOT_ = os.path.abspath(os.path.join(_HOME_, '..'))
_LOG_PATH_ = os.path.join(_ROOT_, 'log')
_LOGFILE_ = os.path.join(_LOG_PATH_, 'console.log')
os.mkdir(_LOG_PATH_) if not os.path.exists(_LOG_PATH_) else ''


class SnmpConsole(object):
    def __init__(self, agent, *args,
                 logfile=None, display=True,
                 retries=2, timeout=3, port=161):
        self.args = ' '.join(args)
        # self.args = args
        self.agent = agent

        self._log_file = _LOGFILE_ if logfile is None else logfile
        self.display = display
        self.logger_prefix = 'SNMP'
        self.logger_suffix = str(agent)

        self.port = port
        self.retries = retries
        self.timeout = timeout

        self.args = f'-r {self.retries} -t {self.timeout} {self.args}'
        self.colorlog(f'detected snmp args [{self.args}]', 'debug')

    def colorlog(self, msg=None, level=None):
        msg = '' if msg is None else msg
        level = 'debug' if level is None else level
        name = f'{self.logger_prefix:<4s} {self.logger_suffix:<14s}'
        colorlogger = busybox.ColorLogger(name, self._log_file, display=self.display)
        busybox.log_cleaner(self._log_file, 50)
        colorlogger.colorlog(msg, level)

    def is_port_open(self):
        _output = subprocess.getstatusoutput(f'nc -v -z -w1 -u {self.agent} {self.port}')
        _return = _output[0]
        for _line in _output[1].split('\n'):
            self.colorlog(_line, 'debug')
        return True if _return == 0 else False

    def snmpget(self, oid) -> str:
        self.colorlog(f'snmpget [{oid}] from {self.agent} with args: [{self.args}]')
        return subprocess.getoutput(f'{_SNMPGET_} {self.args} {self.agent} {oid}')

    def snmpwalk(self, oid) -> str:
        """
        :param oid: snmp oid
        :return: strings separated with '\n'
        """
        self.colorlog(f'snmpwalk [{oid}] from {self.agent} with args: [{self.args}]')
        return subprocess.getoutput(f'{_SNMPWALK_} {self.args} {self.agent} {oid}')

    def snmpwalkstatus(self, oid) -> tuple:
        self.colorlog(f'snmpwalk [{oid}] from {self.agent} with args: [{self.args}]')
        return subprocess.getstatusoutput(f'{_SNMPWALK_} {self.args} {self.agent} {oid}')

    def snmptable(self, oid_table_entry) -> str:
        self.colorlog(f'snmptable [{oid_table_entry}] from {self.agent} with args [{self.args}]')
        return subprocess.getoutput(f'{_SNMPTABLE_} {self.args} {self.agent} {oid_table_entry}')

    def snmpwalk_format(self, oid_table):
        _data_list = self.snmpwalk(oid_table).split('\n')
        _data_tuple_list = []
        for _line in _data_list:
            __list1 = _line.split('::')
            __list2 = _line.split('=')

            __mib = __list1[0].strip()
            try:
                __desc = __list1[1].split('.')[0].strip()
            except IndexError as _e:
                self.colorlog(_e, 'warn')
                self.colorlog(f'[{_line}] has no description.', 'warn')
                __desc = '-'

            # some OID has no index.
            try:
                # __index = __list2[0].split('.')[1].strip()
                __index = __list2[0].split('.')[-1].strip()
            except IndexError as _e:
                self.colorlog(_e, 'warn')
                self.colorlog(f'[{_line}] has no index.', 'warn')
                __index = '-'

            try:
                __type = __list2[1].split(':')[0].strip().strip('"')
                # __value = __list2[1].split(':')[1].strip()

                # bug: value string -> STRING: "2022-04-24 20:34:23" ':' will be disappear
                # __value = ''.join(__list2[1].split(':')[1:]).strip().strip('"').strip()
                __value = ''.join(__list2[1].split(': ')[1:]).strip().strip('"').strip()
            except IndexError as _e:
                self.colorlog(_e, 'warn')
                self.colorlog(f'[{_line}] has no type or value.', 'warn')
                __type = '-'
                __value = '-'

            _data_tuple_list.append((__mib, __desc, __index, __type, __value))
        return _data_tuple_list


if __name__ == '__main__':
    pass

