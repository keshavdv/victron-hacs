[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Victron Instant Readout Integration

This integration allows exposing data from Victron devices with Instant Readout enabled in Home Assistant.

Supported Devices & Entities:

- SmartShunt 500A/500mv and BMV-712/702 provide the following data:
  - Voltage
  - Alarm status
  - Current
  - Remaining time (mins)
  - State of charge (%)
  - Consumed amp hours
  - Auxilary input mode and value (temperature, midpoint voltage, or starter battery voltage)
- Smart Battery Sense
  - Voltage
  - Temperature (°C)
- Smart Battery Protect
  - Input Voltage
  - Output Voltage
  - Output State
  - Device State
  - Charger Error
  - Alarm Reason
  - Warning Reason
  - Off Reason
- MPPT/Solar Charger
  - Charger State (Off, Bulk, Absorption, Float)
  - Battery Voltage (V)
  - Battery Charging Current (A)
  - Solar Power (W)
  - Yield Today (Wh)
  - External Device Load (A)
- DC/DC Charger
  - Input Voltage
  - Output Voltage
  - Operation Mode
  - Charger Error
  - Off Reason
- AC Charger
  - Output Voltage 1|2|3
  - Output Current 1|2|3
  - Operation Mode
  - Temperature (°C)
  - AC Current

# Installation

## Manual

1. Clone the repository to your machine and copy the contents of custom_components/ to your config directory
2. Restart Home Assistant
3. Setup integration via the integration page.

## HACS

1. Add the integration through this link:
   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=keshavdv&repository=victron-hacs&category=integration)
2. Restart Home Assistant
3. Setup integration via the integration page.

## 🛰️ Adding a Victron Device

After installing the integration, follow these steps to connect your Victron equipment via Bluetooth.

### 🔍 Device Discovery & Setup

1. Ensure your Home Assistant instance has working Bluetooth support.
2. Go to **Settings > Devices & Services**, and look for a discovered device such as `Victron VE.Direct`, `SmartShunt`, or `SmartSolar`.
3. Click **Add** and give the device a name and enter the corresponding encryption key (see below).
4. **Tip:** Home Assistant will show the **MAC address** of the discovered device. Use this to confirm which device you’re configuring by comparing it with the MAC address shown in the VictronConnect app.

---

### 🔑 Get the MAC Address and Encryption Key

You can find both values using the **VictronConnect App**:

1. Open the VictronConnect App and connect to your device.
2. Tap the **gear icon** (⚙️) in the top right corner.
3. Tap the **three-dot menu** (⋮) and select **Product Info**.
4. Scroll to the **Encryption Data** section.
5. Tap **SHOW** to reveal:
   - **MAC Address**
   - **Encryption Key** (called *Advertisement Key* in this integration)

> 💡 Save these values to paste into the Home Assistant configuration screen when prompted.

---

### 🧪 Troubleshooting

- Ensure your Home Assistant host supports Bluetooth (e.g., Home Assistant OS or compatible USB adapter).
- If discovery fails, try restarting Home Assistant or moving your system closer to the Victron hardware.
- Check **Settings > System > Logs** for messages from the `victron_ble` integration.
