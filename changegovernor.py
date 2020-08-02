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

__version__ = "0.5.5"

def printMessage(msg, printMSG=False):
    """
    Print on standart output messages
    """
    if debug:
        printMSG = True
    if printMSG:
        now = datetime.now()
        date_time = now.strftime("%Y-%m-%d  %H:%M:%S")
        print(date_time, msg)

def checkAvailableGovernor(governor,
    agfile = '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors'):
    """
    Return boolean if the governor exist or not
    """
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

def checkAvailableEnergyPerformance(lenergyPerformance,
    agfile = '/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences'):
    """
    Return boolean if the energyPerformance exist or not
    """
    try:
        ag = Path(agfile)
        ag.resolve(strict=True)
        for line in ag.open(mode='r'):
            printMessage("CPU energyPerformance: '" + line + "'")
            if re.search(lenergyPerformance, line):
                printMessage("Found energyPerformance '" + lenergyPerformance + "'")
                return True
        return False
    except FileNotFoundError:
        printMessage("File '" + agfile + "' doesn't exist... disabling energyPerformance", True)
        global energyPerformance
        energyPerformance = False
        return False
    except PermissionError:
        printMessage("No read permission on file '" + agfile + "' ... Exit", True)
        sys.exit(1)

def fileIsJson(jsonfile):
    """
    Return true if the jsonfile is a valid json
    """
    try:
        json_object = json.load(open(jsonfile))
        printMessage("Content of json file: " + str(jsonfile))
        printMessage(json_object)
    except ValueError as e:
        return False
    return True

def validateConfigurationFile(jsonfile):
    """
    Validate the json configuration file
    """
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
    global energyPerformance
    global defaultenergyPerformance
    global configurationfile
    global restoreseconds
    global libsensors
    global debug
    parser.add_argument('-s', '--seconds', type=int, dest='SECONDS',
        default=5, help='Define how many seconds to sleep')
    parser.add_argument('-g', '--change-governor', dest='GOVERNOR',
        action='store_true', default=False, help='Change cpu governor from default to the choosed one')
    parser.add_argument('-d', '--default-governor', dest='DEFAULTGOVERNOR',
        default='powersave', help='Default (powersave) cpu scheduler')
    parser.add_argument('-e', '--change-energy-erformance', dest='ENERGYPERFORMANCE',
        action='store_true', default=False, help='Change cpu energy performance from default to the choosed one')
    parser.add_argument('-D', '--default-energy-performance', dest='DEFAULTENERGYPERFORMANCE',
        default='power', help='Default (power) cpu energy performance')
    parser.add_argument('-c', '--config-file', dest='CONFIGURATIONFILE',
        default='/etc/changegovernor.json', help='Configuration file as json')
    parser.add_argument('-r', '--restore-seconds', type=int, dest='RESTORESECONDS',
        default=10, help='How many seconds wait for restoring default configurations')
    parser.add_argument('-l', '--sensors', dest='LIBSENSORS',
        action='store_true', default=False, help='Activate temperatures detection via libsensors')
    parser.add_argument('-v', '--verbose', dest='DEBUG',
        action='store_true', default=False, help='Activate debug messages')
    parser.add_argument('--version', action='version',
        version='%(prog)s {version}'.format(version=__version__))

    args = parser.parse_args()

    seconds = args.SECONDS
    governor = args.GOVERNOR
    defaultgovernor = args.DEFAULTGOVERNOR
    energyPerformance = args.ENERGYPERFORMANCE
    defaultenergyPerformance = args.DEFAULTENERGYPERFORMANCE
    configurationfile = args.CONFIGURATIONFILE
    restoreseconds = args.RESTORESECONDS
    libsensors = args.LIBSENSORS
    debug = args.DEBUG

def validateGovernor(governor):
    """
    Validate if the input governor name is a valid
    governor present on the host
    """
    printMessage("Validate governor '" + governor + "'")
    if checkAvailableGovernor(governor) == False:
        printMessage("Governor: '" + governor + "' not found... Exit", True)
        sys.exit(1)

