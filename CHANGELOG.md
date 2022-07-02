# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [https://norvyn.com](https://norvyn.com).

## [Unreleased]

### [0.0.11] - 2022-06-16
#### Add
- print snmp events to monitor if storage not connected via ssh or OBS detected
- add datetime to HW Storage snmp events line
#### Changed
- change class snmpconsole method snmpwalk_format '_value' line split from ':' to ': '
- change 'N/A' color from red to yellow

### [0.0.10] - 2022-06-15
#### Fixed
- FOS 7 sfp stat does not contain port which has no receiver

#### Changed
- change 'Failed' to 'N/A' if Huawei Storage not connected

### [0.0.9] - 2022-06-14
#### Need
- fetch port index from every line snmpwalk from sfp OID
- change FAILED to N/A when pm Huawei Storage via SSH failed with connection

### [0.0.7] - 2022-03-30
#### Modify
- delete "self.HOME = os.environ['HOME']" parameter in class SshConsole, windows has no this place
- delete color in string 'PASSWD' & 'FAILED'
- agent xiv.py add "_value != 'OK' and _value != 'Ready'"
#### Changed
- change 'snmpwalk', 'snmpget', 'snmptable' command PATH




[Unreleased]: https://norvyn.com
[0.0.5]: https://norvyn.com