#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2022 by ZHANG ZHIJIE.
# All rights reserved.

# Last Modified Time: 4/9/22 18:35
# Author: ZHANG ZHIJIE
# Email: norvyn@norvyn.com
# Git: @n0rvyn
# File Name: switch.py
# Tools: PyCharm

"""
---preventive maintenance for Brocade-based San Switch---
"""
import os
import sys
import math
import subprocess
import threading
import platform

_HOME_ = os.path.abspath(os.path.dirname(__file__))
_ROOT_ = os.path.abspath(os.path.join(_HOME_, '..'))
_LOG_PATH = os.path.join(_ROOT_, 'log')
_DATA_PATH = os.path.join(_ROOT_, 'data')
os.mkdir(_LOG_PATH) if not os.path.exists(_LOG_PATH) else ''
_LOG_FILE = os.path.join(_LOG_PATH, 'agent.log')

# define the low & high level for SFP
TEMP_LOW = 0
TEMP_HIGH = 75
CURR_LOW = 2
CURR_HIGH = 11.5
VOLT_LOW = 3100
VOLT_HIGH = 3500
RX_LOW = 32
RX_HIGH = 790
TX_LOW = 200
TX_HIGH = 790

# sys.path.append(_ROOT_)
sys.path.insert(0, _ROOT_)

from console import SnmpConsole
from console import SshConsole
from console import SwitchLogDecoder

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