def validateEnergyPerformance(energyPerformance):
    """
    Validate if the input energyPerformance name is a valid
    energyPerformance present on the host
    """
    printMessage("Validate energyPerformance '" + energyPerformance + "'")
    if checkAvailableGovernor(energyPerformance) == False:
        printMessage("Energy performance: '" + energyPerformance + "' not found... Exit", True)
        sys.exit(1)

def checkIfProcessIsRunning(process):
    """
    Return boolean, based on the presence of the process
    running on the host
    """
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
    """
    Loop for the 'processes' objects in the json and verify
    for every of them, if is running on the host, and on this
    case return True and the name of process
    """
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
    """
    Execute command on the host
    """
    printMessage("Execute command '" + cmd + "'")
    try:
        subprocess.call(cmd, shell=True)
    except ValueError as e:
        printMessage("An error occurred during executeCommand function... Exit", True)
        sys.exit(1)

def setGovernor(governor):
    """
    Set the desired governor as the current one
    """
    printMessage("Setting governor to '" + governor + "'")
    try:
        # validate the governor
        validateGovernor(governor)
        # first verify if the current governor in use
        g = checkAvailableGovernor(governor, '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor')
        if g:
            printMessage("The governor '" + governor + "' is the current governor")
        else:
            printMessage("Change to governor: '" + governor + "'", True)
            cmd = "echo " + governor + " | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null"
            executeCommand(cmd)
    except ValueError as e:
        printMessage("An error occurred during setGovernor function... Exit", True)
        sys.exit(1)

def setEnergyPerformance(energyPerformance):
    """
    Set the desired energyPerformance as the current one
    """
    printMessage("Setting energyPerformance to '" + energyPerformance + "'")
    try:
        # validate the energyPerformance
        validateEnergyPerformance(energyPerformance)
        # first verify if the current energyPerformance in use
        g = checkAvailableEnergyPerformance(energyPerformance, '/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference')
        if g:
            printMessage("The energyPerformance '" + energyPerformance + "' is the current energyPerformance")
        else:
            if Path('/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference').is_file():
                printMessage("Change to energyPerformance: '" + energyPerformance + "'", True)
                cmd = "echo " + energyPerformance + " | tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference > /dev/null"
                executeCommand(cmd)
    except ValueError as e:
        printMessage("An error occurred during setEnergyPerformance function... Exit", True)
        sys.exit(1)

def processes(json_object, ptime):
    """
    Loop for processes and set the corresponding governor, energyPerformance,
    and execute every extra commands required by user
    If no process will be found return 0
    """
    p, pname = checkProcess(json_object)
    if p:
        # one of the process was found
        ptime = int(time())
        for proc in json_object['processes']:
            if ( proc['name'] == pname ) and ( proc['state'] == "present" ):
                if governor:
                    setGovernor(proc['governor'])
                if energyPerformance:
                    setEnergyPerformance(proc['energyPerformance'])
                for extra in proc['extra_commands']:
                    if extra != "":
                        executeCommand(extra)
    else:
        # no process found, but before to set the default governor
        # we've to wait until the 'restoreseconds'
        if ( ptime > 0 ) and ( ( int(time()) - ptime ) > restoreseconds ):
            ptime = 0
            if governor:
                setGovernor(defaultgovernor)
            if energyPerformance:
                setEnergyPerformance(defaultenergyPerformance)
            for proc in json_object['processes']:
                if ( proc['name'] == "DEFAULTS" ) and ( proc['state'] == "present" ):
                    for extra in proc['extra_commands']:
                        if extra != "":
                            executeCommand(extra)
    return ptime

def sleeper(seconds):
    """
    Sleep for the desired seconds
    """
    printMessage("Sleeping: '" + str(seconds) + "' seconds")
    sleep(seconds)

