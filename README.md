# Grass <!-- omit in toc -->

[![Donations: Coffee](https://img.shields.io/badge/donations-Coffee-brown?style=flat-square)](https://github.com/Chrismettal#donations)

This is a python-based controller for a growbox using [PiPLC](https://github.com/Chrismettal/PiPLC) hardware.It's meant to be run on a Raspberry Pi mounted to your growbox.
Most sensors are wired using `I²C` so you don't end up running 50 wires through the box.

It features:

- Lighting schedule
    - Light dimming
- Exhaust fan (Temp / Humidity based)
    - Exhaust speed control
- Circulation fan schedule
    - Circulation fan speed control
- Heating
- Watering (Soil humidity / schedule based)
    - Water resorvoir level measurement
    - Water resorvoir temperature measurement
- Air Temperature / Humidity measurement
- Soil Temperatur / Humidity measurement for 3 buckets (I'm not using these anymore as they were measuring crap)

**If you like my work please consider [supporting me](https://github.com/Chrismettal#donations)!**

## Table of contents <!-- omit in toc -->

- [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [Pypi installation](#pypi-installation)
    - [Manual installation (for development)](#manual-installation-for-development)
- [Usage](#usage)
- [GPIO mapping](#gpio-mapping)
- [Roadmap](#roadmap)
- [Camera](#camera)
- [Donations](#donations)
- [License](#license)

## Installation

### Prerequisites

- Either create a Python venv or be prepared to `--break-system-packages`

- Install [Adafruit Blinka](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi) for our sensor dependencies

- As of 2024-04, you'll need to remove the default `RPi.GPIO` library via `sudo apt remove python3-rpi.gpio` before installing a forked version with `pip install rpi-lgpio` (potentially with `--break-system-packages`) since GPIO interrupts won't work in the base library version

### Pypi installation

Might be pushed to Pypi later idk.

### Manual installation (for development)

- Clone the repo:

`git clone https://github.com/chrismettal/grass`

- Change directory into said cloned repo:

`cd grass`

- Install in "editable" mode:

`pip install -e .`

- Open up `./grass/grass.py` and modify the global parameters at the top to fit your needs.

- Execute `grass` to run the software. Potentially configure your OS to autorun at boot.

- To run `Grass` at boot, create `/etc/systemd/system/grass.service` with the following content, making sure to update your repo folder location and user/group:

```
[Unit]
After=network.target

[Service]
WorkingDirectory=<repo>/grass
Type=simple
ExecStart=/usr/bin/python <repo>/grass/grass.py
User=<YourUser>
Group=<YourGroup>

[Install]
WantedBy=default.target
```

- Enable this service to run `Grass` at boot with `sudo systemctl enable --now grass.service`

## Usage

The current state of the project reflects somewhat of a minimum viable product that fits specifically my environment while I get familiar with growing itself. Once I obtain enough knowledge about plants, I want to update this project into a more fully fledged solution.

Make sure you have changed the global parameters at the top of `./grass/grass.py` to fit your MQTT server etc.

On startup, `Grass` will want to connect to that MQTT server, and try to instance all sensors. Sensors that aren't found during Init, won't be reconnected at runtime at the moment so you'll need to restart `Grass` if a sensor is only connected during runtime.

Periodically, `Grass` will poll all of your sensors and upload their state to MQTT. Heating / Lighting etc. is executed locally without remote control through MQTT required.

Exhaust is currently only executed through MQTT and not by any local logic.

## GPIO mapping

This code is intended to be run on a [PiPLC](https://github.com/chrismettal/piplc) running regular `PiOS` but theoretically it's possible to be run on a bare Pi with some I/O attached.

| GPIO Name | PiPLC function           | grass                                             |
| :-------: | :----------------------- | :------------------------------------------------ |
| `GPIO_02` | :blue_square: I²C SDA    | `BH1750` light / `AHT20` temp/hum / Soil moisture |
| `GPIO_03` | :blue_square: I²C SCL    | `BH1750` light / `AHT20` temp/hum / Soil moisture |
| `GPIO_04` | :blue_square: Modbus TX  | :x:                                               |
| `GPIO_05` | :blue_square: Modbus RX  | :x:                                               |
| `GPIO_06` | :blue_square: Modbus RTS | :x:                                               |
| `GPIO_07` | :red_square: Q4          | *230 V spare*                                     |
| `GPIO_08` | :red_square: Q3          | 230 V Exhaust                                     |
| `GPIO_09` | :yellow_square: I5       | -                                                 |
| `GPIO_10` | :yellow_square: I4       | -                                                 |
| `GPIO_11` | :yellow_square: I6       | -                                                 |
| `GPIO_12` | :red_square: Q5          | 24 V Water Pump                                   |
| `GPIO_13` | :yellow_square: I7       | -                                                 |
| `GPIO_14` | :blue_square: KNX TX     | :x:                                               |
| `GPIO_15` | :blue_square: KNX RX     | :x:                                               |
| `GPIO_16` | :red_square: Q6          | 24 V Circulation fan  (2 x 12v fans in series)    |
| `GPIO_17` | :yellow_square: I1       | S0 energy meter                                   |
| `GPIO_18` | :orange_square: PWM_0    | -                                                 |
| `GPIO_19` | :orange_square: PWM_1    | -                                                 |
| `GPIO_20` | :red_square: Q7          | *24 V spare*                                      |
| `GPIO_21` | :red_square: Q8          | *24 V spare*                                      |
| `GPIO_22` | :yellow_square: I3       | -                                                 |
| `GPIO_23` | :blue_square: 1-Wire     | `DS18B20` Soil / Water temp                       |
| `GPIO_24` | :red_square: Q1          | 230 V Light                                       |
| `GPIO_25` | :red_square: Q2          | 230 V Heater                                      |
| `GPIO_26` | :yellow_square: I8       | -                                                 |
| `GPIO_27` | :yellow_square: I2       | -                                                 |

![Schematic](/doc/PiPLC_Testboard.drawio.svg)

## Roadmap

In no particular order

- [x] GPIO working manually
- [x] Timelapse feature works (Via `motion`)
    - [x] Camera still accessible as webcam stream 
- [x] All print statements become log statements
- [ ] Parameter handling
    - [ ] Control parameters and secrets saved in config struct/file
    - [ ] Control parameters updated persistently through MQTT
    - [ ] Current Control parameters uploaded to MQTT at connection time
- [ ] Sensors
    - [x] Power meter works
    - [x] Air temperature / humidity can be read
    - [x] Soil moisture / temperature can be read
    - [x] Water tank temperature can be read
    - [x] Telemetry sensors (CPU Temp, free space on disk..)
    - [ ] Water tank fill level can be read
    - [ ] Sensors that aren't present at machine start get detected without restart
- [ ] Actuators / Logic
    - [x] Light schedule works
    - [x] Heater logic works
    - [x] Circulation logic works
    - [x] Exhaust logic works
    - [ ] Watering logic works
    - [x] All actuators log execution into MQTT
- [ ] HomeAssistant
    - [x] Invalidate sensor states on disconnect (Done in )
    - [ ] Potential integration or at least shared dashboard configuration
    - [ ] Cyclic sending of sensor states in addition to on change
    - [ ] Override outputs
    - [ ] MQTT advertising
- [ ] Documentation
    - [ ] Sensors used
    - [ ] Parameters
    - [ ] Autostart on machine boot

## Camera

The Camera is not handled in `Grass`'s code, but I used `motion` as a simple way to stream the camera footage to my Homeassistant instance as well as run local timelapses

- `sudo apt install motion`
- Change config file to enable timelapse snapshots
- `Change /lib/systemd/system/motion.service` to start in non-daemon mode 
    - `ExecStart=/usr/bin/motion -n`
- `sudo systemctl enable --now motion`

## Donations

**If you like my work please consider [supporting me](https://github.com/Chrismettal#donations)!**

## License

 <a rel="GPLlicense" href="https://www.gnu.org/licenses/gpl-3.0.html"><img alt="GPLv3" style="border-width:0" src="https://www.gnu.org/graphics/gplv3-or-later.png" /></a><br />This work is licensed under a <a rel="GPLlicense" href="https://www.gnu.org/licenses/gpl-3.0.html">GNU GPLv3 License</a>.
