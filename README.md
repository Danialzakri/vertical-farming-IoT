# 🌱 IoT Vertical Farming Control System

> **Undergraduate Thesis Project**  
> **Institution:** Universiti Kebangsaan Malaysia (UKM)  
> **Faculty:** Fakulti Kejuruteraan dan Alam Bina (FKAB)  
> **Author:** Muhammad Danial Bin Mohamad Zakri  
> **Supervisor:** Prof. Madya Dr. Mohamad Hanif Bin Md Saad

---

## 📖 About This Project

This repository contains the complete source code and documentation for an **IoT-based environmental control system** designed for a **semi-hydroponic vertical farming** setup. The system automates monitoring and control of critical environmental parameters across a 3-tier growing structure, reducing manual supervision and improving operational reliability.

The project was developed to upgrade an existing vertical farm at the **Integra Laboratory, AST Building, UKM**, integrating multi-node ESP32 microcontrollers, a custom Python Tkinter desktop application, and the university's **ThingsSentral** IoT cloud platform.

---

## 🔧 What's Inside

### 1. ESP32 Firmware (`/firmware/`)
The system runs on **three dedicated ESP32 nodes** to distribute processing load and improve reliability:

| Node | Folder | Role | Key Functions |
|:---|:---|:---|:---|
| **ESP32_1** | `esp32_control/` | **Control Node** | Manages 9x LED relays (3 levels × White/Red-Blue/Power) and 1x water pump relay. Handles LED scheduling via NTP timer and receives commands from the desktop app or ThingsSentral cloud. |
| **ESP32_2** | `esp32_sensors/` | **Environmental Monitoring Node** | Reads 3x DHT22 (temperature & humidity) and 3x BH1750 (light intensity) sensors — one set per growing tier. Pushes data to ThingsSentral every 10 seconds and serves data via local HTTP for the desktop app. |
| **ESP32_3** | `esp32_ultrasonic/` | **Water Level Monitoring Node** | Reads 4x HC-SR04 ultrasonic sensors (tank + 3 growing levels), converts distance to percentage, sends Telegram alerts when water drops below 30%, and triggers safety lock to prevent pump dry-run. |

All nodes use **RapidBootWiFi** for fast Wi-Fi reconnection and serve an HTTP `/status` endpoint so the desktop app can poll data locally.

### 2. Desktop Application (`/software/desktop_app/`)
A **Python Tkinter** desktop GUI that acts as the central command center:
- **Real-time monitoring** of all sensor data (temp, humidity, light, water level)
- **Manual / Auto control modes** — switch between local app control or cloud-based ThingsSentral control
- **LED timer scheduling** — set ON/OFF times for each growing level
- **SQLite data logging** — automatic archival of sensor history, tank levels, and system events
- **Plant health rating** — 1-3 star visual rating system for each tier to track crop condition over time
- **Safety lock reset** — UI control to reset pump protection after low-water events

### 3. Documentation & CAD (`/docs/` & `/hardware/`)
- Full thesis report (PDF)
- System photos, GUI screenshots, and wiring diagrams
- 3D-printed housing designs (STL/drawings) for HC-SR04 ultrasonic sensors

---

## 🌡️ Sensors & Hardware Used

| Sensor | Quantity | Parameter Measured | Placement |
|:---|:---:|:---|:---|
| **DHT22** | 3 | Temperature (±0.5°C) & Relative Humidity (±2% RH) | One per growing tier (Level 1, 2, 3) |
| **BH1750** | 3 | Ambient Light Intensity (lux) | One per growing tier |
| **HC-SR04** | 4 | Water Level / Distance (2 cm – 400 cm, ±3 mm) | Tank + 3 plant containers |
| **ESP32 DevKit V1** | 3 | Main microcontroller & Wi-Fi communicator | Control, Sensor, and Ultrasonic nodes |
| **Relay Module** | 1 (9-channel + 1-channel) | Switching LED panels & water pump | Integrated with ESP32_1 |

**Growing Medium:** Lightweight Expanded Clay Aggregate (LECA)  
**Irrigation:** Recirculating drip system with water pump  
**Lighting:** LED grow lights (White + Red-Blue spectrum) per tier

---

## 🏗️ System Architecture

```
┌─────────────────┐     Wi-Fi      ┌──────────────────┐
│   ESP32_2       │───────────────→│  ThingsSentral   │
│ (DHT22+BH1750)  │                │   Cloud Platform │
└─────────────────┘                └────────┬─────────┘
                                            │
┌─────────────────┐     Wi-Fi      ┌────────▼─────────┐
│   ESP32_3       │───────────────→│   Desktop App    │
│ (HC-SR04 +      │←───────────────│  (Python Tkinter)│
│  Telegram Bot)  │   HTTP Polling └──────────────────┘
└─────────────────┘                         │
┌─────────────────┐                         │ SQLite
│   ESP32_1       │←────────────────────────┘
│ (LED + Pump     │    HTTP Commands
│  Relays)        │    (Manual Mode)
└─────────────────┘
```

---

## 🚀 Quick Start

### Hardware Setup
1. Flash each ESP32 with its respective firmware from `/firmware/`
2. Configure Wi-Fi credentials via the captive portal (RapidBootWiFi)
3. Wire sensors and relays according to the pin mappings in each `.ino` file
4. Install 3D-printed HC-SR04 housings on plant containers and tank

### Desktop App
```bash
cd software/desktop_app
pip install -r requirements.txt
python main.py
```

> ⚠️ **Note:** Before uploading, replace placeholder values for `BOT_TOKEN` and `CHAT_ID` in `esp32_ultrasonic.ino` with your own Telegram bot credentials.

---

## 🛡️ Safety Features

- **Dry-Run Protection:** Pump automatically stops when tank water level falls below **20%**
- **Telegram Alerts:** Critical water level warnings sent when any tank/container drops below **30%**
- **Cooldown Logic:** Prevents spam alerts with a 5-minute cooldown between Telegram messages
- **Safety Lock:** Manual controls are blocked until the safety lock is physically reset via the desktop app

---

## 📚 What is Vertical Farming?

**Vertical farming** is a method of growing crops in vertically stacked layers, typically inside a controlled indoor environment. Instead of spreading outward across fields, it expands **upward**, making it ideal for urban areas with limited land.

### Why It Matters
- 🌍 **Land Efficiency:** Produces more food per square meter than traditional farming
- 💧 **Water Savings:** Uses **70–95% less water** through recirculating hydroponic systems
- 🌦️ **Climate Independence:** Grows year-round regardless of external weather
- 🏙️ **Urban Friendly:** Can be deployed in buildings, laboratories, or small indoor spaces

### This Project's Approach: Semi-Hydroponic
This system uses a **semi-hydroponic** method with **LECA** (Lightweight Expanded Clay Aggregate) as a solid support medium. Water and nutrients are delivered via a drip irrigation system, combining the stability of soil-like support with the efficiency of hydroponic nutrient delivery.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- **Prof. Madya Dr. Mohamad Hanif Bin Md Saad** — Project supervision and guidance
- **Universiti Kebangsaan Malaysia (UKM)** — Research facilities and the ThingsSentral IoT platform
- **Integra Laboratory, AST Building** — Deployment site for the prototype
