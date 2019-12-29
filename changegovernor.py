#!/usr/bin/env python
#
import argparse
from time import sleep
from time import time
from pathlib import Path
import sys
import re
from datetime import datetime
import json
import psutil
import subprocess

__version__ = "0.3.0"

def printMessage(msg, printMSG=False):
    if debug:
        printMSG = True
    if printMSG:
        now = datetime.now()
        date_time = now.strftime("%Y-%m-%d  %H:%M:%S")
        print(date_time, msg)

def checkAvailableGovernor(governor,
    agfile = '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors'):
    try:
        ag = Path(agfile)
        ag.resolve(strict=True)
        for line in ag.open(mode='r'):
            printMessage("CPU Governors: '" + line + "'")
            if re.search(governor, line):
                printMessage("Found governor '" + governor + "'")
                return True
        return False
    except FileNotFoundError:
        printMessage("File '" + agfile + "' doesn't exist... Exit", True)
        sys.exit(1)
    except PermissionError:
        printMessage("No read permission on file '" + agfile + "' ... Exit", True)
        sys.exit(1)

def fileIsJson(jsonfile):
    try:
        json_object = json.load(open(jsonfile))
        printMessage("Content of json file: " + str(jsonfile))
        printMessage(json_object)
    except ValueError as e:
        return False
    return True

def validateConfigurationFile(jsonfile):
    try:
        cf = Path(jsonfile)
        cf.resolve(strict=True)
        cf.open(mode='r')
        if fileIsJson(str(cf.resolve(strict=True))):
            printMessage("Configuration file: '" + jsonfile + "' is a json file... continue")
        else:
            printMessage("Configuration file: '" + jsonfile + "' is NOT a json file... Exit", True)
            sys.exit(1)
    except FileNotFoundError:
        printMessage("File '" + jsonfile + "' doesn't exist... Exit", True)
        sys.exit(1)
    except PermissionError:
        printMessage("No read permission on file '" + jsonfile + "' ... Exit", True)
        sys.exit(1)

def parseArgs(parser):
    global seconds
    global governor
    global defaultgovernor
    global configurationfile
    global restoreseconds
    global debug
    parser.add_argument('-s', '--seconds', type=int, dest='SECONDS',
        default=5, help='Define how many seconds to sleep')
    parser.add_argument('-g', '--change-governor', dest='GOVERNOR',
        action='store_true', default=False, help='Change cpu governor from powersave to performance')
    parser.add_argument('-d', '--default-governor', dest='DEFAULTGOVERNOR',
        default='powersave', help='Default cpu scheduler')
    parser.add_argument('-c', '--config-file', dest='CONFIGURATIONFILE',
        default='/etc/changegovernor.json', help='Configuration file as json')
    parser.add_argument('-r', '--restore-seconds', type=int, dest='RESTORESECONDS',
        default=60, help='How many seconds wait for restoring previus configurations')
    parser.add_argument('-v', '--verbose', dest='DEBUG',
        action='store_true', default=False, help='Activate debug messages')
    parser.add_argument('--version', action='version',
        version='%(prog)s {version}'.format(version=__version__))

    args = parser.parse_args()

    seconds = args.SECONDS
    governor = args.GOVERNOR
    defaultgovernor = args.DEFAULTGOVERNOR
    configurationfile = args.CONFIGURATIONFILE
    restoreseconds = args.RESTORESECONDS
    debug = args.DEBUG

def validateGovernor(governor):
    printMessage("Change governor if needed")
    printMessage("Validate governor '" + governor + "'")
    if checkAvailableGovernor(governor) == False:
        printMessage("Governor: '" + governor + "' not found... Exit", True)
        sys.exit(1)

def checkIfProcessIsRunning(process):
    for proc in psutil.process_iter():
        try:
            if process in proc.name():
                printMessage("Found process '" + process + "' with pid '"
                    + str(proc.pid) + "'")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    printMessage("Process '" + process + "' NOT found")
    return False

def checkProcess(json_object):
    try:
        for p in json_object['processes']:
            process = p['name']
            if (p['state'] != "present") or ( process == "DEFAULTS"):
                printMessage("Skip process '" + process +
                    "' as it's state is not 'present' -> " + p['state'] +
                    " or is DEFAULTS")
                continue
            printMessage("Trying to find process: '" + str(process) + "'")
            if checkIfProcessIsRunning(process):
                return True, process
    except ValueError as e:
        printMessage("An error occurred during checkProcess function... Exit", True)
        sys.exit(1)
    return False, ""

def executeCommand(cmd):
    printMessage("Execute command '" + cmd + "'")
    try:
        subprocess.call(cmd, shell=True)
    except ValueError as e:
        printMessage("An error occurred during executeCommand function... Exit", True)
        sys.exit(1)

def setGovernor(governor):
    printMessage("Setting governor to '" + governor + "'")
    try:
        validateGovernor(governor)
        # first verify if the current governor in use
        g = checkAvailableGovernor(governor, '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor')
        if g:
            printMessage("The governor '" + governor + "' is the current governor")
        else:
            cmd = "echo " + governor + " | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null"
            executeCommand(cmd)
    except ValueError as e:
        printMessage("An error occurred during setGovernor function... Exit", True)
        sys.exit(1)

def processes(json_object, ptime):
    p, pname = checkProcess(json_object)
    if p:
        ptime = int(time())
        for proc in json_object['processes']:
            if ( proc['name'] == pname ) and ( proc['state'] == "present" ):
                if governor:
                    setGovernor(proc['governor'])
                for extra in proc['extra_commands']:
                    if extra != "":
                        executeCommand(extra)
    else:
        if ( ptime > 0 ) and ( ( int(time()) - ptime ) > restoreseconds ):
            ptime = 0
            if governor:
                setGovernor(defaultgovernor)
            for proc in json_object['processes']:
                if ( proc['name'] == "DEFAULTS" ) and ( proc['state'] == "present" ):
                    for extra in proc['extra_commands']:
                        if extra != "":
                            executeCommand(extra)
    return ptime

def sleeper(seconds):
    printMessage("Sleeping: '" + str(seconds) + "' seconds")
    sleep(seconds)

def percentages(json_object, percenttime):
    cpuPercent = float(psutil.cpu_percent())
    for proc in json_object['percentages']:
        if (( cpuPercent >= float(proc['min']) )
            and ( cpuPercent <= float(proc['max']) )
            and ( proc['state'] == "present" )
            and ( int(time())-percenttime > restoreseconds )):
            percenttime = int(time())
            printMessage("Found cpu percentage: '" + proc['name'] + "' --> " + str(cpuPercent))
            if governor:
                setGovernor(proc['governor'])
            for extra in proc['extra_commands']:
                if extra != "":
                    executeCommand(extra)
            return percenttime
    return percenttime

def main():
    parser = argparse.ArgumentParser()
    parseArgs(parser)
    validateConfigurationFile(configurationfile)
    if governor:
        validateGovernor(defaultgovernor)
    json_object = json.load(open(configurationfile))
    ptime = int(time())-(restoreseconds+1)
    percenttime = int(0)
    while True:
        ### set governor based on processes running
        ptime = processes(json_object, ptime)
        while ptime > 0:
            ## TODO: put here the logic to check via PySensor
            ## if critical temperature is reached
            ptime = processes(json_object, ptime)
            sleeper(seconds)
        ### set governor based on percentage
        percenttime = percentages(json_object, percenttime)
        ### finally sleep
        sleeper(seconds)

try:
    main()
except KeyboardInterrupt:
    printMessage("Ctrl-C pressed... Exit", True)
    sys.exit(0)
