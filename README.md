<div align="center">
    <img alt="beny-wifi" height="256px" src="https://github.com/Jarauvi/beny-wifi">
</div>

# beny-wifi

![Home Assistant](https://img.shields.io/badge/home%20assistant-%2341BDF5.svg?style=for-the-badge&logo=home-assistant&logoColor=white)
https://img.shields.io/badge/license-GPL%203.0-green?link=https%3A%2F%2Fopensource.org%2Flicense%2Fgpl-3-0
![License](https://img.shields.io/badge/license-GPL%203.0-green?link=https%3A%2F%2Fopensource.org%2Flicense%2Fgpl-3-0
gi)

:warning: *DISCLAIMER: I DO NOT TAKE ANY RESPONSIBILITY OF DAMAGED OR DESTROYED PROPERTY, INJURIES OR HUMAN CASUALTIES. USE WITH YOUR OWN RISK*

This repository contains Home Assistant addon for controlling and retrieving information from ZJ Beny 3-phase EV chargers. 

This integration mimics ZBox phone app's communication with charger. I think that any charger communicating with ZBox app should work.

### Supported chargers

1-phase chargers and OCPP equipped devices may work, but I have no possibility to confirm that. If you have possibility to test one, please share your results and we'll add the model to supported devices :pray: 

### Confirmed to work with models

| Model              | Firmware version |       Status      |
| ------------------ | ---------------- | ----------------- |
| BCP-AT1N-L         | 1.26             | :heavy_check_mark:|

### Sensors

Currently, integration contains sensor for charger with following parameters

Value: 
- Charger state (standby | waiting | starting charging | charging | abnormal)

Attributes:
- Current A [A]
- Current B [A]
- Current C [A]
- Voltage A [V]
- Voltage B [V]
- Voltage C [V]
- Power [kW]
- Total energy [kWh]
- Timer start time [UTC timestamp]
- Timer end time [UTC timestamp]

### Actions

Currently integration supports following actions:
- start charging
- stop charging
- set timer (start time > end time)

### Roadmap

I am pretty busy with the most adorable baby boy right now, but I'll be adding some bells and whistles when I have a moment:
- action to set max amps
- map missing parameters as sensors (like outdoor temperature)