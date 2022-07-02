#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2022 by ZHANG ZHIJIE.
# All rights reserved.

# Last Modified Time: 4/9/22 19:31
# Author: ZHANG ZHIJIE
# Email: norvyn@norvyn.com
# Git: @n0rvyn
# File Name: huawei_str.py
# Tools: PyCharm

"""
---Huawei OceanStor Serial Storage Preventive Maintenance Script---
"""
import os
import sys
import threading
import platform

_HOME_ = os.path.abspath(os.path.dirname(__file__))
_ROOT_ = os.path.abspath(os.path.join(_HOME_, '..'))
_LOG_PATH_ = os.path.join(_ROOT_, 'log')
os.mkdir(_LOG_PATH_) if not os.path.exists(_LOG_PATH_) else ''
_LOG_FILE_ = os.path.join(_LOG_PATH_, 'agent.log')
sys.path.append(_ROOT_)

from console.sshconsole import SshConsole
from console.snmpconsole import SnmpConsole

if platform.system().lower() == 'linux':
    PASSED = '\033[0;37mPassed\033[0m'
    FAILED = '\033[0;31mFailed\033[0m'
    UNKNOWN = '\033[0;33mN/A\033[0m'
    NO_COLOR = 61
else:
    PASSED = 'Passed'
    FAILED = 'FAILED'
    UNKNOWN = 'N/A'
    NO_COLOR = 50


class HwSnmpConsole(SnmpConsole):
    def __init__(self, agent, *args, display=False, desc=None):
        # self.event_oid = '1.3.6.1.4.1.2011.2.251.20.1.1.1'  # too long to display
        self.event_oid = '1.3.6.1.4.1.2011.2.251.20.1.1.1.1.4'
        self.event_date_oid = '1.3.6.1.4.1.2011.2.251.20.1.1.1.1.8'
        self.agent = agent
        self.args = ','.join(args)
        # self.args = ''.args
        self.desc = desc if desc is not None else 'Undefined'
        self.events_line = ''

        SnmpConsole.__init__(self, self.agent, self.args, display=display, logfile=_LOG_FILE_)

    def snmpwalk_event(self):
        _events = self.snmpwalk(self.event_oid)
        _e_date = [_line[4] for _line in self.snmpwalk_format(self.event_date_oid)]

        _no_event_output_ends = 'No Such Object available on this agent at this OID'

        if _events.endswith(_no_event_output_ends):
            return PASSED

        else:
            _events = self.snmpwalk_format(self.event_oid)
            try:
                for _snmp_line in _events:
                    _type = _snmp_line[3]
                    _event_string = _snmp_line[4]

                    _id = _events.index(_snmp_line)

                    try:
                        _event_time = _e_date[_id]
                    except IndexError:
                        _event_time = 'N/A'

                    if _type.upper() == 'STRING':
                        self.events_line += f'|{_event_time:<20s} {_event_string:<58s}|\n'

                self.events_line.rstrip('\n')

            except KeyError:
                pass

            return FAILED

    def pm(self):
        print('-' * 80, sep='')
        # print('-' * 42, f'{self.agent:^16s}', '-' * 42, sep='')
        prompt = f'Huawei Storage [{self.agent:<13s}] Event Status'
        # if self.snmpwalk_event() is None:
        #     _event_stat = '\033[0;37mPassed\033[0m'
        # else:
        #     _event_stat = '\033[0;31mFailed\033[0m'
        print(f'{prompt:<40s}{self.event_stat:.>48s}')