class SwitchSshConsole(SshConsole):
    def __init__(self, manage_ipaddr, username=None, password=None, port=None,
                 datafile=None, logfile=None, vf_id=None, display=True):
        """
        Args:
            manage_ipaddr: managed IP address of San Switch
            username: user for login via SSH
            password: password for user
            port: SSH port, default is 22
            datafile: file path for storing switch command output
            logfile: path of log
            vf_id: virtual fiber ID, set to None if Switch is non-VF switch
            display: set True or False to whether display log to stdout or not
        """
        self.manage_ipaddr = manage_ipaddr
        self.username = 'admin' if username is None else username
        self.password = password
        self.port = 22 if port is None else port

        self.virtual_fabric = False
        self.vf_id = str(vf_id) if vf_id is not None else 'FID0'
        self.vf_id = f'FID{self.vf_id}' if self.vf_id.isnumeric() else self.vf_id

        self.datafile = os.path.join(_DATA_PATH, f'sw_{manage_ipaddr}.log') if datafile is None else datafile
        self.logfile = _LOG_FILE if logfile is None else logfile

        self.decoder = SwitchLogDecoder(datafile='', display=display)
        self.switch_detail = self.decoder.detail
        self.error_msg = []

        self.fir_ver_val = self.sys_stat_val = self.sensor_stat_val = self.sfp_stat_val = None

        SshConsole.__init__(self, self.manage_ipaddr, logfile=self.logfile, display=display)

    # deprecated
    def is_switch_virtual(self):
        _return = self.getstatusoutput('lscfg --show')[0]
        self.virtual_fabric = True if _return == 0 else False
        return self.virtual_fabric

    def write_datafile(self, data_lines):
        """
        write string list to file
        """
        try:
            _data = '\n'.join(data_lines)

            with open(self.datafile, 'a+') as f:
                self.colorlog(f'write data lines to file [{self.datafile}]', 'info')
                f.write(_data)
                f.flush()
            return True

        except TypeError as _e:
            self.colorlog(_e, 'error')

        except FileNotFoundError as _e:
            self.colorlog(_e, 'error')

        self.colorlog('write data to file error', 'error')
        return False

    def conn_default_vf(self):
        return self.ssh_connect(hostname=self.manage_ipaddr, username=self.username, password=self.password)

    def get_fid(self):
        return self.getoutput('switchshow | grep "LS Attributes"')

    def show_basic_cfg_and_sensors(self, log=False, vf_id=None):
        data = []
        for _command in ['fanshow', 'psshow', 'slotshow', 'tempshow', 'sensorshow',
                         'ipaddrshow', 'firmwareshow', 'fabricshow', 'memshow', 'hashow']:
            _output = self.getoutput(_command)

            if self.virtual_fabric:
                _prompt = f'SWITCH:{self.vf_id}:{self.username}> {_command}'
            else:
                _prompt = f'SWITCH:{self.username}> {_command}'

            data.append(_prompt)
            data.extend(_output)

            if _command == 'fanshow':
                self.decoder.fanshow_decode(_output, self.vf_id)

            elif _command == 'psshow':
                self.decoder.psshow_decode(_output, self.vf_id)

            elif _command == 'slotshow':
                self.decoder.slotshow_decode(_output, self.vf_id)

            elif _command == 'tempshow':
                self.decoder.tempshow_decode(_output, self.vf_id)

            elif _command == 'sensorshow':
                self.decoder.sensorshow_decode(_output, self.vf_id)

            elif _command == 'ipaddrshow':
                self.decoder.ipaddrshow_decode(_output, self.vf_id)

            elif _command.startswith('firmwareshow'):
                self.decoder.firmwareshow_decode(_output, self.vf_id)

            elif _command.startswith('fabricshow'):
                self.decoder.fabricshow_decode(_output, self.vf_id)

        if log is True:
            self.write_datafile(data)

        return _output

    def getcontext(self):
        _fids = []
        try:
            # todo 1st line output of 'lscfg --show' may be '', try 2rd.
            _fids = [_fid.split('(')[0] for _fid in self.getoutput('lscfg --show')[0].split(':')[-1].split()]
        except IndexError as _e:
            self.colorlog(_e, 'critical')
            self.colorlog('fetch vf id from output failed', 'critical')

        return _fids

    def setcontext(self, vf_id):
        vf_id = vf_id.strip('FID')
        _output = self.getoutput(f'setcontext {vf_id}')
        """
        command 'setcontext' can not be executed via remote non-tty terminal
        """

        _context_error = 'FID not associated with a switch.'
        _context_not_exist = 'lscfg_util: requires VF to be enabled.'

        if vf_id == '0' or not _output:
            return True
        return False

    def list_port_indexes(self):
        _output = self.getoutput('switchshow')
        port_indexes = []
        for _line in _output:
            if _line.strip() == '':
                continue

            _index = _line.split()[0]

            if _line.startswith('LS Attributes'):
                pass

            if _index.isnumeric():
                self.colorlog('switchshow port index line detected', 'debug')
                self.colorlog(f'line: [{_line}]', 'debug')
                port_indexes.append(_index)
        return port_indexes

    def show_vf_port_detail(self):
        _output = self.getoutput('sfpshow -all')
        self.decoder.sfpshow_all_decode(_output, self.vf_id)

        # for _port_index in self.list_port_indexes():
        #     _command = f'portshow -i {_port_index}'
        #     _output = self.getoutput(_command)
        #     self.decoder.portshow_decode(_output, self.vf_id)
        # switchstatusshow

        _output = self.getoutput('switchshow')
        self.decoder.switchshow_decode(_output, self.vf_id)

    def show_vf_cfg_detail(self):
        _output = []
        for _command in ['switchshow', 'sfpshow -all', 'zoneshow', 'trunkshow',
                         'islshow', 'cfgshow', 'cfgactvshow', 'alishow']:
            _output.extend(self.getoutput(_command))

        for _port_index in self.list_port_indexes():
            _command = f'portshow -i {_port_index}'
            _output.extend(self.getoutput(_command))

        return _output

    def collect_data_to_file(self):
        _data = self.show_basic_cfg_and_sensors()

        _fids = [self.vf_id] if self.vf_id is not None else self.getcontext()

        for _fid in _fids:
            self.setcontext(vf_id=_fid) if _fid is not None else ''
            # _data.append(self.show_vf_detail())
            _data.extend(self.show_vf_detail())

        self.write_datafile(_data)

    def version(self):
        try:
            _ver = self.switch_detail[self.vf_id]['switch']['firmware']['Primary']
        except KeyError:
            _ver = UNKNOWN
        return _ver

    def sys_stat(self):
        try:
            _stat = self.switch_detail[self.vf_id]['switch']['switchState']

            if _stat == 'Online':
                return PASSED
        except KeyError:
            pass

        return FAILED

    def sensor_stat(self):
        try:
            sensor_dict = self.switch_detail[self.vf_id]['sensor']
        except KeyError:
            return FAILED

        if sensor_dict == {}:
            return FAILED

        for _type in sensor_dict:
            sensor_stat_dict = sensor_dict[_type]
            for _sensor in sensor_stat_dict:
                try:
                    _stat = sensor_stat_dict[_sensor]['state']
                    if _stat.upper() != 'OK':
                        self.error_msg.append(tuple(sensor_stat_dict[_sensor].values()))
                        return FAILED

                except KeyError:
                    pass

        return PASSED

    def port_sfp_stat(self):
        try:
            sfp_detail = self.switch_detail[self.vf_id]['port']
        except KeyError:
            return FAILED

        if sfp_detail == {}:
            return FAILED

        _return = PASSED

        for _port in sfp_detail:
            # 'Temperature': 61.0, 'Current': 8.52, 'Voltage': 3334.2, 'RX Power': '2.7', 'TX Power': '524.8'
            try:
                _temp = float(sfp_detail[_port]['Temperature'])
                _curr = float(sfp_detail[_port]['Current'])
                _vol = float(sfp_detail[_port]['Voltage'])
                _rx_power = float(sfp_detail[_port]['RX Power'])
                _tx_power = float(sfp_detail[_port]['TX Power'])

                _state = sfp_detail[_port]['State']
                _proto = sfp_detail[_port]['Proto']

                _name = f"""{sfp_detail[_port]['Slot']}/{sfp_detail[_port]['Port']}"""
            except ValueError:
                continue
            except KeyError:
                continue

            if TEMP_LOW < _temp < TEMP_HIGH \
                    and CURR_LOW < _curr < CURR_HIGH \
                    and VOLT_LOW < _vol < VOLT_HIGH \
                    and RX_LOW < _rx_power < RX_HIGH \
                    and TX_LOW < _tx_power < TX_HIGH:
                continue

            if _state.lower() in ['no_module', 'no_light']:
                continue

            _state = f'\033[31m{_state:<10s}\033[0m' if _state != 'Online' else f'{_state:<10s}'
            _temp = f'\033[31m{_temp:>5.1f}^C\033[0m' if _temp <= TEMP_LOW or _temp >= TEMP_HIGH else f'{_temp:>5.1f}^C'
            _curr = f'\033[31m{_curr:>5.2f}mA\033[0m' if _curr <= CURR_LOW or _curr >= CURR_HIGH else f'{_curr:>5.2f}mA'
            _vol = f'\033[0;31m{_vol:>7.1f}mV \033[0m' if _vol <= VOLT_LOW or _vol >= VOLT_HIGH else f'{_vol:>7.1f}mV '
            _rx_power = f'\033[31m{_rx_power:>7.1f}ruW\033[0m' if _rx_power <= RX_LOW or _rx_power >= RX_HIGH else f'{_rx_power:>7.1f}ruW'
            _tx_power = f'\033[31m{_tx_power:>7.1f}tuW\033[0m' if _tx_power <= TX_LOW or _tx_power >= TX_HIGH else f'{_tx_power:>7.1f}tuW'

            _return = FAILED
            self.error_msg.append(f'Port{_port:<4s}{_name:<8s}{_state}'
                                  f'{_temp}'
                                  f'{_curr}'
                                  f'{_vol}'
                                  f'{_rx_power}'
                                  f'{_tx_power} '
                                  f'{_proto}')

        return _return

    def fetch_pm_values(self):
        """
        :return: Nothing

        no print, for backend executing in Threading
        """
        self.conn_default_vf()
        self.show_basic_cfg_and_sensors()
        self.show_vf_port_detail()

        self.fir_ver_val = self.version()
        self.sys_stat_val = self.sys_stat()
        self.sensor_stat_val = self.sensor_stat()
        self.sfp_stat_val = self.port_sfp_stat()

    def pm(self):
        print('\n', '=' * 80, sep='')
        print('-' * 30, f'{self.manage_ipaddr:^14s}{self.vf_id:^6s}', '-' * 30, sep='')
        # self.conn_default_vf()
        # self.show_basic_cfg_and_sensors()
        # self.show_vf_port_detail()

        # firmware version
        prompt = 'Switch Firmware Version'
        # fir_ver = self.version()
        fir_ver = self.fir_ver_val
        print(f'{prompt:<30s}{fir_ver:.>50s}')

        prompt = 'Switch System State'
        # sys_stat = self.sys_stat()
        sys_stat = self.sys_stat_val
        print(f'{prompt:<30s}{sys_stat:.>{NO_COLOR}}')

        # sensor state
        prompt = 'Switch Sensor State'
        # sensor_stat = self.sensor_stat()
        sensor_stat = self.sensor_stat_val
        print(f'{prompt:<30s}{sensor_stat:.>{NO_COLOR}s}')

        # sfp state
        prompt = 'Switch Port&SFP State'
        # sfp_stat = self.port_sfp_stat()
        sfp_stat = self.sfp_stat_val
        print(f'{prompt:<30s}{sfp_stat:.>{NO_COLOR}s}')

        # display error messages to the monitor
        print('-' * 80)
        for line in self.error_msg:
            print(line)
        print('-' * 80)

        # # CP State
        # prompt = 'Switch CP State'
        # cp_stat = self.cp_stat()
        # print(f'{prompt:<30s}{cp_stat:.>{NO_COLOR}s}')


