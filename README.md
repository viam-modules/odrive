# Odrive S1 Modular Component

## Getting Started
* See the [odrive documentation](https://docs.odriverobotics.com/v/latest/getting-started.html) on how to configure and tune your motor properly. The configuration remains on the same ODrive motor controller across reboots, and only changes when you go through the configuration of the ODrive again.
* See the [odrive CAN documentation](https://docs.odriverobotics.com/v/latest/can-guide.html) for detailed information on how to set up CAN on your odrive. Make sure that you:
    * enable SPI communication on your Raspberry Pi
    * install `odrive`, `python-can`, and `cantools`
* Update the sample config as following:
    * Update the `executable_path` (string) to the location of `run.sh` on your machine
    * If using a `"canbus"` connection, update the `canbus_node_id` (int) to the node ID of whichever CAN node you'd like to use
* Provide the config on app.viam.com
* (For `"canbus"` models) You must run `sudo ip link set can0 up type can bitrate <baud_rate>` in your terminal in order to receive CAN messages. See *CAN Link Issues* in the *Troubleshooting* section for more details.

## Connecting to an Odrive
* `"serial"`: plug the [USB Isolator for Odrive](https://odriverobotics.com/shop/usb-c-to-usb-a-cable-and-usb-isolator) into a USB port on your board, and then plug a USB-C to USB-A cable from the isolator to the Odrive.
* `"canbus"`: wire the CANH and CANL (see [Odrive pinout](https://docs.odriverobotics.com/v/latest/pinout.html)) pins from your board to your Odrive
    * In order to configure the Odrive (see the first item in the *Getting Started* secion), you will also need to plug the Odrive into your board through a USB port with the [USB Isolator for Odrive](https://odriverobotics.com/shop/usb-c-to-usb-a-cable-and-usb-isolator). Once you have configured the Odrive, you can either leave the serial connection plugged in, or remove it and just leave the CANH and CANL pins wired.

## Optional Configs
The following optional config parameters are available for the Odrive:
1. `odrive_config_file`: path to a json file with your odrive configs (string)
    * You can add this config parameter if you'd like to reconfigure your Odrive each time it is initialized, but if you have configured your Odrive to your liking already, it's not necessary.
    * Extract your configurations from your odrive. To do so you must have `odrivetool` installed. See the [Odrive instructions](https://docs.odriverobotics.com/v/latest/odrivetool.html) on how to do this.
    * After installing `odrivetool` run `odrivetool backup-config config.json` to extract your configs to a file called `config.json`. See [Odrive instructions](https://docs.odriverobotics.com/v/latest/odrivetool.html#configuration-backup) for more info.
    * `iq_msg_rate_ms` in the config defaults to `0`, but it needs to be approximately `100` in order to use `set_power()` 
    * Provide the path to the config file as a string for this parameter.
    * See sample-configs/config.json for a sample odrive config file.
    * (For `"canbus"` connection) If you add an `odrive_config_file`, you will have to leave the Odrive plugged in to the USB port in addition to wiring the CANH and CANL pins.
    * An alternative to adding an `odrive_config_file` is running the command `odrivetool restore-config /path/to/config.json` in your terminal.
2. `serial_number`: serial number of the odrive (string).
    * This is not necessary if you only have one odrive connected. See *Troubleshooting* section *Hanging* for a note on multiple serial numbers. 
    * (For `"canbus"` connection) This is not necessary unless you have multiple Odrives connected AND are providing an `odrive_config_file` for any of them. The `"canbus"` implementation allows you to connect multiple Odrives without providing a `serial_number` as long as you don't have any `odrive_config_file`.
3. (Only with `"canbus"` connection) `canbus_baud_rate`: baud rate of the odrive CAN protocol (string).
    * This parameter can be found using `odrivetool` with `<odrv>.can.config.baud_rate`
    * Format the string as a multiple of 1000 (ex: `"250k"`)


## Sample Viam Serial Config
```json
{
  "modules": [
    {
      "name": "odrive",
      "executable_path": "path/to/run.sh"
    }
  ],
  "components": [
    {
      "model": "viam:motor:odrive-serial",
      "namespace": "rdk",
      "attributes": {
        "serial_number": "NUM000",
        "odrive_config_file": "local/path/to/motor/config.json",
      },
      "depends_on": [],
      "type": "motor",
      "name": "odrive-motor"
    }
  ]
}
```

## Sample Viam CAN Config
```json
{
  "modules": [
    {
      "name": "odrive",
      "executable_path": "path/to/run.sh"
    }
  ],
  "components": [
    {
      "model": "viam:motor:odrive-canbus",
      "namespace": "rdk",
      "attributes": {
        "canbus_node_id": 0,
      },
      "depends_on": [],
      "type": "motor",
      "name": "odrive-motor"
    }
  ]
}
```

## Sample Viam CAN Config with 2 Odrives and odrive_config_files
```json
{
  "modules": [
    {
      "name": "odrive",
      "executable_path": "path/to/run.sh"
    }
  ],
  "components": [
    {
      "model": "viam:motor:odrive-canbus",
      "namespace": "rdk",
      "attributes": {
        "canbus_node_id": 0,
        "odrive_config_file": "/path/to/first/config.json",
        "serial_number": "NUM0001"
      },
      "depends_on": [],
      "type": "motor",
      "name": "odrive-motor"
    },
    {
      "model": "viam:motor:odrive-canbus",
      "namespace": "rdk",
      "attributes": {
        "canbus_node_id": 2,
        "odrive_config_file": "/path/to/second/config.json",
        "serial_number": "NUM0002"
      },
      "depends_on": [],
      "type": "motor",
      "name": "odrive-motor-2"
    }
  ]
}
```

## Troubleshooting

### Unstable Behavior
* The motor is likely not properly tuned see the [odrive documentation](https://docs.odriverobotics.com/v/latest/control.html) for instructions on how to tune.

### Hanging
* If you have provided a serial number, make sure it is the correct serial number. Odrives have **2 serial numbers**: one that will be printed out when you start `odrivetool`, and one that can be accessed in `odrivetool` by running `odrv0.serial_number`. The **correct** serial number is the one that is printed out when you start `odrivetool`.
* If you have not provided a serial number or you are sure you have provided the correct serial number, you are likely connected to the odrive elsewhere. Make sure any connections via python, `odrivetool` or the GUI are closed.

### CAN Link Issues
* If you get an error of `"Device or resource busy"`, try setting CAN down and back up with the command `sudo ip link set can0 down` followed by `sudo ip link set can0 up type can bitrate <baud_rate>`
    * You will have to do this any time you want to change the baud rate
* If you get an error of `"Network is down"`, try setting CAN up with the command `sudo ip link set can0 up type can bitrate <baud_rate>`

## License
Copyright 2021-2023 Viam Inc.

Apache 2.0 - See [LICENSE](https://github.com/viamrobotics/odrive/blob/main/LICENSE) file
