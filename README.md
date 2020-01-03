# changegovernor
Change CPU governor based on processes running, on data retrieved by libsensors and finally by the percentage of CPU usage
## Usage
Since the program need to write the CPU governor to be used, it need root or sudo grants.
```
$ sudo ./changegovernor.py --help
$ sudo ./changegovernor.py -c changegovernor.json -g -l
```

