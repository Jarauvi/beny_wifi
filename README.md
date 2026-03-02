<div align="left">
    <img alt="beny-wifi" width="50%" src="https://github.com/Jarauvi/beny-wifi/blob/main/images/logo@2x.png?raw=true">
</div>

# ⚡ Beny Wifi ⚡

<div align="left">
    <img alt="Home Assistant" src="https://img.shields.io/badge/home%20assistant-%2341BDF5.svg"/>
    <img alt="Local polling" src="https://img.shields.io/badge/IOT_class-Local_polling-blue">
    <img alt="Static Badge" src="https://img.shields.io/badge/License-GPL_3.0-green">
    <img alt="Version" src="https://img.shields.io/github/manifest-json/v/Jarauvi/beny_wifi?filename=custom_components%2Fbeny_wifi%2Fmanifest.json&label=Version">
</div>

*PRs accepted! My progress with this integration is veeery slow right now and I definitely appreciate help!*

⚠️*DISCLAIMER: I DO NOT TAKE ANY RESPONSIBILITY OF DAMAGED OR DESTROYED PROPERTY, INJURIES OR HUMAN CASUALTIES. USE AT YOUR OWN RISK*

<div align="left">
    <img alt="Sensors" height="256px" src="https://github.com/Jarauvi/beny-wifi/blob/main/images/sensors.png?raw=true">
</div>

This repository contains Home Assistant custom component for communicating with ZJ Beny EV chargers over Wifi. 

Integration mimics ZBox phone app's communication with charger. All parameters and commands are not mapped yet, but assumption is that any charger communicating with ZBox app should work with integration.

### Supported chargers

Integration should support 1-phase and 3-phase "smart" chargers with or without DLB. Also OCPP equipped devices may work, but I've had no possibility to confirm that. If you have one and you're willing to test the compatibility, please share your results and I will add the model to supported devices 🙏 

### Confirmed to work with models

| Model              | Firmware version |       Status      |
| ------------------ | ---------------- | ----------------- |
| BCP-AT1N-L         | 1.26             | ✅                |
| BCP-A2-L           | 1.26             | WIP               |

### Installation

**Using HACS**

You can now find this plugin from HACS Store! 

Or alternatively add repository to HACS:
- Click three dots in the upper right corner of HACS.
- From the menu, select Custom Repositories
- Paste link of this repository to Repository field
- Select "integration" to Type field
- Find and install Beny Wifi from the list of integrations
- Restart Home Assistant

**Manually**
- Copy contents of custom_components/beny_wifi folder of this repository to config/custom_components/beny_wifi folder in Home Assistant

**Configuration**
- Find Beny Wifi integration under Settings > Devices & services
- Insert charger serial number and pin. Also scan interval of the sensors can be configured

### Sensors

Currently, integration creates charger device with following sensors:

| Sensor             | Unit            | Description                                                                   |
| ------------------ | --------------- | ----------------------------------------------------------------------------- |
| state              | [charger state] | Charger state *(abnormal unplugged standby starting unknown waiting charging)*|
| current1           | [A]             | Current L1                                                                    |
| current2*          | [A]             | Current L2                                                                    |
| current3*          | [A]             | Current L3                                                                    |
| voltage1           | [V]             | Voltage L1                                                                    |
| voltage2*          | [V]             | Voltage L2                                                                    |
| voltage3*          | [V]             | Voltage L3                                                                    |
| power              | [kW]            | Current power consumption                                                     |
| total_energy       | [kWh]           | Session based charged capacity                                                |
| temperature        | [C / F]         | Charger temperature
| maximum_session_consumption       | [kWh]           | Session based maximum consumption                                                |
| timer_start        | [timestamp]     | Currently set timer start time                                                |
| timer_end          | [timestamp]     | Currently set timer end time                                                  |
| grid_power**      | [kW]            | Import/export power from grid                                                  |
| solar_power**      | [kW]            | Solar power                                                                   |
| ev_power**         | [kW]            | Power for charging EV                                                         |
| house_power**      | [kW]            | Power for house                                                               |

* 3-phase charger only
* dlb equipped charger only

### Actions

Currently integration supports following actions:

Controls for Setting Maximum charge current.

*Only when EV is plugged to charger:*
- beny_wifi.start_charging (*device_id*)
- beny_wifi.stop_charging (*device_id*)
- beny_wifi.set_timer (*device_id | start time | end time*)
- beny_wifi.reset_timer (*device_id*)
- beny_wifi.set_maximum_session_consumption (*device_id | maximum_consumption*)

*Any state:*
- beny_wifi.request_weekly_schedule (*device_id*)
- beny_wifi.set_weekly_schedule (*device_id | sunday | monday | tuesday | wednesday | thursday | friday | saturday | start time | end time)
- beny_wifi.set_maximum_monthly_consumption (*device_id | maximum_consumption*)

### Roadmap

I am pretty busy with the most adorable baby boy right now, but I'll be adding some bells and whistles when I have a moment:

### Troubleshooting guide

   1. Get [PCAPdroid](https://github.com/emanuele-f/PCAPdroid)
   2. Open that up and select traffic dump to PCAP file and from target apps select Z-Box. Do not start capture yet (on my phone Z-Box did not want to connect to charger while capturing)
   3. Open Z-Box and enter the main page of device where the values and data are shown and updated
   4. Now go back to PCAPdroid and press circle with "Ready". Record a couple kb of data and stop capturing
   5. Under three dots in upper right corner, select Open PCAP file. By default, it is saved to Downloads > PCAPdroid
   6. The interesting part is UDP to port 3333
   7. From there you can check Payload tab with both request and response
   
For privacy, just keep in mind that characters 13-18 are your pin code, obfuscate it before sharing if you wish to keep it private

Tools folder has some scripts that may help:
- simple udp server that can be used for simulating charger responses
- tool for converting pcap-file to json that simulator can read
- script for translating messages
