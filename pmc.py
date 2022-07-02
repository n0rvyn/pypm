#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2021 by ZHANG ZHIJIE.
# All Right Reserved.

# Last Modified Time: 2022/4/12 11:25
# Author: ZHANG ZHIJIE
# Email: beyan@beyan.me
# File Name: pmc.py
# Tools: PyCharm

"""
---Preventive Maintenance Console---
"""
from console import ConfigReader
from agent import huaweistorage
from agent import xiv
from agent import switch
import sys

reader = ConfigReader(production=False)   # set to True for reading configuration from './config/production'


def hw_str_pm():
    storages = reader.read_hw_str()
    huaweistorage.pm_all_hw_storage(storages)


def xiv_pm():
    xiv_list = reader.read_xiv()
    xiv.pm_xiv_all(xiv_list)


def switch_pm():
    switch_list = reader.read_switch()
    switch.pm_all_switch(switch_list)


if __name__ == '__main__':
    try:
        dev = sys.argv[1]

        if dev == 'xiv':
            xiv_pm()
        if dev == 'sw':
            switch_pm()
        if dev == 'hw':
            hw_str_pm()
        if dev == 'all':
            hw_str_pm()
            xiv_pm()
            switch_pm()

    except IndexError:
        print('Supported args: xiv | sw | hw | all')



