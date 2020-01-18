# changegovernor
Change CPU governor based on processes running, on data retrieved by libsensors and finally by the percentage of CPU usage

Detailed informations could be found on my [blog](https://amedeos.github.io/cpu/governor/2020/01/06/change-cpu-governor-automatically.html)
## Usage
Since the program need to write the CPU governor to be used, it need root or sudo grants.
```
$ sudo ./changegovernor.py --help
$ sudo ./changegovernor.py -c changegovernor.json -g -l
```
## Operating flow
<img src="https://github.com/amedeos/changegovernor/raw/master/changegovernor-operatingflow.png" width=800 />
