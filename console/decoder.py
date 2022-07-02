#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2022 by ZHANG ZHIJIE.
# All rights reserved.

# Created Time: 4/23/22 10:40
# Author: ZHANG ZHIJIE
# Email: norvyn@norvyn.com
# Git: @n0rvyn
# File Name: decoder.py
# Tools: PyCharm

"""
---Decode San Switch log to Dict---
"""
import os
import sys
import math

_HOME_ = os.path.abspath(os.path.dirname(__file__))
_ROOT_ = os.path.abspath(os.path.join(_HOME_, '..'))

_LOG_PATH_ = os.path.join(_ROOT_, 'log')
_LOGFILE_ = os.path.join(_LOG_PATH_, 'console.log')

sys.path.append(_ROOT_)
from console import ColorLogger
from console import log_cleaner


class SwitchLogDecoder(object):
    def __init__(self, datafile=None, logfile=None, user='admin', display=True, virtual_fabric=False):
        self.prompt = '>'
        self.blade = False
        self.virtual_fabric = virtual_fabric
        self.datafile = datafile

        self.logfile = logfile if logfile is not None else _LOGFILE_
        self.logger_prefix = 'Switch Log Decoder'
        self.display = display

        self.weight = 0 if virtual_fabric is False else 1

        self.detail = {}
        """
        {
        FID128: 
            {
            'switch': {}, 
            'port': {}, 
            'sensor': {},
            'fru': {},
            'cfg': 
                [
                    {
                    'cfg name': '',
                    'zone': {},
                    'alias': {}
                    },
                    {
                    'cfg  name': '',
                    'zone': {},
                    'alias': {}
                    }
                ]
            },
        FID24: {}
        }
        """
        self.FIDs = []
        self.user = user

    def colorlog(self, msg=None, level=None):
        msg = '' if msg is None else msg
        level = 'debug' if level is None else level
        # name = self.class_name + ' {:<15s}'.format(self.logger_suffix)
        name = f'{self.logger_prefix:<18s}'
        colorlogger = ColorLogger(name, self.logfile, display=self.display)
        log_cleaner(self.logfile, 100)
        colorlogger.colorlog(msg, level)

    def is_line_data_or_prompt(self, line):
        line = line.strip()

        if self.prompt not in line:
            return 'data'
        if len(line.split(self.prompt)) < 2:
            return 'data'
        # SNS2224:admin> lscfg
        # SNS3096-BC01:FID128:admin> lscfg
        if len(line.split(':')) < 2+self.weight:
            return 'data'
        if self.user not in line:
            return 'data'

        self.colorlog(f'prompt line detected [{line}]', 'debug')
        return 'prompt'

    def detect_command(self, prompt_line):
        vf_id = command = None

        try:
            vf_id = prompt_line.split(':')[1] if self.virtual_fabric is True else 'FID0'
            command = prompt_line.split(':')[1+self.weight].split(self.prompt)[1].strip()
            self.colorlog(f'vf id: [{vf_id}] command: [{command}] detected.', 'debug')
        except IndexError as _e:
            self.colorlog(_e, 'error')
        except ValueError as _e:
            self.colorlog(_e, 'error')
        self.FIDs.append(vf_id)
        self.FIDs = list(set(self.FIDs))

        # self.detail.update({vf_id: {'switch': {}, 'port': {}, 'health': {}, 'cfg': {}}})
        return vf_id, command

    def split_file_as_dict(self):
        _datalines = []
        try:
            with open(self.datafile, 'r+') as f:
                _datalines = [_line.strip('\n').strip() for _line in f.readlines()]
        except FileNotFoundError as _e:
            self.colorlog(_e, 'error')
            return _datalines

        _output = {}
        _current_vf_id = None
        _current_command = None
        for _line in _datalines:
            if self.is_line_data_or_prompt(_line) == 'prompt':
                _current_vf_id, _current_command = self.detect_command(_line)
                continue
            if _current_command or _current_vf_id is None:
                continue
            if '|' in _current_command:  # ignore command contains '|', output may be not complete.
                _current_command = None
                continue
            if _line == '':
                continue
            try:
                _output[(_current_vf_id, _current_command)].append(_line)
            except KeyError:
                _output.update({(_current_vf_id, _current_command): [_line]})

        return _output

    def switchshow_decode(self, switchshow_output: list, vf_id: str):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['switch']
        except KeyError:
            self.detail[vf_id].update({'switch': {}})
        try:
            self.detail[vf_id]['port']
        except KeyError:
            self.detail[vf_id].update({'port': {}})

        # add here, if other attribute need to be collected.
        switch_attr = ['switchName', 'switchState', 'switchDomain', 'zoning']
        switchshow_detail = {_attr: '' for _attr in switch_attr}

        for line in switchshow_output:
            line = line.strip('\n')
            if line == '':
                continue

            try:
                _key, _value = line.split(':')
                _key = _key.strip()
                _value = _value.strip()

                switchshow_detail[_key] = _value
            except ValueError:
                pass
            except IndexError:
                pass
            except KeyError:
                pass

            """
            Index Slot Port     Address     Media   Speed   State       Proto
            Index Port          Address     Media   Speed   State       Proto
            """
            if line.startswith('Index'):
                _port_attr = line.split()
                try:
                    if _port_attr[1] == 'Slot':
                        self.blade = True
                    if _port_attr[1] == 'Port':
                        self.blade = False
                except IndexError:
                    continue
            elif line.split()[0].isnumeric() and len(line.split()) >= 7:  # port detail
                _port_detail = line.split()
                if self.blade:
                    _port_index = _port_detail[0]
                    _port_slot = _port_detail[1]
                    _port_port = _port_detail[2]
                    _port_address = _port_detail[3]
                    _port_media = _port_detail[4]
                    _port_speed = _port_detail[5]
                    _port_state = _port_detail[6]
                    _port_proto = ' '.join(_port_detail[7:])

                elif not self.blade:
                    _port_index = _port_detail[0]
                    _port_slot = 'N/A'
                    _port_port = _port_detail[1]
                    _port_address = _port_detail[2]
                    _port_media = _port_detail[3]
                    _port_speed = _port_detail[4]
                    _port_state = _port_detail[5]
                    _port_proto = ' '.join(_port_detail[6:])

                else:
                    continue
                # _port_detail =    (_port_index, _port_slot, _port_port,
                #                   _port_address, _port_media, _port_speed, _port_state, _port_proto)
                _port_detail = {'Index': _port_index, 'Slot': _port_slot, 'Port': _port_port,
                                'Address': _port_address, 'Media': _port_media, 'Speed': _port_speed,
                                'State': _port_state, 'Proto': _port_proto}
                # _port_name = f'port{_port_index}'
                _port_name = str(_port_index)

                try:
                    self.detail[vf_id]['port'][_port_name].update(_port_detail)
                except KeyError:
                    self.detail[vf_id]['port'].update({_port_name: _port_detail})

        self.detail[vf_id]['switch'].update(switchshow_detail)
        return switchshow_detail

    def portshow_decode(self, portshow_output: list, vf_id: str):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['port']
        except KeyError:
            self.detail[vf_id].update({'port': {}})

        # portshow_attr = ['portIndex', 'portHealth', 'WWNs', 'Loss_of_sync']
        # portshow_detail = {_attr: '' for _attr in portshow_attr}
        portshow_detail = {}

        # connect key value split with ': ' as 'key:value'
        _output_formatted = []
        _output_keys_values = []
        for _line in portshow_output:
            # _no_parts = len(_line.split(': '))
            # split with ': ' not ':' for void making mistake of WWN '50:05:07:...'
            _no_parts = len(_line.split(': '))  # split with ': ' not ':' for void making mistake of WWN '50:05:07:...'
            _part_list = _line.split(': ')
            if _no_parts > 2:  # line has more than 2 key-value pairs
                _ = [_l.strip() for _l in _line.split()]
                _line = '|'.join(_).replace(':|', ':')
                _output_formatted.append(_line)
            elif _no_parts == 2:  # line has just 1 key-value pair
                try:
                    portshow_detail[_part_list[0].strip()] = _part_list[1].strip()
                except KeyError:
                    pass
                except IndexError:
                    pass
            elif _no_parts == 1:  # line is blank or does contain ': '
                pass

        _output_in_one_line = '|'.join(_output_formatted)
        _output_keys_values = _output_in_one_line.split('|')
        for _key_value in _output_keys_values:
            try:
                _key, _value = _key_value.split(':')
                _key = _key.strip()
                _value = _value.strip()
                portshow_detail[_key] = _value
            except ValueError:
                pass
            except KeyError:
                pass

        _npiv_info = ' '.join(portshow_output).split('portWwn of device(s) connected:')[-1]
        _npiv_info = _npiv_info.split('16b Area list:')[0].split()
        _npiv_info = tuple(_npiv_info)
        portshow_detail['WWNs'] = _npiv_info

        _port_phys = ''.join(portshow_output).split('portPhys:')[-1]
        _port_phys = _port_phys.split('portScn:')[0]
        portshow_detail['portPhys'] = _port_phys.strip()

        _port_scn = ''.join(portshow_output).split('portScn:')[-1]
        _port_scn = _port_scn.split('port generation number:')[0]
        portshow_detail['portScn'] = _port_scn.strip()

        try:
            # _port_name = f'port{portshow_detail["portIndex"]}'
            # change port name from 'port95' to '95'#
            # for emerging with sfp detail
            _port_name = str(portshow_detail["portIndex"])
        except KeyError:
            return False

        try:
            self.detail[vf_id]['port'][_port_name].update(portshow_detail)
        except KeyError:
            self.detail[vf_id]['port'].update({_port_name: portshow_detail})

        # try:
        #     self.detail[vf_id]['port'][_port_name].update(portshow_detail)
        # except KeyError:
        #     pass
        return portshow_detail

    def sfpshow_decode(self, sfpshow_output: list, vf_id: str, full_command: str):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['port']
        except KeyError:
            self.detail[vf_id].update({'port': {}})
        sfpshow_detail = {}

        for _line in sfpshow_output:
            _key, *_value = _line.split(':')
            _key = _key.strip()
            _value = ''.join(_value).strip()
            sfpshow_detail.update({_key: _value})
        _port_name = full_command.strip('sfpshow').strip()
        if '/' in _port_name:
            for port in self.detail[vf_id]['port']:
                try:
                    _slot = self.detail[vf_id]['port'][port]['Slot']
                    _port = self.detail[vf_id]['port'][port]['Port']
                    if _port_name == f'{_slot}/{_port}':
                        _port_name = port
                except KeyError:
                    pass
        elif _port_name.isnumeric():
            _port_name = f'port{_port_name}'

        try:
            self.detail[vf_id]['port'][_port_name].update(sfpshow_detail)
        except KeyError:
            self.detail[vf_id]['port'].update({_port_name: sfpshow_detail})

        return sfpshow_detail

    def sfpshow_all_decode(self, sfpshow_all_output: list, vf_id: str):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['port']
        except KeyError:
            self.detail[vf_id].update({'port': {}})
        sfpshow_all_detail = {}

        current_port = None
        for _line in sfpshow_all_output:
            if _line.startswith('Port'):
                current_port = _line.split()[-1].strip(':')
                sfpshow_all_detail.update({current_port: {}})
                continue

            _key, *_value = _line.split(':')
            _key = _key.strip()
            _value = ''.join(_value).strip()

            if _key in ['Temperature', 'Current', 'Voltage', 'RX Power', 'TX Power']:
                try:
                    _sub_value = float(_value.split()[0])
                    _unit = _value.split()[1]

                    if _unit == 'dBm':
                        _sub_value = f'{(math.pow(10, _sub_value / 10) * 1000):.1f}'

                # _uWatts = float('{:.0f}'.format(math.pow(10, _dbPower / 10) * 1000))
                except IndexError:
                    continue

            else:
                continue

            try:
                sfpshow_all_detail[current_port].update({_key: _sub_value})
                self.detail[vf_id]['port'][current_port].update({_key: _sub_value})
            except KeyError:
                self.detail[vf_id]['port'].update({current_port: {_key: _sub_value}})

        return sfpshow_all_detail

    def tempshow_decode(self, tempshow_output, vf_id):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        tempshow_detail = {}

        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['sensor']
        except KeyError:
            self.detail[vf_id].update({'sensor': {}})

        for _line in tempshow_output:
            _list = _line.split()
            if _list[0].isnumeric():
                try:
                    _temp = _list[-2]
                    _state = _list[-3]
                    # _sensor_id_slot = ' '.join(_list[-5:-3])
                    _id = _list[0]
                    tempshow_detail.update({_id: {'ID': _id, 'State': _state, 'Centigrade': _temp}})
                except IndexError as _e:
                    self.colorlog(_e, 'warn')
        try:
            self.detail[vf_id]['sensor'].update({'temp': tempshow_detail})
        except KeyError:
            pass

        return tempshow_detail

    def slotshow_decode(self, slotshow_output, vf_id):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        slotshow_detail = {}

        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['switch']
        except KeyError:
            self.detail[vf_id].update({'switch': {}})

        for _line in slotshow_output:
            if _line.strip() == '':
                continue

            _line = _line.replace(' BLADE', '_BLADE')
            _list = _line.split()
            # Slot   Blade Type     ID     Status
            # 1      SW_BLADE       96     ENABLED
            # 12     UNKNOWN               VACANT
            if _list[0].isnumeric():
                try:
                    _slot = _list[0]
                    _type = _list[1]

                    _id = _list[-2]
                    _stat = _list[-1]

                    slotshow_detail.update({_slot: {'Slot': _slot, 'Blade Type': _type, 'ID': _id, 'Status': _stat}})
                except IndexError:
                    continue

        self.detail[vf_id]['switch'].update({'slot': slotshow_detail})
        return slotshow_detail

    def psshow_decode(self, psshow_output, vf_id):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        psshow_detail = {}

        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['sensor']
        except KeyError:
            self.detail[vf_id].update({'sensor': {}})

        for _line in psshow_output:
            if _line.startswith('Power Supply'):
                _list = _line.split()
                try:
                    _id = _list[2]
                    _state = _list[4]
                    psshow_detail.update({_id: {'ID': _id, 'State': _state}})
                except ValueError as _e:
                    self.colorlog(_e, 'error')

        self.detail[vf_id]['sensor'].update({'PowerSupply': psshow_detail})
        return psshow_detail

    def ipaddrshow_decode(self, ipaddrshow_output, vf_id):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        ipaddrshow_detail = {}
        keywords = ['CHASSIS', 'CP0', 'CP1', 'SWITCH']

        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['switch']
        except KeyError:
            self.detail[vf_id].update({'switch': {}})

        _current_key = _last_key = None
        _ip = _netmask = _gw = _hostname = ''
        for _line in ipaddrshow_output:
            if _line in keywords:
                _current_key = _line.strip()
                continue

            if (_last_key is not None and _last_key != _current_key) or ipaddrshow_output[-1] == _line:  # todo last one
                ipaddrshow_detail.update(
                    {_current_key: {'ip': _ip, 'netmask': _netmask, 'gw': _gw, 'hostname': _hostname}})

            _list = _line.split(':')

            if _line.startswith('Ethernet IP Address'):
                _ip = _list[-1]

            elif _line.startswith('Ethernet Subnetmask'):
                _netmask = _list[-1]

            elif _line.startswith('Gateway IP Address'):
                _gw = _list[-1]

            elif _line.startswith('Host Name'):
                _hostname = _list[-1]

            _last_key = _current_key

        self.detail[vf_id]['switch'].update({'ipaddr': ipaddrshow_detail})
        return ipaddrshow_detail

    def firmwareshow_decode(self, firmwareshow_output, vf_id):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        firmwareshow_detail = {}

        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['switch']
        except KeyError:
            self.detail[vf_id].update({'switch': {}})

        for _line in firmwareshow_output:
            if _line.startswith('FOS'):
                """
                FOS     v7.2.1
                        v7.2.1
                """
                _index = firmwareshow_output.index(_line)

                try:
                    _pri_firm = _line.split()[-1].strip()
                    _sec_firm = firmwareshow_output[_index+1].strip()

                    firmwareshow_detail.update({'Appl': 'FOS', 'Primary': _pri_firm, 'Secondary': _sec_firm})
                except IndexError:
                    break

            elif _line.split()[0].isnumeric():
                _index = firmwareshow_output.index(_line)
                _list = _line.split()
                try:
                    _next_line = firmwareshow_output[_index+1]

                    _slot = _list[0]
                    _name = _list[1]
                    _appl = _list[2]
                    _pri_firm = _list[3]
                    _stat = _list[4]
                    _sec_firm = _next_line.strip()

                    firmwareshow_detail.update({'Slot': _slot, 'Name': _name, 'Appl': _appl,
                                                'Primary': _pri_firm, 'Secondary': _sec_firm, 'Status': _stat})

                except IndexError:
                    pass

        self.detail[vf_id]['switch'].update({'firmware': firmwareshow_detail})
        return firmwareshow_detail

    def sensorshow_decode(self, sensorshow_output, vf_id):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        sensorshow_detail = {}

        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['sensor']
        except KeyError:
            self.detail[vf_id].update({'sensor': {}})

        for _line in sensorshow_output:
            if _line.startswith('sensor') and ':' in _line:
                _id = _line.split(':')[0]

                try:
                    _state = _line.split('is')[1].split()[0].split(',')[0]
                    _type = _line.split('(')[1].split(')')[0].strip()
                    _value = _line.split('is')[-1]

                    sensorshow_detail.update({_id: {'id': _id, 'state': _state, 'type': _type, 'value': _value}})
                except IndexError as _e:
                    self.colorlog(_e, 'warn')

        self.detail[vf_id]['sensor'].update({'sensor': sensorshow_detail})
        return sensorshow_detail

    def fanshow_decode(self, fanshow_output, vf_id):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        fanshow_detail = {}

        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['sensor']
        except KeyError:
            self.detail[vf_id].update({'sensor': {}})

        for _line in fanshow_output:
            if not _line.upper().startswith('FAN'):
                pass
            _list = _line.split()
            _id = f'{_list[0]} {_list[1]}'
            _state = _list[3].strip(',')
            _speed = f'{_list[-2]} {_list[-1]}'

            fanshow_detail.update({_id: {'id': _id, 'state': _state, 'speed': _speed}})

        self.detail[vf_id]['sensor'].update({'Fan': fanshow_detail})

        return fanshow_detail

    def fabricshow_decode(self, fabricshow_output, vf_id):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        fabricshow_detail = {}

        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['switch']
        except KeyError:
            self.detail[vf_id].update({'switch': {}})

        for _line in fabricshow_output:
            if _line == '':
                continue

            _list = _line.split()
            if _list[0].strip(':').isnumeric():
                try:
                    _switch = _list[0]
                    _id = _list[1]
                    _wwn = _list[2]
                    _ip = _list[3]
                    _name_or_version = _list[-1]

                    fabricshow_detail.update({_switch: {'Switch': _switch, 'ID': _id,
                                                        'WWN': _wwn, 'IP': _ip,
                                                        'Name or Version': _name_or_version}})
                except IndexError:
                    continue

        self.detail[vf_id]['switch'].update({'fabric': fabricshow_detail})
        return fabricshow_detail

    def cfgshow_decode(self, cfgshow_output, vf_id):
        vf_id = f'FID{vf_id}' if vf_id.isnumeric() else vf_id
        fabricshow_detail = {}

        try:
            self.detail[vf_id]
        except KeyError:
            self.detail.update({vf_id: {}})
        try:
            self.detail[vf_id]['cfg']
        except KeyError:
            self.detail[vf_id].update({'cfg': {}})

        _output_line = '|'.join(cfgshow_output)

        _cfg_list = _output_line.split('cfg:')
        _ali_list = _output_line.split('alias:')
        _zone_list = _output_line.split('zone:')

        for _line in cfgshow_output:
            pass

    def alishow_decode(self, alishow_output, vf_id):
        pass

    def zoneshow_decode(self, zoneshow_output, vf_id):
        pass

    def cfgactvshow_decode(self, cfgactvshow_output, vf_id):
        pass

    def lscfgshow_decode(self, lscfgshow_output, vf_id):
        pass

    def islshow_decode(self, islshow_output, vf_id):
        pass

    def trunkshow_decode(self, trunkshow_output, vf_id):
        pass

    def final_decode(self):
        data_dict = self.split_file_as_dict()
        for _key in data_dict:
            try:
                _vf_id, _command, = _key

                if _command == 'switchshow':
                    self.switchshow_decode(data_dict[_key], _vf_id)

                if _command.startswith('portshow'):
                    self.portshow_decode(data_dict[_key], _vf_id)

                if _command.startswith('sfpshow'):
                    self.sfpshow_decode(data_dict[_key], _vf_id, _command)

                if _command == 'tempshow':
                    self.tempshow_decode(data_dict[_key], _vf_id)

                if _command == 'psshow':
                    self.psshow_decode(data_dict[_key], _vf_id)

            except ValueError:
                pass


if __name__ == '__main__':
    decoder = SwitchLogDecoder('/path/to/name.log', display=False)
    decoder.final_decode()




