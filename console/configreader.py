#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2021 by ZHANG ZHIJIE.
# All Right Reserved.

# Last Modified Time: 2022/4/13 08:
# Author: ZHANG ZHIJIE
# Email: beyan@beyan.me
# File Name: configreader.py
# Tools: PyCharm

"""
---Read configuration from files---
"""
from yaml import safe_load
import os
import subprocess
try:
    import busybox
except ModuleNotFoundError:
    from . import busybox

_HOME_ = os.path.abspath(os.path.dirname(__file__))
_ROOT_ = os.path.abspath(os.path.join(_HOME_, '..'))
_CONFIG_DIR_ = os.path.join(_ROOT_, 'config')
_LOG_PATH_ = os.path.join(_ROOT_, 'log')
_LOG_FILE_ = os.path.join(_LOG_PATH_, 'console.log')

_CONFIG_DIR_TEST_ = os.path.join(_CONFIG_DIR_, 'devtest')
_CONFIG_DIR_PRO_ = os.path.join(_CONFIG_DIR_, 'production')

_xiv_config_name_ = 'xiv.yaml'
_switch_config_name_ = 'switch.yaml'
_hw_str_config_name_ = 'huaweistorage.yaml'


class ConfigReader(object):
    def __init__(self, production=False, display=False):
        self.config_dir = _CONFIG_DIR_TEST_ if production is not True else _CONFIG_DIR_PRO_

        self.xiv_config = os.path.join(self.config_dir, _xiv_config_name_)
        self.hw_str_config = os.path.join(self.config_dir, _hw_str_config_name_)
        self.switch_config = os.path.join(self.config_dir, _switch_config_name_)

        self.class_name = __class__.__name__
        self.logger_prefix = 'Config Reader'
        self._log_file = _LOG_FILE_
        self.display = display

        self.hw_str_config_keys = ['id', 'description', 'ipaddr', 'username', 'password', 'obs']

    def _colorlog(self, msg=None, level=None):
        msg = '' if msg is None else msg
        level = 'debug' if level is None else level
        name = self.class_name + ' {:<14s}'.format(self.logger_prefix)
        colorlogger = busybox.ColorLogger(name, self._log_file, display=self.display)
        busybox.log_cleaner(self._log_file, 50)
        colorlogger.colorlog(msg, level)

    def _is_ip_reachable(self, ipaddr_list: list, port=22, udp=False, fast=False):
        """
        :param ipaddr_list: one or more ip address[es]
        :param port: port to be tested if open or closed, 22 by default
        :param udp: set 'True' to test a UDP port like snmp port '161'
        :return: ip address passed the test or None if all addresses failed.
        """
        if fast:
            return ipaddr_list[0]

        if ipaddr_list is None or ipaddr_list == ['']:
            self._colorlog('read IP address list from configuration failed', 'critical')
            return None

        for _ip in ipaddr_list:
            if udp:
                self._colorlog(f'udp port test enable for address [{_ip}]', 'info')
                _test_command = f'nc -v -z -w1 -u {_ip} {port}'
            else:
                _test_command = f'nc -v -z -w1 {_ip} {port}'

            _return = subprocess.getstatusoutput(_test_command)[0]
            if _return == 0:
                self._colorlog(f'IP address [{_ip}] port [{port}] is open', 'info')
                return _ip
            else:
                self._colorlog(f'IP address [{_ip}] port [{port}] is closed', 'warn')
                return None

    def read_hw_str(self, hw_str_config=None):
        _config = self.hw_str_config if hw_str_config is None else hw_str_config
        # _keys = ['id', 'ipaddrs', 'username', 'password', 'snmp_args']
        output = []

        with open(_config, 'r') as f:
            _data = safe_load(f)
            self._colorlog(f'Load yaml config file [{_config}]', 'info')

            for _line in _data:
                try:
                    _id, _ipaddrs = _line['id'], _line['ipaddrs']
                    self._colorlog(f'read addresses {_ipaddrs}', 'debug')
                    _ipaddr = self._is_ip_reachable(_ipaddrs, fast=True)
                    self._colorlog(f'return reachable address [{_ipaddr}]', 'debug')

                except KeyError:
                    self._colorlog(f'read id or addresses failed from line [{_line}]', 'debug')
                    continue

                try:
                    _username, _password = _line['username'], _line['password']
                except KeyError:
                    self._colorlog(f'read username or password for address [{_line}] failed', 'warn')
                    _username = _password = None

                try:
                    _desc = _line['description']
                except KeyError:
                    _desc = None

                try:
                    _obs = _line['obs']
                except KeyError:
                    _obs = False

                try:
                    _snmp_args = _line['snmp_args']
                    _ipaddr = self._is_ip_reachable(_ipaddrs, port=161, udp=True, fast=True)
                except KeyError:
                    self._colorlog(f'read snmp args failed from line [{_line}]', 'debug')
                    _snmp_args = None

                if _ipaddr is not None:
                    output.append((_ipaddr, _username, _password, _snmp_args, _desc))
        return output

    def read_xiv(self, xiv_config=None):
        _config = self.xiv_config if xiv_config is None else xiv_config
        _keys = ['id', 'ipaddrs']
        output = []

        with open(_config, 'r') as f:
            _data = safe_load(f)
            for _line in _data:
                try:
                    _id, _ipaddrs = _line['id'], _line['ipaddrs']
                    _ipaddr = self._is_ip_reachable(_ipaddrs, port=161, udp=True, fast=True)
                except KeyError:
                    continue

                try:
                    _desc = _line['description']
                except KeyError:
                    _desc = None

                """try:
                    _snmp_args = _line['snmp_args']
                except KeyError:
                    _snmp_args = ''"""

                if _ipaddr is not None:
                    output.append((_ipaddr, _desc))
        return output

    def read_switch(self, switch_config=None):
        """
        Args:
            switch_config: switch configuration formatted as YAML

        Returns:
            [list: tuple()]
            [(ipaddr, username, password, ssh_port, fid, snmp_args)]
        """
        _config = self.switch_config if switch_config is None else switch_config
        # _keys = ['id', 'ipaddrs', 'username', 'password', 'snmp_args', 'context']
        output = []

        with open(_config, 'r') as f:
            _data = safe_load(f)
            for _line in _data:
                try:
                    _id, _ipaddrs = _line['id'], _line['ipaddrs']
                    _ipaddr = self._is_ip_reachable(_ipaddrs, fast=True)
                    # _ipaddr = _ipaddrs[0]
                except KeyError:
                    continue

                try:
                    _username, _password = _line['username'], _line['password']
                except KeyError:
                    _username = _password = None

                try:
                    _ssh_port = int(_line['port'])
                except KeyError:
                    _ssh_port = None
                except ValueError:
                    _ssh_port = None

                try:
                    _snmp_args = _line['snmp_args']
                    _ipaddr = self._is_ip_reachable(_ipaddrs, port=161, udp=True, fast=True)
                except KeyError:
                    self._colorlog(f'detected snmp args, but port 161 not opened.')
                    _snmp_args = None

                try:
                    _desc = _line['description']
                except KeyError:
                    _desc = None

                if _ipaddr is None:
                    continue

                try:
                    _vf_ids = _line['context']
                    _snmp_args_vf = [f'{_snmp_args} -n VF:{_id}' for _id in _vf_ids]
                    output.append((_ipaddr, _username, _password, _ssh_port, _snmp_args_vf, _desc))

                except KeyError:
                    output.append((_ipaddr, _username, _password, _ssh_port, [_snmp_args], _desc))

        # tuple(ip, username, password, port, vf_id, snmp_args)
        return output


if __name__ == '__main__':
    cr = ConfigReader()
    # cr.read_hw_str()

    # print(cr.read_xiv())
    for _sw_info in cr.read_switch():
        print(_sw_info)

