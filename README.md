<div align="center">
    <img alt="beny-wifi" width="400" src="https://github.com/Jarauvi/beny-wifi/blob/main/images/logo@2x.png?raw=true">

# ⚡ Beny Wifi ⚡

[![Home Assistant](https://img.shields.io/badge/home%20assistant-%2341BDF5.svg)](#)
![Local polling](https://img.shields.io/badge/IOT_class-Local_polling-blue)
![License](https://img.shields.io/badge/License-GPL_3.0-green)
![Version](https://img.shields.io/github/manifest-json/v/Jarauvi/beny_wifi?filename=custom_components%2Fbeny_wifi%2Fmanifest.json&label=Version)

**Home Assistant custom component for ZJ Beny EV chargers over Wifi.**
</div>

---

## 🎉 1-Year Anniversary Update! (March 2026)

One year ago, this project started as a small experiment to decode the ZBox protocol. Today, **Beny Wifi** has grown into a robust community-driven integration supporting multiple charger brands and models, DLB configurations, and practically every single option from ZBox app! Thanks to everyone - by contributing, raising issues and informing about model support we can make this flawless together! 

## 📖 Overview
This integration mimics the **ZBox** mobile app's communication protocol. Any charger compatible with the ZBox app is expected to work with this integration.

> [!IMPORTANT]
> **Version 1.0.0** introduces Home Assistant's native entity naming instead of fixed *[serial]_[key]* format. Existing entity names should remain intact, but if you update from very old version, new entities use new naming logic. If you want to update all entity names to new standard, you can do this by opening created device -> under 3 dots at the top right corner, select "**Recreate entity IDs**"
>
> **Since version 0.8.5**, the integration requires the user to input the **main fuse** value when using DLB (Dynamic Load Balancing) modes. Ensure you set the correct value for your electrical system.

> [!CAUTION]
> This integration is a community project and is **not** affiliated with, endorsed by, or supported by ZJBeny or any other supported brands. **Use at your own risk**.

---

## 📍 Quick Links
- [📖 Overview](#-overview)
- [🔌 Compatibility](#-compatibility)
- [🛠 Installation & Setup](#-installation--setup)
- [📊 Entities & Controls](#-entities--controls)
- [⚡ Service Actions](#-service-actions)
- [🔍 Troubleshooting](#-troubleshooting)

---

## 🔌 Compatibility

### Supported Chargers
Supports both **1-phase** and **3-phase** "smart" chargers (with or without DLB). OCPP-equipped devices may also work, though this is currently unconfirmed. 


**Supported Firmware:**
|  **Firmware** | **Status** |
| :--- | :--- |
| 1.26 | ✅ |
| 1.27 | ✅ |
| 1.28 | ✅ |

**Confirmed Models:**
| **Brand** | **Model** | **Status** |
| :--- | :--- | :--- |
| CHINT | WCP-2SM/S1 | ✅ |
| PlusRite | BCP-A2N-L | ✅ |
| ZJBeny | BCP-AT1N-L | ✅ |
| ZJBeny | BCP-A2-L | ✅ |
| ZJBeny | BCP-A2N-L | ✅ |

*If you have a different model and it works, please [open an issue](https://github.com/Jarauvi/beny-wifi/issues) to let us know!*

---

## 🛠 Installation & Setup

### Option 1: HACS (Recommended)
1. Search for **Beny Wifi** in the HACS Store.
2. *Alternatively:* Go to HACS > Custom Repositories > Paste this repo URL > Select **Integration**.
3. Install and **Restart Home Assistant**.

### Option 2: Manual
1. Copy the `custom_components/beny_wifi` folder to your HA `config/custom_components/` directory.
2. **Restart Home Assistant**.

---

## 🛠 Configuration

### Initial Setup
The integration is configured entirely through the Home Assistant UI.
1. Navigate to **Settings > Devices & Services**.
2. Click **Add Integration** and search for **Beny Wifi**.
3. Follow the guided setup:
   * **Connection:** Enter the IP Address (if not auto-discovered), Port, and your preferred Update Interval (Default: 10s).
   * **Device:** Provide the **Serial Number** (9 digits) and **PIN** (6 digits).
   * **Safe Limits:** Define the min/max current bounds for your UI sliders (Default: 6A–32A).
   * **DLB:** Specify if you have the physical Dynamic Load Balancing module installed. If enabled, you can also configure the **Anti Overload** toggle and its **threshold value** (1–99, Default: 63) here.

### Reconfiguration
If you change your charger's IP or PIN, you don't need to delete the integration. Simply go to the **Beny Wifi** card in Devices & Services and select **Reconfigure**.

---

## 🔍 Troubleshooting

### Common Setup Errors
If the configuration fails, check for these common issues:

| Error Message | Likely Cause |
| :--- | :--- |
| `wrong_pin` | The 6-digit PIN code was denied by the charger. |
| `no_response_timeout` | The charger is not responding. Check your Serial Number and network connection. |
| `cannot_resolve_ip` | The integration could not find the charger by Serial. Try setting the **IP Address manually** in the connection step. |
| `pin_length_invalid` | Ensure your PIN is exactly 6 numeric characters. |
| `serial_length_invalid` | Ensure your Serial Number is exactly 9 numeric characters. |

### Debug Logging
If you encounter persistent issues, please enable debug logging and provide the logs in your [issue report](https://github.com/Jarauvi/beny-wifi/issues):
1. Go to **Settings > Devices & Services**.
2. Find **Beny Wifi** and click the three-dot menu `⋮`.
3. Select **Enable debug logging**.
4. Reproduce the issue, then select **Disable debug logging** to download the log file.

> [!TIP]
> **Privacy Note:** When sharing logs, ensure you obfuscate your PIN code (typically found at characters 13-18 in the UDP payload).

## 📊 Entities & Controls

### Sensors
| Sensor | Unit | Description |
| :--- | :---: | :--- |
| **Charger State** | - | *abnormal, unplugged, standby, starting, unknown, waiting, charging* |
| **Power** | `kW` | Current power consumption |
| **Voltage L1-L3*** | `V` | Voltage per phase (* 3-phase only) |
| **Current L1-L3*** | `A` | Current per phase (* 3-phase only) |
| **Total Energy** | `kWh` | Session based charged capacity |
| **Temperature** | `°C / °F` | Internal charger temperature |
| **DLB Grid Power**** | `kW` | Import/export power from grid (** DLB only) |
| **DLB Solar Power**** | `kW` | Solar production power (** DLB only) |
| **DLB EV Power**** | `kW` | Power currently going to the EV (** DLB only) |
| **DLB House Power**** | `kW` | Power consumed by the house (** DLB only) |
| **Max Current** | `A` | Current limit currently set on the charger |
| **Maximum Session Consumption** | `kWh` | Session based maximum consumption limit |
| **Timer Start / End** | `timestamp` | Currently set charging window (Displays "Not set" if empty) |

### Controls & Configuration
| Entity | Type | Description |
| :--- | :---: | :--- |
| **Max Current Control** | `Number` | Slider to adjust the maximum charging current (6–32A) |
| **Hybrid Current Limit** | `Number` | Current limit in amps when DLB mode is set to Hybrid |
| **Night Mode Start/End** | `Number` | Define the hour window for Night Mode charging (0–23) |
| **Anti Overload Threshold** | `Number` | Threshold value (1–99) used when Anti Overload is enabled |
| **DLB Mode** | `Select` | *Pure PV, Hybrid, Full Speed, or DLB Box* |
| **PV Dynamic Load Balance** | `Switch` | Master toggle for the entire DLB feature |
| **Extreme Mode** | `Switch` | Reduce or stop charging when home load is high |
| **Night Mode** | `Switch` | Enable full-speed charging during the nightly window |
| **Anti Overload** | `Switch` | Toggle Anti Overload protection (initial state and threshold configured during setup) |
| **Start / Stop Charging** | `Button` | Manually trigger charging start or stop |
| **Send Max Current** | `Button` | Push the current slider value to the charger |

*\* 3-phase charger only*
*\** dlb equipped charger only*
---

## ⚡ Service Actions

These services can be used in automations, scripts, or the Developer Tools.

| Service | Description |
| :--- | :--- |
| **Start Charging** | Starts the charging process (EV must be plugged in). |
| **Stop Charging** | Stops the charging process. |
| **Set Timer** | Sets a specific start and end time window for charging. |
| **Reset Timer** | Clears the currently set charging timer. |
| **Set Schedule** | Configures a weekly charging schedule with day-specific toggles. |
| **Set Max Current** | Sets the maximum charging current limit (6–32A). |
| **Set DLB Config** | Configures DLB Mode, Extreme Mode, Night Mode, and Anti-Overload settings. |
| **Set Monthly Limit** | Sets a limit for maximum monthly energy consumption (kWh). |
| **Set Session Limit** | Sets a limit for maximum energy consumption for the current session. |
| **Request Schedule** | Manually requests the current weekly schedule from the charger. |

### Service Details & Fields

<details>
<summary><b>beny_wifi.set_dlb_config</b></summary>

Configures advanced charger behavior. All fields are optional—only supplied fields are changed.

| Field | Description |
| :--- | :--- |
| `dlb_enabled` | Master toggle for the entire DLB feature. |
| `dlb_mode` | Operating mode: `pure_pv`, `hybrid`, `full_speed`, or `dlb_box`. |
| `hybrid_current` | Current limit (6–32A) used specifically in **Hybrid** mode. |
| `extreme_mode` | Reduce/stop charging when total house load is high. |
| `night_mode` | Enable full-speed charging during a specific nightly window. |
| `night_start/end` | Defines the start/end hour (0–23) for Night Mode. |
| `anti_overload` | Toggle Anti Overload protection. |
| `anti_overload_value` | Threshold (1–99) for Anti Overload (Default: 63). |

> [!NOTE]
> The initial Anti Overload state and threshold are configured during integration setup in the **DLB** section. The `set_dlb_config` service can override these at runtime without changing your setup configuration.

</details>

<details>
<summary><b>beny_wifi.set_timer</b></summary>

| Field | Description |
| :--- | :--- |
| `start_time` | Time to begin charging (HH:MM). |
| `end_time` | Time to stop charging (HH:MM). |

</details>

<details>
<summary><b>beny_wifi.set_weekly_schedule</b></summary>

| Field | Description |
| :--- | :--- |
| `monday` - `sunday` | Boolean toggles for each day of the week. |
| `start_time` | Time to begin charging (HH:MM). |
| `end_time` | Time to stop charging (HH:MM). |

</details>

---

## 🔍 Troubleshooting & Debugging

If you encounter issues, you can help by providing a network trace:
1. Use **PCAPdroid** to capture traffic from the **Z-Box** app.
2. Navigate to the main page of the Z-Box app to trigger data updates.
3. Stop capture and inspect **UDP port 3333**.
4. **Note:** Characters 13-18 in the payload represent your PIN. **Obfuscate this** before sharing logs.

Check the `tools/` folder for scripts to simulate charger responses or translate messages.