class HuaweiOceanStorConsole(SshConsole):
    def __init__(self, host, username, password, display=True, timeout=10, desc=None, snmp_args=None, obs=False):
        self.host = host
        self.username = username
        self.password = password
        self.timeout = timeout
        self.display = display
        self.desc = desc if desc is not None else 'Undefined'
        self.obs = obs

        self.snmp_consl = HwSnmpConsole(self.host, snmp_args, display=self.display)
        self.snmp_event = None

        self.alarm_lines = ''

        self.sys_info = {}
        SshConsole.__init__(self, self.host, display=self.display, logfile=_LOG_FILE_)

    def connect_storage(self):
        if self.obs:
            return False

        self.ssh_connect(hostname=self.host, username=self.username, password=self.password)
        self.getoutput('change cli more_enabled=no')
        return True

    @staticmethod
    def format_hw_cli_output(_output_list, _key_line_starts, *_ignore_line_starts):
        _ignore_line_starts = ('-', '#show')
        _part_len = _main_key = None
        _keys = _values = []

        output_dict = {}

        # fetch length of each key_value pairs
        for _line in _output_list:
            if _line.strip().startswith('-'):
                _part_len = [len(_i) for _i in _line.strip().split()]
        if not _part_len:
            return output_dict

        # fetch keys from output, strings like: ID, Health Status...
        for _line in _output_list:
            # change from 0 to 2
            _start_pos = 2
            # _line = _line.strip()
            if _line.strip().startswith(_key_line_starts):
                for _len in _part_len:
                    _key = _line[_start_pos:_start_pos + _len]
                    _keys.append(_key.strip())
                    # _line = _line.replace(_key, '', 1).strip()
                    _line = _line.replace('  ', '', 1)
                    _line = _line.replace(_key, '', 1)

        # fetch values from output
        for _line in _output_list:
            _values = []
            # change from 0 to 2
            _start_pos = 2
            # _line = _line.strip()
            if not _line.strip().startswith(_ignore_line_starts) and not _line.strip().startswith(_key_line_starts):
                if not _line.strip():
                    continue
                for _len in _part_len:
                    _value = _line[_start_pos:_start_pos + _len]
                    _values.append(_value.strip())
                    # _line = _line.replace(_value, '', 1).strip()
                    _line = _line.replace('  ', '', 1)
                    _line = _line.replace(_value, '', 1)

                output_dict.update({_values[0]: {}})
                for _i in range(len(_values)):
                    try:
                        output_dict[_values[0]].update({_keys[_i]: _values[_i].strip()})
                    except IndexError:
                        continue
        return output_dict

    def show_alarm(self):
        _alarm = self.getoutput('show alarm')
        return self.format_hw_cli_output(_alarm, 'Sequence')

    def show_bbu(self):
        _bbu_info = self.getoutput('show bbu general')
        return self.format_hw_cli_output(_bbu_info, 'ID')

    def show_bbu_life(self):
        _bbu_life = self.getoutput('show bbu life')
        return self.format_hw_cli_output(_bbu_life, 'ID')

    def show_controller(self):
        _keys = ['Controller', 'Health Status', 'Running Status', 'CPU', 'Location',
                 'Role', 'Cache Capacity', 'CPU Usage(%)', 'Memory Usage(%)', 'Temperature(Celsius)',
                 'Voltage(V)', 'Software Version', 'PCB Version', 'SES Version', 'BMC Version',
                 'Logic Version', 'BIOS Version', 'All Temperatures(Celsius)']

        _ctrl_info_list = self.getoutput('show controller general')
        ctrl_info_dict = {_key: [] for _key in _keys}
        # ctrl_info_dict = {_key: '' for _key in _keys}
        for _line in _ctrl_info_list:
            try:
                _key, _value = _line.split(':')
                _key = _key.strip()
                _value = _value.strip()
            except ValueError:
                continue
            try:
                ctrl_info_dict[_key].append(_value)
                # ctrl_info_dict[_key] += '|' + _value
            except KeyError:
                continue
        return {'controller': ctrl_info_dict}

    def show_disks(self):
        _disk_info = self.getoutput('show disk general')
        return self.format_hw_cli_output(_disk_info, 'ID')

    def show_disk_domain(self):
        _disk_domain_info = self.getoutput('show disk_domain general')
        return self.format_hw_cli_output(_disk_domain_info, 'ID')

    def show_enclosure(self):
        _enclosure_info = self.getoutput('show enclosure')
        return self.format_hw_cli_output(_enclosure_info, 'ID')

    def show_exp_module(self):
        _exp_info = self.getoutput('show expansion_module')
        return self.format_hw_cli_output(_exp_info, 'ID')

    def show_fan(self):
        _fan_info = self.getoutput('show fan')
        return self.format_hw_cli_output(_fan_info, 'ID')

    def show_host(self):
        _host_info = self.getoutput('show host general')
        return self.format_hw_cli_output(_host_info, 'ID')

    def show_if(self):
        _if_info = self.getoutput('show interface_module')
        return self.format_hw_cli_output(_if_info, 'ID')

    def show_ps(self):
        _ps_info = self.getoutput('show power_supply')
        return self.format_hw_cli_output(_ps_info, 'ID')

    def show_system(self):
        # show system general
        keys = ['System Name', 'Health Status', 'Running Status', 'Total Capacity', 'SN', 'Location',
                'Product Model', 'Product Version', 'High Water Level(%)', 'Low Water Level(%)', 'WWN',
                'Time', 'Patch Version']
        # keys = ['System Name', 'Health Status', 'Running Status', 'Total Capacity', 'SN', 'Product Model']
        sys_info_dict = {_key: '' for _key in keys}
        _sys_info_list = self.getoutput('show system general')
        for _line in _sys_info_list:
            try:
                _key, _value = _line.split(':')
            except ValueError:
                continue
            _key = _key.strip()
            _value = _value.strip()
            try:
                sys_info_dict[_key] = _value
            except KeyError:
                continue
        return {'system': sys_info_dict}

    def show_storage_pool(self):
        _storage_pool_cap = self.getoutput('show storage_pool general')
        return self.format_hw_cli_output(_storage_pool_cap, 'ID')

    def show_fc_port(self):
        _fc_info = self.getoutput('show port fibre_module')
        return self.format_hw_cli_output(_fc_info, 'PortID')

    def fetch_capacity(self):
        total = 0
        free = 0

        def _trans_cap_to_TiB(_value_with_unit):
            _value_in_TB = ''
            try:
                if 'TB' in _value_with_unit:
                    return float(_value_with_unit.strip('TB'))
                if 'GB' in _value_with_unit:
                    return float(_value_with_unit.strip('GB')) / 1024
                if 'MB' in _value_with_unit:
                    return float(_value_with_unit.strip('MB')) / 1024 / 1024
                if 'KB' in _value_with_unit:
                    return float(_value_with_unit.strip('KB')) / 1024 / 1024
            except ValueError:
                return 0

        try:
            _storage_pool_info = self.sys_info['storage pool']
            for _id in _storage_pool_info:
                try:
                    _total, _free = _storage_pool_info[_id]['Total Capacity'], _storage_pool_info[_id]['Free Capacity']
                    _total, _free = _trans_cap_to_TiB(_total), _trans_cap_to_TiB(_free)
                    total += _total
                    free += _free
                except KeyError:
                    continue
        except KeyError:
            pass
        return f'{total:.3f}', f'{free:.3f}'

    def fetch_bbu_life(self):
        _bbu_lives = []
        try:
            _bbu_life_dict = self.sys_info['bbu_life']
            for _bbu in _bbu_life_dict:
                _bbu_lives.append(_bbu_life_dict[_bbu]['Remaining Lifetime(days)'])
        except KeyError:
            pass
        return tuple(_bbu_lives) if _bbu_lives != [] else ['N/A', 'N/A']

    def collect_info_all(self):
        if self.obs:
            return self.sys_info

        self.sys_info.update({'alarm': self.show_alarm()})
        self.sys_info.update({'bbu': self.show_bbu()})
        self.sys_info.update({'bbu_life': self.show_bbu_life()})
        self.sys_info.update({'controller': self.show_controller()})
        self.sys_info.update({'disks': self.show_disks()})
        self.sys_info.update({'disk_domain': self.show_disk_domain()})
        self.sys_info.update({'enclosure': self.show_enclosure()})
        self.sys_info.update({'exp_module': self.show_exp_module()})
        self.sys_info.update({'fan': self.show_fan()})
        self.sys_info.update({'host': self.show_host()})
        self.sys_info.update({'interface': self.show_if()})
        self.sys_info.update({'ps': self.show_ps()})
        self.sys_info.update({'system': self.show_system()})
        self.sys_info.update({'storage pool': self.show_storage_pool()})
        self.sys_info.update({'fc': self.show_fc_port()})

        return self.sys_info

    def fetch_snmp_event(self):
        self.snmp_event = self.snmp_consl.snmpwalk_event()
        return self.snmp_event

    def pm(self):
        def _check_status_from_sys_info(_module_key):
            _hel_key = 'Health Status'
            _hel_stat = ['Normal', ['Normal', 'Normal']]
            _run_key = 'Running Status'
            _run_stat = ['Running', 'Online', 'Link Up', 'Normal', ['Online', 'Online']]

            try:
                _module_info = self.sys_info[_module_key]

                # todo delete or keep, it's a question.
                if not _module_info and _module_key != 'alarm':
                    return UNKNOWN

                for _m in _module_info:
                    if _module_key == 'alarm':
                        _alarm_dict = [self.sys_info['alarm'][_l] for _l in self.sys_info['alarm']]
                        for _alarm in _alarm_dict:
                            self.alarm_lines += '{:<79s}|\n'.format(
                                '|' + _alarm['Occurred On'] + ' ' + _alarm['Name'])
                        if _module_info:
                            return FAILED
                        else:
                            return PASSED

                    _hel_value = _module_info[_m][_hel_key]
                    if _module_key == 'host':  # host only has key 'Health Status'
                        # once health status not equal to _heal_stat, return False.
                        if _hel_value not in _hel_stat:
                            _alarm_string = f'{_module_key} {_m} [{_hel_key} {_hel_value}]'
                            self.alarm_lines += '{:<79s}|\n'.format('|' + _alarm_string)
                            return FAILED

                    _run_value = _module_info[_m][_run_key]
                    if _hel_value not in _hel_stat or _run_value not in _run_stat:
                        _alarm_string = f'{_module_key} {_m} [{_hel_key} {_hel_value}] [{_run_key} {_run_value}]'
                        self.alarm_lines += '{:<79s}|\n'.format('|' + _alarm_string)
                        return FAILED
                return PASSED
            except KeyError:
                return FAILED

        def _print_module_status(_module_key):
            _prompt = f'Checking Stat of {_module_key}'
            print(f'{_prompt:<30s}{_check_status_from_sys_info(_module_key):.>{NO_COLOR}s}')

        def _print_events():
            if len(self.alarm_lines.strip().strip('\n')) != 0:
                print('-' * 80)
                print(self.alarm_lines.rstrip('\n'))
                print('-' * 80)

        def _print_snmp_events():
            if len(self.snmp_consl.events_line.strip().strip('\n')) != 0:
                print('-' * 80)
                print(self.snmp_consl.events_line.rstrip('\n'))
                print('-' * 80)

        """
        BEGINNING of PREVENTIVE MAINTENANCE
        """
        print('\n', '=' * 80, sep='')
        print('-' * 32, f'{self.host:^16s}', '-' * 32, sep='')
        # print description
        prompt = 'Storage Description'
        desc = self.desc
        print(f'{prompt:<30s}{desc:.>50s}')

        # storage events status
        prompt = f'Checking Stat of Events(snmp)'
        print(f'{prompt:<30s}{self.snmp_event:.>{NO_COLOR}s}')

        # Huawei OBS does not offer CLI show command
        # If Huawei storage CLI not connected, following checking not necessary.
        if self.obs or not self.connected:
            _print_snmp_events()
            return True

        # calculate capacity of storage
        prompt = 'Total/free capacity(TiB)'
        cap = '|'.join(self.fetch_capacity())
        print(f'{prompt:<30s}{cap:.>50s}')

        # check BBU lifetime
        prompt = 'BBU Remaining Lifetime(days)'
        bbu_life = '|'.join(self.fetch_bbu_life())
        print(f'{prompt:<30s}{bbu_life:.>50s}')

        # Check module status which has key 'Health Status' & 'Running Status'
        _module_keys = ['bbu', 'disks', 'disk_domain', 'enclosure', 'fan',
                        'interface', 'ps', 'storage pool', 'fc', 'alarm',
                        'system', 'controller']
        for _key in _module_keys:
            _print_module_status(_key)

        # if len(self.alarm_lines.strip().strip('\n')) != 0:
        #     print('-' * 80)
        #     print(self.alarm_lines.rstrip('\n'))
        #     print('-' * 80)
        #
        # if len(self.snmp_consl.events_line.strip().strip('\n')) != 0:
        #     print('-' * 80)
        #     print(self.snmp_consl.events_line.rstrip('\n'))
        #     print('-' * 80)
        _print_events()
        _print_snmp_events()


