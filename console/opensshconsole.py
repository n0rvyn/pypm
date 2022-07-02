#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2021 by ZHANG ZHIJIE.
# All rights reserved.

# Last Modified Time: 11/28/21 20:47
# Author: ZHANG ZHIJIE
# Email: beyan@beyan.me
# File Name: sshconsole.py
# Tools: PyCharm
#
# History:
#   2022/05/23 modify --> add parameter 'self.connected', if value is 'False', command return []

"""
---SSH Console Rebuilt with Paramiko

"""
import os
import tarfile
import random
import socket
import sys
import subprocess


_HOME_ = os.path.abspath(os.path.dirname(__file__))
_ROOT_ = os.path.join(_HOME_, '..')
_LOG_PATH_ = os.path.join(_ROOT_, 'log')
_LOG_FILE_ = os.path.join(_LOG_PATH_, 'console.log')
os.mkdir(_LOG_PATH_) if not os.path.exists(_LOG_PATH_) else ''

sys.path.insert(0, _ROOT_)
from console import ColorLogger
from console import log_cleaner


class OpenSshConsole(object):
    def __init__(self, hostname, display=True, logfile=None):
        self.logger_prefix = 'SSH'
        self.logger_suffix = hostname
        self.display = display

        self.hostname = hostname
        self.terminal = None
        self.connected = False

        self.logfile = logfile if logfile is not None else _LOG_FILE_
        self.home = os.environ['HOME']

    def colorlog(self, msg=None, level=None):
        msg = '' if msg is None else msg
        level = 'debug' if level is None else level
        # name = self.class_name + ' {:<15s}'.format(self.logger_suffix)
        name = f'{self.logger_prefix:<4s} {self.logger_suffix:<14s}'
        colorlogger = ColorLogger(name, self.logfile, display=self.display)
        log_cleaner(self.logfile, 100)
        colorlogger.colorlog(msg, level)

    def is_port_open(self, hostname=None, port=None):
        hostname = hostname if hostname is not None else self.hostname
        port = port if port is not None else 22

        _output = subprocess.getstatusoutput(f'nc -v -z -w1 {hostname} {port}')
        _return = _output[0]
        for _line in _output[1].split('\n'):
            self.colorlog(_line, 'debug')
        return True if _return == 0 else False
        # return True if _output.endswith('(ssh) open') else False

    def ssh_connect(self, hostname=None, port=22, username=None, timeout=10):

        self.colorlog(f'Attempting connect to server {hostname} with port {port}.', 'debug')

        hostname = hostname if hostname is not None else self.hostname
        username = username if username is not None else 'root'

        ssh_cmd = f'ssh {username}@{hostname} -T -o ConnectTimeout={timeout}'
        try:
            self.terminal = subprocess.Popen(ssh_cmd,
                                             stdin=subprocess.PIPE,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             shell=True)

            self.terminal.stdin.write(b'echo EOT\n')
            self.terminal.stdin.flush()

            while True:
                line = self.terminal.stdout.readline().decode().strip('\n')

                if line == 'EOT':
                    break

                if self.display:
                    self.colorlog(line, 'debug')

            self.colorlog('Connection established!', 'debug')
            self.connected = True

        except BrokenPipeError as _e:
            self.colorlog(_e, 'critical')

        return self.connected

    def exec_command(self, command, timeout=None):
        command = f'{command}\n'.encode()
        end_of_term = 'echo EOT $?\n'.encode()

        _return_code = 0
        _output = []

        try:
            self.terminal.stdin.write(command)
            self.terminal.stdin.write(end_of_term)
            self.terminal.stdin.flush()

            while True:
                line = self.terminal.stdout.readline().decode().strip('\n')

                if line.startswith('EOT'):
                    _return_code = line.split()[-1]
                    break

                _output.append(line)

                if self.display:
                    self.colorlog(line, 'debug')

        except BrokenPipeError as _e:
            self.colorlog(_e, 'critical')

        return _return_code, _output

    def getoutput(self, command, timeout=None) -> list:
        """
        return output list after executed.
        """
        _output = []
        _return_code = 0
        self.colorlog(f'Send command [{command}] to remote host.', 'debug')

        if not self.connected:
            self.colorlog(f'[{self.hostname}] not connected.', 'critical')

        else:
            try:
                _return_code, _output = self.exec_command(command, timeout=timeout)
            except ValueError:
                pass

        return _output

    def getstatusoutput(self, command, timeout=None):
        _output = []
        _return_code = 0
        self.colorlog(f'Send command [{command}] to remote host.', 'debug')

        if not self.connected:
            self.colorlog(f'[{self.hostname}] not connected.', 'critical')

        else:
            try:
                _return_code, _output = self.exec_command(command, timeout=timeout)
            except ValueError:
                pass

        _output.insert(0, _return_code)
        return _output

    def key_based_authorize(self, hostname=None, username=None, port=22):
        hostname = hostname if hostname is not None else self.hostname
        username = username if username is not None else 'root'

        _return_code = 0
        _ssh_home = os.path.join(self.home, '.ssh')
        _rsa_pub_key = os.path.join(_ssh_home, 'id_rsa.pub')

        if not os.path.exists(_rsa_pub_key):
            self.colorlog(f'SSH rsa public key [{_rsa_pub_key}] not exist, generate now!', 'info')
            _return_code = os.system("""ssh-keygen -t rsa -P '' -q""")

        _command = f'ssh-copy-id {username}@{hostname} -p {port} 2>&1'
        _output = subprocess.getstatusoutput(_command)
        _return_code += _output[0]

        try:
            _prompt_lines = _output[1].split('\n')
        except IndexError as _e:
            self.colorlog(_e, 'warn')
            _prompt_lines = []

        for _line in _prompt_lines:
            _line = str(_line)
            if 'error' in _line.lower():
                self.colorlog(_line, 'error')
            if 'warning' in _line.lower():
                self.colorlog(_line, 'warn')
            if 'info' in _line.lower():
                self.colorlog(_line, 'info')
        return True if _return_code == 0 else False


if __name__ == '__main__':
    ssh = OpenSshConsole('192.168.1.1')
    ssh.ssh_connect(username='user1')
    print(ssh.getstatusoutput('switchshow'))

    ssh.getoutput('setcontext 99')
    print(ssh.getoutput('switchshow'))