class SwitchSnmpConsole(SnmpConsole):
    def __init__(self,
                 manage_ipaddr,
                 *snmp_args,
                 vf_id=None,
                 desc=None,
                 display=True):
        self.manage_ipaddr = manage_ipaddr
        self.vf_id = f'FID{vf_id}' if vf_id is not None else 'FID0'
        self.desc = desc if desc is not None else 'Unknown'

        self.snmp_args = ','.join(snmp_args)

        self.BaseOid = '1.3.6.1.4.1.1588.2.1.1.1'

        # system firmware version
        self.fir_ver_val = None
        # system state
        self.sys_stat_val = None
        # sensor state
        self.sensor_stat_val = None
        # fru state
        self.fru_stat_val = None
        # CP State
        self.cp_stat_val = None
        # port state
        self.port_stat_val = None

        self.error_msg = []

        SnmpConsole.__init__(self, self.manage_ipaddr, self.snmp_args, logfile=_LOG_FILE, display=display)

    def decode_index(self, index_string_dict, index, error_key=None):
        """
        Trans snmp value from number to string
        :param index_string_dict:
        :param index:
        :param error_key:
        :return:
        """
        error_key = 'NULL' if error_key is None else error_key
        try:
            return index_string_dict[index]
        except KeyError:
            self.colorlog(f'SNMP [{error_key}] decode failed, index not defined!', 'warn')
            # self.colorlog(f'index dict [{index_string_dict}]', 'warn')
            self.colorlog(f'index value [{index}]', 'warn')
            # return index
            return None

    def snmpwalk_values(self, oid):
        return [_line[4] for _line in self.snmpwalk_format(oid)]

    def snmpwalk_index_value(self, oid):
        return [(_line[2], _line[4]) for _line in self.snmpwalk_format(oid)]

    def snmpwalk_value1(self, oid):
        return self.snmpwalk_format(oid)[0][4]

    def events(self, no_events=0):
        _return = []
        _no_events = 5 if no_events == 0 else no_events
        _base_oid = '1.3.6.1.4.1.1588.2.1.1.1.8.5.1'

        # _index = self.snmpwalk_format(f'{_base_oid}.1')[0:_no_events]
        _time = self.snmpwalk_values(f'{_base_oid}.2')[0:_no_events]
        _level = self.snmpwalk_values(f'{_base_oid}.3')[0:_no_events]
        _repeat = self.snmpwalk_values(f'{_base_oid}.4')[0:_no_events]
        _desc = self.snmpwalk_values(f'{_base_oid}.5')[0:_no_events]
        _vfid = self.snmpwalk_values(f'{_base_oid}.6')[0:_no_events]

        _level_code = {'1': 'critical', '2': 'error', '3': 'warning', '4': 'info', '5': 'debug'}

        for _i in range(_no_events):
            try:
                _line = f'{_time[_i]} ' \
                        f'[{self.decode_index(_level_code, _level[_i], "event level")}] ' \
                        f'[repeat: {_repeat[_i]} times]' \
                        f'[{_desc[_i]}]' \
                        f'[vfid: {_vfid[_i]}]'
                _return.append(_line)
            except IndexError:
                continue
        return _return

    def firmware_version(self):
        _oid = '1.3.6.1.4.1.1588.2.1.1.1.1.6'
        _value = self.snmpwalk_value1(_oid)
        return _value if _value != '-' else 'N/A'

    def sys_stat(self):
        _oid = '1.3.6.1.4.1.1588.2.1.1.1.1.7'
        _value = self.snmpwalk_value1(_oid)
        _stat_code = {'1': 'online', '2': 'offline', '3': 'testing', '4': 'faulty'}
        _return = self.decode_index(_stat_code, _value, 'sys_stat')

        if _return is None:
            return UNKNOWN

        return PASSED if _return == 'online' else FAILED

    def sensor_stat(self):
        _base_oid = '1.3.6.1.4.1.1588.2.1.1.1.1.22.1'
        _index_list = self.snmpwalk_values(f'{_base_oid}.1')
        _type_list = self.snmpwalk_values(f'{_base_oid}.2')
        _stat_list = self.snmpwalk_values(f'{_base_oid}.3')
        _value_list = self.snmpwalk_values(f'{_base_oid}.4')
        _info_list = self.snmpwalk_values(f'{_base_oid}.5')

        _return_code = 0

        if len(_index_list) == 0 or list(set(_index_list)) == ['-'] or _index_list == ['']:
            return UNKNOWN

        _type_code = {'1': 'unknown', '2': 'other', '3': 'battery', '4': 'fan',
                      '5': 'power-supply', '6': 'transmitter', '7': 'enclosure',
                      '8': 'board', '9': 'receiver'}

        _stat_code = {'1': 'unknown', '2': 'faulty', '3': 'below-min', '4': 'nominal', '5': 'above-max', '6': 'absent'}

        for _i in range(len(_index_list)):
            _line = f'{_index_list[_i]} ' \
                    f'{self.decode_index(_type_code, _type_list[_i], "Sensor Type")} ' \
                    f'{self.decode_index(_stat_code, _stat_list[_i], "Sensor Stat")} ' \
                    f'{_value_list[_i]} ' \
                    f'{_info_list[_i]}'
            if 'nominal' not in _line and 'absent' not in _line:  # some sensor recognrised 'unknown' or 'battery' is absent
                self.error_msg.append(_line)
                _return_code += 1  # todo prevent write error line such as '- - - - -'
        return PASSED if _return_code == 0 else FAILED

    def port_stat(self):
        _return_code = 0

        _base_oid = '1.3.6.1.4.1.1588.2.1.1.1.6.2.1'
        _name_list = self.snmpwalk_values(f'{_base_oid}.36')
        _type_list = self.snmpwalk_values(f'{_base_oid}.2')  # The type of ASIC for the switch port
        _phy_stat_list = self.snmpwalk_values(f'{_base_oid}.3')  # The physical state of the port
        _op_stat_list = self.snmpwalk_values(f'{_base_oid}.4')
        _adm_stat_list = self.snmpwalk_values(f'{_base_oid}.5')
        _link_stat_list = self.snmpwalk_values(f'{_base_oid}.6')

        _type_code = {'1': 'stitch', '2': 'flannel', '3': 'loom', '4': 'bloom',
                      '5': 'rdbloom', '6': 'wormhole', '7': 'other', '8': 'unknown'}
        _phy_stat_code = {'1': 'noCard',  # NO card in this slot
                          '2': 'noTransceiver',  # No transceiver module in this port
                          '3': 'laserFault',  # The module is signaling a laser fault
                          '4': 'noLight',  # The module is not receiving light
                          '5': 'noSync',  # The module is receiving light but is out of sync
                          '6': 'inSync',  # The module is receiving light and is in sync
                          '7': 'portFault',  # The port is marked faulty (GBIC, cable, or device)
                          '8': 'diagFault',
                          '9': 'lockRef',
                          '10': 'validating',
                          '11': 'invalidModule',
                          '14': 'noSigDet',
                          '255': 'unknown'}
        _op_stat_code = {'0': 'unknown', '1': 'online', '2': 'offline', '3': 'testing', '4': 'faulty'}
        _adm_stat_code = {'1': 'online', '2': 'offline', '3': 'testing', '4': 'faulty'}
        _link_stat_code = {'1': 'enable', '2': 'disabled', '3': 'loopback'}

        _sfp_oid = '1.3.6.1.4.1.1588.2.1.1.1.28.1.1'  # SNMPv2-SMI::enterprises.1588.2.1.1.1.28.1.1.1.16.0.80.235.26.208.116.3.0.0.0.0.0.0.0.0.61 = STRING: "65"
        _temp_list = self.snmpwalk_values(f'{_sfp_oid}.1')
        _vol_list = self.snmpwalk_values(f'{_sfp_oid}.2')
        _current_list = self.snmpwalk_values(f'{_sfp_oid}.3')
        _rx_pwr_list = self.snmpwalk_values(f'{_sfp_oid}.4')
        _tx_pwr_list = self.snmpwalk_values(f'{_sfp_oid}.5')
        _pwr_hrs_list = self.snmpwalk_values(f'{_sfp_oid}.6')

        def _trans_dBm_uW(_dbPower) -> float:
            try:
                _dbPower = float(_dbPower)  # For eg: -2.5
            except ValueError:
                _dbPower = 0.0
            _uWatts = float('{:.0f}'.format(math.pow(10, _dbPower / 10) * 1000))  # Trans dBm to uWatts
            return _uWatts

        if len(_name_list) == 0 or list(set(_name_list)) == ['-'] or _name_list == ['']:
            return UNKNOWN

        # remove the values of port which has no transceiver
        # because these ports have no sfp OID value
        """
        for _i in range(len(_name_list)):
            try:
                if _phy_stat_list[_i] == '2':
                    _name_list.pop(_i)
                    _type_list.pop(_i)
                    _phy_stat_list.pop(_i)
                    _op_stat_list.pop(_i)
                    _adm_stat_list.pop(_i)
                    _link_stat_list.pop(_i)
            except IndexError:
                continue
        """

        for _i in range(len(_name_list)):
            try:
                _rx_uw = _trans_dBm_uW(_rx_pwr_list[_i])
                _tx_uw = _trans_dBm_uW(_tx_pwr_list[_i])
            except IndexError:
                _rx_uw = 0.0
                _tx_uw = 0.0

            if platform.system() == 'Linux':
                _rx_uw_color = f'\033[0;37m{_rx_uw}\033[0m' if RX_LOW < _rx_uw < RX_HIGH else f'\033[0;31m{_rx_uw}\033[0m'
                _tx_uw_color = f'\033[0;37m{_tx_uw}\033[0m' if TX_LOW < _tx_uw < TX_HIGH else f'\033[0;31m{_tx_uw}\033[0m'

                _no_color = 18
            else:
                _rx_uw_color = f'{_rx_uw}'  # be compatible with windows python3.8
                _tx_uw_color = f'{_tx_uw}'

                _no_color = 6

            try:
                _line = f'{_name_list[_i]:<15s}' \
                        f'{self.decode_index(_phy_stat_code, _phy_stat_list[_i], "Port PHY Stat"):<13s}' \
                        f'{self.decode_index(_op_stat_code, _op_stat_list[_i], "Port OP Stat"):<9s}' \
                        f'{self.decode_index(_link_stat_code, _link_stat_list[_i], "Port Link Stat"):<8s}' \
                        f'{_temp_list[_i]:>3s}^C' \
                        f'{_vol_list[_i]:>7s}mV' \
                        f'{_current_list[_i]:>6s}mA' \
                        f'{_rx_uw_color:>{_no_color}s}ruW' \
                        f'{_tx_uw_color:>{_no_color}s}tuW' \
                        f'{_pwr_hrs_list[_i]:>6s}Hrs'

            # f'{self.decode_index(_adm_stat_code, _adm_stat_list[_i], "Port ADM Stat"):<9s}' \
            # f'{self.decode_index(_type_code, _type_list[_i], "Port Type"):<8s} '
            except IndexError:
                continue

            if _link_stat_list[_i] == '2':  # port is disabled by Administrator, ignore state check
                continue

            if _phy_stat_list[_i] in ['3', '5', '7', '8']:
                self.error_msg.append(_line)
                _return_code += 1

            if _phy_stat_list[_i] in ['6']:
                if (not RX_LOW < _rx_uw < RX_HIGH) or (not TX_LOW < _tx_uw < TX_HIGH):
                    self.error_msg.append(_line)
                    _return_code += 1

        return PASSED if _return_code == 0 else FAILED

    def port_stat_rw(self):
        _return_code = 0
        _port_stat = {}

        _base_oid = '1.3.6.1.4.1.1588.2.1.1.1.6.2.1'
        _base_list = self.snmpwalk_values(f'{_base_oid}.1')  # for checking if snmpwalk successfully
        # _index_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_base_oid}.1')}
        _name_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_base_oid}.36')}
        _type_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_base_oid}.2')}  # The type of ASIC for the switch port
        _phy_stat_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_base_oid}.3')}  # The physical state of the port
        _op_stat_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_base_oid}.4')}
        _adm_stat_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_base_oid}.5')}
        _link_stat_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_base_oid}.6')}

        _type_code = {'1': 'stitch', '2': 'flannel', '3': 'loom', '4': 'bloom',
                      '5': 'rdbloom', '6': 'wormhole', '7': 'other', '8': 'unknown'}
        _phy_stat_code = {'1': 'noCard',            # NO card in this slot
                          '2': 'noTransceiver',     # No transceiver module in this port
                          '3': 'laserFault',        # The module is signaling a laser fault
                          '4': 'noLight',           # The module is not receiving light
                          '5': 'noSync',            # The module is receiving light but is out of sync
                          '6': 'inSync',            # The module is receiving light and is in sync
                          '7': 'portFault',         # The port is marked faulty (GBIC, cable, or device)
                          '8': 'diagFault',
                          '9': 'lockRef',
                          '10': 'validating',
                          '11': 'invalidModule',
                          '14': 'noSigDet',
                          '255': 'unknown'}
        _op_stat_code = {'0': 'unknown', '1': 'online', '2': 'offline', '3': 'testing', '4': 'faulty'}
        _adm_stat_code = {'1': 'online', '2': 'offline', '3': 'testing', '4': 'faulty'}
        _link_stat_code = {'1': 'enable', '2': 'disabled', '3': 'loopback'}

        _sfp_oid = '1.3.6.1.4.1.1588.2.1.1.1.28.1.1'
        # SNMPv2-SMI::enterprises.1588.2.1.1.1.28.1.1.1.16.0.80.235.26.208.116.3.0.0.0.0.0.0.0.0.61 = STRING: "65"
        _temp_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_sfp_oid}.1')}
        _vol_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_sfp_oid}.2')}
        _current_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_sfp_oid}.3')}
        _rx_pwr_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_sfp_oid}.4')}
        _tx_pwr_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_sfp_oid}.5')}
        _pwr_hrs_list = {_line[0]: _line[1] for _line in self.snmpwalk_index_value(f'{_sfp_oid}.6')}

        def _trans_dBm_uW(_dbPower) -> float:
            try:
                _dbPower = float(_dbPower)  # For eg: -2.5
            except ValueError:
                _dbPower = 0.0
            _uWatts = float('{:.0f}'.format(math.pow(10, _dbPower / 10) * 1000))  # Trans dBm to uWatts
            return _uWatts

        if len(_base_list) == 0 or list(set(_base_list)) == ['-'] or _base_list == ['']:
            return UNKNOWN

        # for _i in range(len(_name_list)):
        for _i, _value in _name_list.items():
            try:
                _rx_uw = _trans_dBm_uW(_rx_pwr_list[_i])
                _tx_uw = _trans_dBm_uW(_tx_pwr_list[_i])
            except IndexError:
                _rx_uw = _tx_uw = 0.0
            except KeyError:
                self.colorlog(f'no rx/tx power value found for [{_value}]', 'warn')
                _rx_uw = _tx_uw = 0.0

            if platform.system() == 'Linux':
                _rx_uw_color = f'\033[0;37m{_rx_uw}\033[0m' if RX_LOW < _rx_uw < RX_HIGH else f'\033[0;31m{_rx_uw}\033[0m'
                _tx_uw_color = f'\033[0;37m{_tx_uw}\033[0m' if TX_LOW < _tx_uw < TX_HIGH else f'\033[0;31m{_tx_uw}\033[0m'

                _no_color = 18
            else:
                _rx_uw_color = f'{_rx_uw}'  # be compatible with windows python3.8
                _tx_uw_color = f'{_tx_uw}'

                _no_color = 6

            # index 0 does not exist in snmp values
            # index 0 does not exist in values of OID '1.3.6.1.4.1.1588.2.1.1.1.28.1.1'
            try:
                # change port name from slot5port5 to s5p5, for short use of line
                _name = _name_list[_i].upper().replace('SLOT', 'S').replace('PORT', 'P')

                _line = f'{_name:<6s}' \
                        f'{self.decode_index(_phy_stat_code, _phy_stat_list[_i], "Port PHY Stat"):<13s}' \
                        f'{self.decode_index(_op_stat_code, _op_stat_list[_i], "Port OP Stat"):<9s}' \
                        f'{self.decode_index(_link_stat_code, _link_stat_list[_i], "Port Link Stat"):<8s}' \
                        f'{_temp_list[_i]:>3s}^C' \
                        f'{_vol_list[_i]:>7s}mV' \
                        f'{_current_list[_i]:>6s}mA' \
                        f'{_rx_uw_color:>{_no_color}s}ruW' \
                        f'{_tx_uw_color:>{_no_color}s}tuW' \
                        f'{_pwr_hrs_list[_i]:>6s}Hrs'

            # f'{self.decode_index(_adm_stat_code, _adm_stat_list[_i], "Port ADM Stat"):<9s}' \
            # f'{self.decode_index(_type_code, _type_list[_i], "Port Type"):<8s} '
            except IndexError:
                continue
            except KeyError as _e:
                self.colorlog(f'maybe the port [{_value}] has no transceiver', 'warn')
                continue

            if _link_stat_list[_i] == '2':  # port is disabled by Administrator, ignore state check
                self.colorlog(f'port [{_value}] is disabled by admin, ignore checking.', 'info')
                continue

            if _phy_stat_list[_i] in ['3', '5', '7', '8']:
                self.error_msg.append(_line)
                _return_code += 1

            if _phy_stat_list[_i] in ['6']:
                if (not RX_LOW < _rx_uw < RX_HIGH) or (not TX_LOW < _tx_uw < TX_HIGH):
                    self.error_msg.append(_line)
                    _return_code += 1

        return PASSED if _return_code == 0 else FAILED

    def ha_stat(self):
        _oid = '1.3.6.1.4.1.1588.2.1.2.1.1'
        _value = self.snmpwalk_value1(_oid)
        _stat_code = {'0': 'redundant', '1': 'nonredundant'}
        _return = self.decode_index(_stat_code, _value, 'HA_stat')

        if _return is None:
            return UNKNOWN
        return PASSED if _return == 'online' else FAILED

    def fru_stat(self):
        _return_code = 0

        _base_oid = '1.3.6.1.4.1.1588.2.1.2.1.5.1'
        _class_list = self.snmpwalk_values(f'{_base_oid}.1')
        _stat_list = self.snmpwalk_values(f'{_base_oid}.2')
        _obj_num_list = self.snmpwalk_values(f'{_base_oid}.3')
        _supplier_id_list = self.snmpwalk_values(f'{_base_oid}.4')
        _supplier_pn_list = self.snmpwalk_values(f'{_base_oid}.5')
        _supplier_sn_list = self.snmpwalk_values(f'{_base_oid}.6')
        _supplier_revcode_list = self.snmpwalk_values(f'{_base_oid}.7')
        _pwr_con_list = self.snmpwalk_values(f'{_base_oid}.8')

        _class_code = {'1': 'other', '2': 'unknown', '3': 'chassis', '4': 'CP',
                       '5': 'other-CP', '6': 'switchblade', '7': 'wwn',
                       '8': 'powerSupply', '9': 'fan', '10': 'CoreBlade', '11': 'ApplicationBlade'}

        _stat_code = {'1': 'other', '2': 'unknown', '3': 'on', '4': 'off', '5': 'faulty'}

        if len(_class_list) == 0 or list(set(_class_list)) == ['-'] or _class_list == ['']:
            return UNKNOWN

        for _i in range(len(_class_list)):
            _line = f'{self.decode_index(_class_code, _class_list[_i], "FRU Class")} ' \
                    f'{self.decode_index(_stat_code, _stat_list[_i], "FRU Stat")} ' \
                    f'{_obj_num_list[_i]} ' \
                    f'{_supplier_id_list[_i]} ' \
                    f'{_supplier_pn_list[_i]} ' \
                    f'{_supplier_sn_list[_i]} ' \
                    f'{_supplier_revcode_list[_i]} ' \
                    f'{_pwr_con_list[_i]}'
            if 'faulty' in _line:
                self.error_msg.append(_line)
                _return_code += 1
        return PASSED if _return_code == 0 else FAILED

    def cp_stat(self):
        _return_code = 0

        _base_oid = '1.3.6.1.4.1.1588.2.1.2.1.7.1'
        _stat_list = self.snmpwalk_values(f'{_base_oid}.1')
        _ip_list = self.snmpwalk_values(f'{_base_oid}.2')
        _mask_list = self.snmpwalk_values(f'{_base_oid}.3')
        _gw_list = self.snmpwalk_values(f'{_base_oid}.4')
        _last_event_list = self.snmpwalk_values(f'{_base_oid}.5')

        _stat_code = {'1': 'other', '2': 'unknown', '3': 'active', '4': 'standby', '5': 'failed'}
        _event_code = {'1': 'other', '2': 'unknown', '3': 'haSync', '4': 'haOutSync', '5': 'cpFaulty',
                       '6': 'cpHealthy', '7': 'cpActive', '8': 'configChange', '9': 'failOverStart',
                       '10': 'failOverDone', '11': 'firmwareCommit', '12': 'firmwareUpgrade'}

        if len(_stat_list) == 0 or list(set(_stat_list)) == ['-'] or _stat_list == ['']:
            return UNKNOWN

        for _i in range(len(_stat_list)):
            _line = f'{self.decode_index(_stat_code, _stat_list[_i], "CP Stat")} ' \
                    f'{_ip_list[_i]} ' \
                    f'{_mask_list[_i]} ' \
                    f'{_gw_list[_i]} ' \
                    f'{self.decode_index(_event_code, _last_event_list[_i], "CP Last Event")} '

            if 'failed' in _line:
                self.error_msg.append(_line)
                _return_code += 1
        return PASSED if _return_code == 0 else FAILED

    def fetch_pm_values(self):
        # firmware version
        self.fir_ver_val = self.firmware_version()
        # system state
        self.sys_stat_val = self.sys_stat()
        # sensor state
        self.sensor_stat_val = self.sensor_stat()
        # fru state
        self.fru_stat_val = self.fru_stat()
        # CP State
        self.cp_stat_val = self.cp_stat()
        # port state
        # self.port_stat_val = self.port_stat()
        self.port_stat_val = self.port_stat_rw()

    def pm(self):
        print('\n', '=' * 80, sep='')
        # print('-' * 32, f'{self.manage_ipaddr:^16s}', '-' * 32, sep='')
        print('-' * 30, f'{self.manage_ipaddr:^14s}{self.vf_id:^6s}', '-' * 30, sep='')

        # machine description
        prompt = 'Switch Description'
        desc = self.desc
        print(f'{prompt:<30s}{desc:.>50s}')

        # firmware version
        prompt = 'Switch Firmware Version'
        # fir_ver = self.firmware_version()
        fir_ver = self.fir_ver_val
        print(f'{prompt:<30s}{fir_ver:.>50s}')

        # system state
        prompt = 'Switch System State'
        # sys_stat = self.sys_stat()
        sys_stat = self.sys_stat_val
        print(f'{prompt:<30s}{sys_stat:.>{NO_COLOR}s}')

        # sensor state
        prompt = 'Switch Sensor State'
        # sensor_stat = self.sensor_stat()
        sensor_stat = self.sensor_stat_val
        print(f'{prompt:<30s}{sensor_stat:.>{NO_COLOR}s}')

        # fru state
        prompt = 'Switch FRU State'
        # fru_stat = self.fru_stat()
        fru_stat = self.fru_stat_val
        print(f'{prompt:<30s}{fru_stat:.>{NO_COLOR}s}')

        # CP State
        prompt = 'Switch CP State'
        # cp_stat = self.cp_stat()
        cp_stat = self.cp_stat_val
        print(f'{prompt:<30s}{cp_stat:.>{NO_COLOR}s}')

        # port state
        prompt = 'Switch Port State'
        # port_stat = self.port_stat()
        port_stat = self.port_stat_val
        print(f'{prompt:<30s}{port_stat:.>{NO_COLOR}s}')

        if len(self.error_msg) != 0:
            print('-' * 80)
            for line in self.error_msg:
                print(line)
            print('-' * 80)

    def pm_1_by_1(self):
        print('\n', '=' * 80, sep='')
        # print('-' * 32, f'{self.manage_ipaddr:^16s}', '-' * 32, sep='')
        print('-' * 30, f'{self.manage_ipaddr:^14s}{self.vf_id:^6s}', '-' * 30, sep='')

        # machine description
        prompt = 'Switch Description'
        desc = self.desc
        print(f'{prompt:<30s}{desc:.>50s}')

        # firmware version
        prompt = 'Switch Firmware Version'
        fir_ver = self.firmware_version()
        # fir_ver = self.fir_ver_val
        print(f'{prompt:<30s}{fir_ver:.>50s}')

        # system state
        prompt = 'Switch System State'
        sys_stat = self.sys_stat()
        # sys_stat = self.sys_stat_val
        print(f'{prompt:<30s}{sys_stat:.>{NO_COLOR}s}')

        # sensor state
        prompt = 'Switch Sensor State'
        sensor_stat = self.sensor_stat()
        # sensor_stat = self.sensor_stat_val
        print(f'{prompt:<30s}{sensor_stat:.>{NO_COLOR}s}')

        # fru state
        prompt = 'Switch FRU State'
        fru_stat = self.fru_stat()
        # fru_stat = self.fru_stat_val
        print(f'{prompt:<30s}{fru_stat:.>{NO_COLOR}s}')

        # CP State
        prompt = 'Switch CP State'
        cp_stat = self.cp_stat()
        # cp_stat = self.cp_stat_val
        print(f'{prompt:<30s}{cp_stat:.>{NO_COLOR}s}')

        # port state
        prompt = 'Switch Port State'
        port_stat = self.port_stat_rw()
        # port_stat = self.port_stat_val
        print(f'{prompt:<30s}{port_stat:.>{NO_COLOR}s}')

        if len(self.error_msg) != 0:
            print('-' * 80)
            for line in self.error_msg:
                print(line)
            print('-' * 80)