def percentages(json_object, percenttime):
    """
    Loop for the percentages objects in the json file
    and set the desired governor for the corresponding 
    range (min >= VALUE <= max)
    """
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
            if energyPerformance:
                setEnergyPerformance(proc['energyPerformance'])
            for extra in proc['extra_commands']:
                if extra != "":
                    executeCommand(extra)
            return percenttime
    return percenttime

def percentage(part, whole):
    """
    Return percentage in float value
    """
    try:
        return 100.0 * float(part)/float(whole)
    except ZeroDivisionError:
        printMessage("When calculating a percentage the whole part is zero", True)
        return 0

def sensors(json_object, stime):
    """
    Loop for the sensors objects in the json file and
    if the corresponding libsensors value is near (in %)
    to the critical value found, set the governor and
    the extra commands
    """
    if libsensors == False:
        # libsensors disabled
        stime = 0
        return stime
    try:
        temp = float(0)
        crit = float(0)
        stemps = psutil.sensors_temperatures()
        for s in json_object['sensors']:
            # try to find sensors's name in libsensors
            slist = stemps.get(s['name'])
            if (slist and
                s['state'] == "present"):
                printMessage("sensors - Found sensor '" + s['name'] + "'")
                for l in slist:
                    if l.label == s['label']:
                        printMessage("sensors - Found  label '" +
                            s['label'] + "' for sensor '" + s['name'] + "'")
                        temp = l.current
                        crit = l.critical
                        printMessage("sensors - " + s['name'] +
                            " " + s['label'] + " temperature: " + str(temp))
                        printMessage("sensors - " + s['name'] +
                            " " + s['label'] + " critical: " + str(crit))
                        if (isinstance(temp, (int, float)) and
                            isinstance(crit, (int, float))):
                            # now we can calculate the percentages from critical
                            p = percentage(temp, crit)
                            printMessage("sensors - temperature " + str(temp) + " are " +
                                str(p) + "% of critical " + str(crit))
                            if (float(s['percent_from_critical']) >= (100.0 - p) ):
                                # we are reaching the critical temp
                                stime = int(time())
                                setGovernor(s['governor'])
                                setEnergyPerformance(s['energyPerformance'])
                                for extra in s['extra_commands']:
                                    if extra != "":
                                        executeCommand(extra)
                                return stime
                            else:
                                stime = 0
                                continue
                        else:
                            printMessage("sensors - temperetures are not integers or floats... skipping")
                            continue
                    else:
                        printMessage("sensors - Sensor NOT to be monitored '" + s['name'] +
                            "' label '" + l.label + "'")
                        continue
            printMessage("sensors - end sensor '" + s['name'])
        return stime
    except Exception as e:
        printMessage("Error on sensors function")
        print(e)
        sys.exit(1)
    return stime

def main():
    # parsing command line parameters
    parser = argparse.ArgumentParser()
    parseArgs(parser)
    # check if the configuration file is a valid json
    validateConfigurationFile(configurationfile)
    json_object = json.load(open(configurationfile))
    # set ptime in the past to force default
    # governor initialization
    ptime = int(time())-(restoreseconds+1)
    percenttime = int(0)
    stime = int(0)
    while True:
        # first check the sensors temperatures
        # and loop until below the critical
        stime = sensors(json_object, stime)
        if stime == 0:
            # set governor based on processes running
            ptime = processes(json_object, ptime)
            while ptime > 0:
                # again, check if critical temperatures
                # was reached
                stime = sensors(json_object, stime)
                if stime > 0:
                    # return to main / sensors loop
                    break
                ptime = processes(json_object, ptime)
                sleeper(seconds)
            # set governor based on percentages
            percenttime = percentages(json_object, percenttime)
        # at the end we can sleep
        sleeper(seconds)

try:
    main()
except KeyboardInterrupt:
    printMessage("Ctrl-C pressed... Exit", True)
    sys.exit(0)
