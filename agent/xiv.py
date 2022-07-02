#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2022 by ZHANG ZHIJIE.
# All rights reserved.

# Last Modified Time: 4/9/22 18:34
# Author: ZHANG ZHIJIE
# Email: norvyn@norvyn.com
# Git: @n0rvyn
# File Name: xiv.py
# Tools: PyCharm

"""
check IBM XIV Storage status via snmp

"""
import os
import sys
import platform


_HOME_ = os.path.abspath(os.path.dirname(__file__))
_ROOT_ = os.path.abspath(os.path.join(_HOME_, '..'))
_LOG_PATH = os.path.join(_ROOT_, 'log')
os.mkdir(_LOG_PATH) if not os.path.exists(_LOG_PATH) else ''
_LOG_FILE = os.path.join(_LOG_PATH, 'agent.log')

sys.path.append(_ROOT_)
from console.snmpconsole import SnmpConsole

if platform.system().lower() == 'linux':
    PASSED = '\033[0;37mPassed\033[0m'
    FAILED = '\033[0;31mFailed\033[0m'
    NO_COLOR = 61
else:
    PASSED = 'Passed'
    FAILED = 'FAILED'
    NO_COLOR = 50


class XivSnmpConsole(SnmpConsole):
    def __init__(self, manage_ipaddr, MIBs=None, version=None, community=None, logfile=None, display=False, desc=None):
        self.manage_ipaddr = manage_ipaddr
        self.MIBs = MIBs if MIBs is not None else 'XIV-MIB'
        self.version = version if version is not None else '2c'
        self.community = community if community is not None else 'XIV'
        self.logfile = logfile if logfile is not None else _LOG_FILE
        self.xiv_snmp_args = f'-v{self.version} -c {self.community} -m {self.MIBs}'
        self.desc = desc if desc is not None else 'Unknown'

        self.PASSED = '\033[0;37mPasswd\033[0m'
        self.FAILED = '\033[0;31mFailed\033[0m'

        SnmpConsole.__init__(self, self.manage_ipaddr, self.xiv_snmp_args, logfile=self.logfile, display=display)

    def xiv_disk_status(self):
        _oid = 'xivFailedDisks'
        _return = self.snmpwalk(_oid).split('INTEGER:')[-1].strip()
        return PASSED if _return == '0' else FAILED

    def xiv_machine_status(self):
        _oid = 'xivMachineStatus'
        _return = self.snmpwalk(_oid).split('STRING:')[-1].strip()
        return PASSED if _return == '"Full Redundancy"' else FAILED

    def xiv_soft_utilization(self):
        _oid = 'xivUtilizationSoft'
        _return = self.snmpwalk(_oid).split('Gauge32:')[-1].strip()
        return f'{_return}%'

    def xiv_hard_utilization(self):
        _oid = 'xivUtilizationHard'
        _return = self.snmpwalk(_oid).split('Gauge32:')[-1].strip()
        return f'{_return}%'

    def xiv_interface_status(self):
        _oid = 'xivIfStatus'
        _return = self.snmpwalk_format(_oid)
        _failed_ifs = ''
        for _mib, _desc, _index, _type, _value in _return:
            if _value != 'OK' and _value != 'Ready':
                # maybe here is the reason what cause XIV Interface Verify always failed. == 'OK' not '"OK"'
                _failed_ifs += f'|[{_desc}{_index}][{_value}]'

        # ('XIV-MIB', 'xivIfStatus', '1004', 'STRING', '"OK"')
        # xivIfIOPS
        return PASSED if _failed_ifs == '' else f'{FAILED} [{_failed_ifs}]'

    def xiv_pm(self):
        print('\n', '=' * 80, sep='')
        print('-' * 32, f'{self.manage_ipaddr:^16s}', '-' * 32, sep='')

        prompt = 'XIV Machine Description'
        desc = self.desc
        print(f'{prompt:<30s}{desc:.>50s}')

        prompt = 'XIV Disk Status'
        disk_stat = self.xiv_disk_status()
        print(f'{prompt:<30s}{disk_stat:.>{NO_COLOR}s}')

        prompt = 'XIV Machine Status'
        machine_stat = self.xiv_machine_status()
        print(f'{prompt:<30s}{machine_stat:.>{NO_COLOR}s}')

        prompt = 'XIV Soft Utilization'
        soft_uti = self.xiv_soft_utilization()
        print(f'{prompt:<30s}{soft_uti:.>50s}')

        prompt = 'XIV Hard Utilization'
        hard_uti = self.xiv_hard_utilization()
        print(f'{prompt:<30s}{hard_uti:.>50s}')

        prompt = 'XIV Interface Status'
        if_stat = self.xiv_interface_status()
        print(f'{prompt:<30s}{if_stat:.>{NO_COLOR}s}')


def pm_xiv_all(xiv_list):
    for _xiv in xiv_list:
        try:
            _ip, _desc = _xiv  # if more attr needed, append here
            xiv_consl = XivSnmpConsole(_ip, desc=_desc)
            xiv_consl.xiv_pm()
        except KeyError:
            pass


if __name__ == '__main__':
    XIV = ['192.168.1.1', '192.168.1.2']
    pm_xiv_all(XIV)

