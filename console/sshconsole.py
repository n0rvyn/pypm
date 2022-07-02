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
import paramiko
import subprocess
import platform


_HOME_ = os.path.abspath(os.path.dirname(__file__))
_ROOT_ = os.path.join(_HOME_, '..')
_LOG_PATH_ = os.path.join(_ROOT_, 'log')
_LOG_FILE_ = os.path.join(_LOG_PATH_, 'console.log')
os.mkdir(_LOG_PATH_) if not os.path.exists(_LOG_PATH_) else ''
_OS_ = platform.system().lower()

sys.path.insert(0, _ROOT_)
from console import ColorLogger
from console import log_cleaner


class SshConsole(paramiko.SSHClient):
    def __init__(self, hostname, display=True, logfile=None):
        paramiko.SSHClient.__init__(self)
        self.logger_prefix = 'SSH'
        self.logger_suffix = hostname
        self.display = display

        self.hostname = hostname
        self.chan = None
        self.connected = False

        self.logfile = logfile if logfile is not None else _LOG_FILE_
        self.home = os.environ['HOME'] if _OS_ == 'linux' else None

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

    def ssh_connect(self, hostname=None, port=22, username=None, password=None,
                    pkey=None, key_filename=None, timeout=10,
                    allow_agent=True, look_for_keys=True, compress=False, sock=None,
                    gss_auth=False, gss_kex=False, gss_deleg_creds=True, gss_host=None,
                    banner_timeout=None, auth_timeout=5,
                    gss_trust_dns=True, passphrase=None, disabled_algorithms=None):
        self.load_system_host_keys()
        self.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.colorlog(f'Attempting connect to server {hostname} with port {port}.', 'debug')

        hostname = hostname if hostname is not None else self.hostname
        password = str(password) if password is not None else ''

        try:
            self.connect(hostname=hostname,
                         port=port,
                         username=username,
                         password=password,
                         pkey=pkey,
                         key_filename=key_filename,
                         timeout=timeout,
                         allow_agent=allow_agent,
                         look_for_keys=look_for_keys,
                         compress=compress,
                         sock=sock,
                         gss_auth=gss_auth,
                         gss_kex=gss_kex,
                         gss_deleg_creds=gss_deleg_creds,
                         gss_host=gss_host,
                         banner_timeout=banner_timeout,
                         auth_timeout=auth_timeout,
                         gss_trust_dns=gss_trust_dns,
                         passphrase=passphrase,
                         disabled_algorithms=disabled_algorithms)
            self.colorlog('Connection established!', 'debug')
            self.connected = True
            return True

        except paramiko.ssh_exception.NoValidConnectionsError as e:
            self.colorlog(e, 'error')
        except socket.timeout as e:
            self.colorlog(e, 'critical')
        except OSError as e:
            self.colorlog(e, 'warn')
        except paramiko.ssh_exception.AuthenticationException as e:
            self.colorlog(e, 'warn')
        except paramiko.ssh_exception.SSHException as e:
            self.colorlog(e, 'warn')
        return False

    def getoutput(self, command, timeout=None) -> list:
        """
        return output list after executed.
        """
        _output = []
        self.colorlog(f'Send command [{command}] to remote host.', 'debug')

        if not self.connected:
            self.colorlog(f'[{self.hostname}] not connected.', 'critical')
            return _output

        if command.endswith('&') or command.startswith('setcontext'):  # todo setcontext always failed
            self.colorlog('Command ends with [&], this is a backend command, no output will be return.', 'info')
            self.colorlog(f'Execute command [{command}] via channel.', 'info')
            _channel = self.get_transport().open_session()
            _channel.exec_command(command)
            return _output

        try:
            stdin, stdout, stderr = self.exec_command(command, timeout=timeout)

            _output, _error = stdout.readlines(), stderr.readlines()
            _output = [_line.strip('\n') for _line in _output]
            _error = [_line.strip('\n') for _line in _error]

            _error = ''.join(_error).strip('\n')
            if _error:
                self.colorlog(_error, 'error')

            return _output  # todo verify type of 'stdout'

        except AttributeError as _e:
            self.colorlog(_e, 'error')
        except paramiko.ssh_exception.SSHException as _e:
            self.colorlog(_e, 'critical')
        except EOFError as _e:
            self.colorlog(_e, 'critical')
        except ValueError as _e:
            self.colorlog(_e, 'error')
        return _output

    def getstatusoutput(self, command, timeout=None):
        _output = self.getoutput(command)
        _return = self.getoutput('echo $?')[0]
        _output.insert(0, _return)
        return _output

    def key_based_authorize(self, hostname=None, username=None, port=None):
        hostname = hostname if hostname is not None else self.hostname
        username = username if username is not None else self.username
        port = port if port is not None else self.port

        _return_code = 0

        if self.home is None:
            return False

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

    def getstatusbackend(self, process):
        # pidof -x process
        # pgrep -f process
        # ps -ef | grep process | grep -v grep
        return True if self.getstatusoutput(f'ps -ef | grep {process} | grep -v grep')[0] == 0 else False


class SftpConsole(SshConsole):
    def __init__(self, hostname):
        self._transport = self.get_transport()
        self.hostname = hostname

        # create sftp transport
        self.colorlog('Establish sftp connection.', 'debug')
        try:
            self.sftp = paramiko.SFTPClient.from_transport(self._transport)
        except paramiko.sftp.SFTPError as error:
            self.colorlog(error, 'critical')

        SshConsole.__init__(self, self.hostname)

    def put(self):
        pass

    def get(self):
        pass

    def ls(self):
        pass

    def put_dir(self):
        pass

    def get_dir(self):
        pass


if __name__ == '__main__':
    pass


