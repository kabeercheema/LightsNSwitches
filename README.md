

# Lights and Switches Raspberry Pi CAN Lights & Switch Controller

> Multi-threaded Python service on a Raspberry Pi that reads **physical switches**, drives **indicator lights**, and communicates with vehicle ECUs over **CAN** using a Waveshare 2-CH CAN HAT (MCP2515/SocketCAN).

![Vehicle console prototype](assets/vehicle-console.jpg)

---

## What this service does

- **Listens** on CAN for *status light commands* from ECUs and updates LEDs:
  - `PSC_Lights_MSG_ID = 0x700` → Propulsion & HV system lights
  - `ADAS_Lights_MSG_ID = 0x701` → CAV Longitudinal, Lateral, and V2X lights
- **Publishes** the *switch positions* from the console to ECUs:
  - `LnS_SwitchStatus_MSG_ID = 0x702`
- Supports (reserved/for future expansion): `LnS_LightsStatus_MSG_ID = 0x703`  
- Uses **cantools + a DBC** to encode/decode frames.
- Runs **two daemon threads**:
  - `lights()` — CAN **RX** + LED state machine
  - `switches()` — GPIO **inputs** + CAN **TX**
- Detects **loss of comms** and **flashes** all lights as a fault indicator.
- Cleans up GPIO and CAN gracefully on exit.

---

## Hardware, interfaces, pins

- **Raspberry Pi** (BCM numbering) + Waveshare **2-CH CAN HAT** (SocketCAN).
- CAN channel: **`can1`** (filters set for `0x700` and `0x701` only).
- **Switch input pins** (pull-up, active-low): `17, 27, 22, 5`
- **Light output pins**:  
  - `PropSysLightPin = 23`  
  - `HVSysLightPin = 24`  
  - `CAVLongCtrlLightPin = 12`  
  - `CAVLatCtrlLightPin = 16`  
  - `CAVV2XCtrlLightPin = 7`

> All outputs initialize **LOW** (lights off). Inputs use `PUD_UP` so a closed switch reads **0 → OFF**, **1 → ON** after inversion in software.

---

## Light states (per LED)

The LED state machine is centralized in `set_light_state()`:

- **0 = OFF** → `GPIO.LOW`  
- **1 = ON** → `GPIO.HIGH`  
- **2 = FLASH** → periodic toggle via `toggle_light()`  

`lights()` sets **state = 2 (FLASH)** automatically on **decode failure** or **comms loss** (see below).

---

## Thread model

### 1) `lights()` — CAN RX + LED control
- Blocks on `bus.recv(0.5)` and decodes any message using the DBC.
- On `0x700` (PSC): updates **PropSys** & **HV** states from signals  
- On `0x701` (ADAS): updates **CAV Long**, **CAV Lat**, **CAV V2X** states
- If a message **decodes**, comms are considered **healthy**; any prior fault clears and all states reset to **0 (OFF)** before following the decoded values.
- If a message **fails to decode**, sets `led_control_mode_normal = False` and forces **FLASH** for all LEDs.
- Only **writes GPIO** when a state actually changes (reduced flicker).

### 2) `switches()` — GPIO read + CAN TX
- Polls the four switch inputs, converts to **0=OFF / 1=ON** semantics.
- Encodes `LnS_SwitchStatus_MSG_ID (0x702)` with DBC signals:
  - `LnS_RegenBrakingSwitchStatus`
  - `LnS_CAVLongControlSwitchStatus`
  - `LnS_CAVLatControlSwitchStatus`
  - `LnS_CAVV2XControlSwitchStatus`
- Sends the frame on **`can1`** (with a short back-off if the TX queue is full).

Both threads share a **mutex (`lock`)** around bus access and state updates to avoid race conditions. The main thread stays alive and joins the daemons; on `KeyboardInterrupt` it turns **all LEDs off**, calls `GPIO.cleanup()`, and **shuts down** the CAN bus.

---

## Communication watchdog & fault behavior

- A timestamp is updated whenever **any** CAN message is received.  
- If **no frames** are seen for **5.0 s**, the app logs a warning and:
  1. Forces `led_control_mode_normal = False`
  2. **Turns all LEDs off once** to sync the flash phase
  3. Sets every LED to **state = 2 (FLASH)**

As soon as valid frames decode again, comms are marked **restored**, all states reset to **0**, and normal LED control resumes.

---

## DBC usage

- The app loads `EVC_DataLogging_Rev3_EDITED.dbc` at startup and resolves:
  - `LnS_SwitchStatus` (TX)  
  - `LnS_LightsStatus` (reserved/for future)  
- Incoming `0x700`/`0x701` frames are decoded by frame ID → signals listed above.  
> Ensure the DBC on the Pi matches the deployed ECU definitions.

---

## CAN setup (example)

Kernel overlays (in `/boot/config.txt`):
```ini
dtparam=spi=on
dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=24
dtoverlay=spi-bcm2835
