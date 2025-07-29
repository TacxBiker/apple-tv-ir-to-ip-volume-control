# Apple TV Remote IR to IP Volume Control

This project allows you to use the volume buttons of an (Apple TV) infrared remote to control IP-based volume, for example towards a Gira HomeServer or Marantz receiver. The code runs on a Raspberry Pi Pico W and provides a web interface for configuration and simulation.

**Update:**  
This project can be used to send TCP and UDP packets when IR signals are received. Both the IR signals to be detected and the codes to be sent (via TCP/UDP) are fully configurable via the web interface and the `config.json`. This makes the project flexible for a wide range of IR-to-IP automation use cases.

## Features

- **IR to IP**: Receives NEC IR codes and sends volume or power commands via UDP or TCP to the correct devices.
- **Configurable IR & IP Mapping**: Both the IR codes to be detected and the corresponding commands to be sent (TCP or UDP) are fully configurable.
- **Web Interface**: Configure settings like IP addresses, ports, commands, and NTP servers through a simple web page.
- **IR Simulation**: Trigger volume and power commands directly from the web interface.
- **Logs**: Built-in logging visible on the web interface.
- **Configuration**: Settings are stored in `config.json`.

## UDP and TCP Use

- The **Gira HomeServer** is used in this project to send commands to KNX, but you can also configure UDP to send directly to any other device that accepts it.
- The HomeServer receives commands via **UDP**, as this is fast and lightweight.
- The **Marantz** receiver receives commands via **TCP**; Marantz only accepts TCP.
- You can choose (via the web interface) to send volume commands to either the Gira (UDP) or the Marantz (TCP).
- The **power on** and **power off** commands are always sent to the Gira (UDP).

## Connection Diagram (Aansluitschema)

Below is the wiring diagram for connecting the IR receiver and (optional) status LEDs to the Raspberry Pi Pico W.

### IR Receiver

- The tested and recommended IR receiver is the **VS1838B 38 KHz Infrared Receiver**.

| IR Receiver Pin | Connect to Pico W |
|-----------------|------------------|
| OUT             | GPIO 15          |
| VCC             | 3.3V             |
| GND             | GND              |

### Optional Status LEDs

| LED Function      | Connect to Pico W | Series Resistor (recommended) |
|-------------------|------------------|-------------------------------|
| Status LED        | GPIO 12          | 220 Ω                         |
| Power ON LED      | GPIO 14          | 220 Ω                         |
| Power OFF LED     | GPIO 13          | 220 Ω                         |

- Connect the **anode** (long leg) of each LED to the specified GPIO pin via a resistor.
- Connect the **cathode** (short leg) of each LED to GND.
- The LEDs are optional; the project works without them.

```
  [VS1838B OUT] ---- GPIO 15 (Pico W)
  [VS1838B VCC] ---- 3.3V (Pico W)
  [VS1838B GND] ---- GND (Pico W)

  [Status LED Anode] ---[220Ω]--- GPIO 12
  [Power ON LED Anode] ---[220Ω]--- GPIO 14
  [Power OFF LED Anode] ---[220Ω]--- GPIO 13
  [All LED Cathodes] ---- GND
```

## Files

- `main.py` — Main program, connects modules, handles IR and networking.
- `webinterface.py` — Web interface and logging.
- `config.py` — Configuration management (load, save, defaults).

## Example Configuration (`config.json`)

```json
{
  "VOLUME_TARGET": "GIRA",
  "MARANTZ_IP": "x.x.x.x",
  "MARANTZ_PORT": 23,
  "MARANTZ_COMMAND_VOL_UP": "MVUP\r",
  "MARANTZ_COMMAND_VOL_DOWN": "MVDOWN\r",
  "GIRA_IP": "x.x.x.x",
  "GIRA_PORT": 8001,
  "GIRA_COMMAND_VOL_UP": "pico:volUP",
  "GIRA_COMMAND_VOL_DOWN": "pico:volDOWN",
  "COMMAND_PWR_ON": "pico:power_on",
  "COMMAND_PWR_OFF": "pico:power_off",
  "NTP_TIME_STATUS": false,
  "NTP_SERVER_1": "pool.ntp.org",
  "NTP_SERVER_2": "time.google.com",
  "IR_CODE_VOL_UP": "0x10000080",
  "IR_CODE_VOL_DOWN": "0x48080480",
  "IR_CODE_MUTE": "0x50080500",
  "RESET_HOUR": 5,
  "MUTE_HOLD_TRIGGER": 3
}
```

## Hardware

- **Raspberry Pi Pico W** (requires wifi)
- **VS1838B 38 KHz IR receiver** connected to GPIO 15
- **Status/power LEDs** on GPIO 12, 13, 14 (optional)

## Installation

1. Copy the files (`main.py`, `webinterface.py`, `config.py`) to the Pico W.
2. Create `config.json` based on the example above.
3. Make sure your wifi settings are handled elsewhere in your code, or adapt `main.py` for your network.
4. Start the Pico W and open the web interface via its IP address in your browser.

## License

This project is open source, see LICENSE for details.

---