def pm_all_switch(switch_list, display=False):
    # todo add parameter for decided if pm with multiple threading
    no_thread = 5

    # snmp_consoles = []

    def _snmp_pm(snmp_class: SwitchSnmpConsole):
        snmp_class.fetch_pm_values()

    # ssh_consoles = []

    def _ssh_pm(ssh_class: SwitchSshConsole):
        ssh_class.fetch_pm_values()

    for switch_cfg in switch_list:
        try:
            # _ipaddr, _user, _pass, _ssh_port, _vf_id, _snmp_args = switch_cfg
            _ipaddr, _user, _pass, _ssh_port, _snmp_args_list, _desc = switch_cfg

            for _snmp_args in _snmp_args_list:
                _vf_id = _snmp_args.split('VF:')[-1].split()[0] if 'VF:' in _snmp_args else None
                _snmp_consl = SwitchSnmpConsole(_ipaddr, _snmp_args, vf_id=_vf_id, display=display, desc=_desc)

                # for multiple threading pm via snmp
                # snmp_consoles.append(_snmp_consl)

                # pm via snmp one by one
                _snmp_consl.pm_1_by_1()

            # pm san switch via ssh uncommitted
            # _ssh_consl = SwitchSshConsole(_ipaddr, _user, _pass, _ssh_port, display=display)
            # ssh_consoles.append(_ssh_consl)
            # _ssh_consl.pm()

        except ValueError:
            pass

    # threading for pm via snmp
    # snmp_threads = [threading.Thread(target=_snmp_pm, args=(_snmp_consl,)) for _snmp_consl in snmp_consoles]

    # threading for pm via ssh
    # ssh_threads = [threading.Thread(target=_ssh_pm, args=(_ssh_consl,)) for _ssh_consl in ssh_consoles]

    # threading for pm via snmp
    # [t.start() for t in snmp_threads]
    # [t.join() for t in snmp_threads]

    # threading for pm via ssh
    # [t.start() for t in ssh_threads]
    # [t.join() for t in ssh_threads]

    # print results
    # [consl.pm() for consl in snmp_consoles]
    # [consl.pm() for consl in ssh_consoles]


if __name__ == '__main__':
    snmp = SwitchSnmpConsole(f'192.168.1.1', '-v3 -u user', display=False)
    snmp.pm()

    ssh = SwitchSshConsole(f'192.168.1.1', username='admin', password='admin', display=False)
    ssh.pm()
