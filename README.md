# ODrive S1 Modular Component

This module provides an implementation of ODrive Robotics' [ODrive S1](https://odriverobotics.com/shop/odrive-s1) motor driver as a modular resource [extending](https://docs.viam.com/extend/modular-resources/) the Viam motor API.
Prepare your ODrive and configure the module and resource to integrate an `odrive-serial` or `odrive-canbus` [motor](https://docs.viam.com/components/motor/#API) into your robot. 


## Getting Started
* See the [ODrive documentation](https://docs.odriverobotics.com/v/latest/getting-started.html) to configure and tune your motor properly. 
This configuration remains on the same ODrive motor controller across reboots, and only changes when you go through the configuration of the ODrive again.
   * Note that `iq_msg_rate_ms` in the config defaults to 0, and you **must** set this to or around 100 to use the [motor API's `SetPower` method](https://docs.viam.com/components/motor/#setpower).
   * See the section *Add an odrive_config_file* for more information on dynamic configuration.
* See the [ODrive CAN documentation](https://docs.odriverobotics.com/v/latest/can-guide.html) for detailed information on how to set up CAN on your ODrive. 
Make sure that you have:
    * enabled SPI communication on your Raspberry Pi to use several common CANHats, other single board computers may have other ways of setting up CANBus communications.
    * installed `odrivetool`, `python-can`, `cantools`, and [Python `viam-sdk`](https://python.viam.dev)

### Connect your ODrive to your single-board computer
* `"odrive-serial"`: plug the [USB Isolator for ODrive](https://odriverobotics.com/shop/usb-c-to-usb-a-cable-and-usb-isolator) into a USB port on your board, and then plug a USB-C to USB-A cable from the isolator to the Odrive.
* `"odrive-canbus"`: wire the CANH and CANL pins from your board to your ODrive. Refer to the [ODrive pinout diagram](https://docs.odriverobotics.com/v/latest/pinout.html). 
    * When making the initial connection to set up the ODrive (see *Getting Started*), you have to make a `serial` connection. After setting up the ODrive, you can either leave the serial connection plugged in, or remove it and just leave the CANH and CANL pins wired.
    * [Raspberry Pi specific]: You must run `sudo ip link set can0 up type can bitrate <baud_rate>` in your terminal to receive CAN messages. See *Troubleshooting: CAN Link Issues* for more details.

## Configuration

To add an `odrive-canbus` or `odrive-serial` motor, update the JSON from the template with the following:

    * Update the `executable_path` (string) to the location of `run.sh` on your machine
    * (For `"canbus"` connection) update the `canbus_node_id` (int) to the node ID of whichever CAN node you'd like to use
    
Copy and paste this JSON configuration for your robot on [the Viam app](https://app.viam.com): 

### `viam:motor:odrive-serial`
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

### `viam:motor:odrive-canbus`
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

Edit and fill in the attributes as applicable.
The following attributes are available for the motor resources available in the Viam ODrive module:

| Name | Type | Inclusion | Description |
| ---- | ---- | --------- | ----------- |
| `canbus_node_id` | int | Optional | Required for successful initialization of the `"odrive-canbus"` type. <br> Node ID of the CAN node you would like to use. You configured this when [setting up your ODrive](https://docs.odriverobotics.com/v/latest/can-guide.html#setting-up-the-odrive). <br> Example: `0` |
| `odrive_config_file` | string | Optional | Filepath of a separate JSON file containing your ODrive's native configuration. </br> See the [Odrive S1 Modular Component repository](https://github.com/viamrobotics/odrive/tree/main/sample-configs) for an example of this file. |
| `serial_number` | string | Optional | The serial number of the ODrive. Note that this is not necessary if you only have one ODrive connected. See [Troubleshooting](#hanging) for help finding this value. |
| `canbus_baud_rate` | string | Optional | [Baud rate](https://docs.odriverobotics.com/v/latest/can-guide.html#setting-up-the-odrive) of the ODrive CAN protocol. This attribute is only available for `"odrive-canbus"` connections. </br> Use [`odrivetool`](https://docs.odriverobotics.com/v/latest/odrivetool.html) to obtain this value with `<odrv>.can.config.baud_rate`. Format the string as a multiple of 1000 (k). <br> Example: `"250k"` |

### Add an odrive_config_file

To add an `odrive_config_file` and reconfigure your ODrive natively each time the motor is initialized on the robot:

1. Extract your configurations from your ODrive. To do so you must [have `odrivetool` installed](https://docs.odriverobotics.com/v/latest/odrivetool.html).
2. After installing `odrivetool` run `odrivetool backup-config config.json` to extract your configs to a file called `config.json`. See the [ODrive documentation](https://docs.odriverobotics.com/v/latest/odrivetool.html#configuration-backup) for more info.
3. `iq_msg_rate_ms` in the config defaults to `0`. You must set this to or around `100` to use the [motor API's `SetPower` method](https://docs.viam.com/components/motor/#setpower).
4. If you add an `odrive_config_file` to an `odrive-canbus` motor, you will have to leave the serial connection established with your ODrive plugged in to the USB port, in addition to wiring the CANH and CANL pins.

An alternative to adding an `odrive_config_file` is running the command `odrivetool restore-config /path/to/config.json` in your terminal.

### Sample Viam CAN Config with 2 motors and odrive_config_files
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
* The motor is likely not properly tuned. 
See the [ODrive documentation](https://docs.odriverobotics.com/v/latest/control.html) for instructions on how to tune.

### Hanging
* If you have provided a serial number, make sure it is the correct serial number. ODrives have **2 serial numbers**: one that will be printed out when you start `odrivetool`, and one that can be accessed in `odrivetool` by running `odrv0.serial_number`. The **correct** serial number is the one that is printed out when you start `odrivetool`.
* If you have not provided a serial number or you are sure you have provided the correct serial number, you are likely connected to the ODrive elsewhere. Make sure any connections via Python, `odrivetool` or the GUI are closed.

### CAN Link Issues
* If you get an error of `"Device or resource busy"`, try setting CAN down and back up with the command `sudo ip link set can0 down` followed by `sudo ip link set can0 up type can bitrate <baud_rate>`
    * You will have to do this any time you want to change the baud rate
* If you get an error of `"Network is down"`, try setting CAN up with the command `sudo ip link set can0 up type can bitrate <baud_rate>`

## License
Copyright 2021-2023 Viam Inc.

Apache 2.0 - See [LICENSE](https://github.com/viamrobotics/odrive/blob/main/LICENSE) file