def pm_all_hw_storage(huawei_storages, display=False, multi_thread=False):
    if multi_thread:
        _object_list = []
        _snmp_obj_list = []

        def _pm_all_target(_host, _username, _password, _snmp_args, _desc):
            hw_consl = HuaweiOceanStorConsole(host=_host,
                                              username=_username,
                                              password=_password,
                                              desc=_desc,
                                              display=display,
                                              snmp_args=_snmp_args)
            if _password is not None:
                hw_consl.connect_storage()
                hw_consl.collect_info_all()

            if _snmp_args is not None:
                hw_consl.fetch_snmp_event()

            _object_list.append(hw_consl)

            # if _snmp_args:
            #     hw_snmp_consl = HwSnmpConsole(_host, ','.join(_snmp_args), display=display)
            #     _snmp_obj_list.append(hw_snmp_consl)

        threads = [threading.Thread(target=_pm_all_target, args=_str) for _str in huawei_storages]
        [t.start() for t in threads]
        [t.join() for t in threads]

        # [_hw_snmp_consl.pm() for _hw_snmp_consl in _snmp_obj_list]
        [_hw_consl.pm() for _hw_consl in _object_list]

    else:
        for _str_info in huawei_storages:
            try:
                _host, _user, _pass, _snmp_args, _desc = _str_info

                hw_console = HuaweiOceanStorConsole(host=_host, username=_user, password=_pass,
                                                    desc=_desc, snmp_args=_snmp_args, display=display)

                if _pass is not None:
                    hw_console.connect_storage()
                    hw_console.collect_info_all()

                if _snmp_args is not None:
                    hw_console.fetch_snmp_event()

                hw_console.pm()

            except ValueError:
                pass


if __name__ == '__main__':
    storages = [
        ('192.168.1.1', 'admin', 'admin', '-v3 -u user'),
    ]

    pm_all_hw_storage(storages)
