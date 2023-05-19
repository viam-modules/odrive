# Odrive S1 Modular Component

## Getting Started
* See the [odrive documentation](https://docs.odriverobotics.com/v/latest/getting-started.html) on how to configure and tune your motor properly
* See the [odrive CAN documentation](https://docs.odriverobotics.com/v/latest/can-guide.html) for detailed information on how to set up CAN on your odrive. Make sure that you:
    * enable SPI communication on your Raspberry Pi
    * install `odrive`, `can-utils`, `python-can`, and `cantools`
* Update the sample config as following:
    * Update the `connection_type` (string) you will be using to communicate with your motor
      * if using a `"canbus"` connection, update the `canbus_node_id` (int) to the node ID of whichever CAN node you'd like to use
    * Update the `executable_path` (string) to the location of `run.sh` on your machine
* Provide the config on app.viam.com

## Optional Configs
The following optional config parameters are available for the Odrive:
1. `odrive_config_file`: path to a json file with your odrive configs (string)
    * Extract your configurations from your odrive. To do so you must have `odrivetool` installed. See the [Odrive instructions](https://docs.odriverobotics.com/v/latest/odrivetool.html) on how to do this.
    * After installing `odrivetool` run `odrivetool backup-config config.json` to extract your configs to a file called `config.json`. See [Odrive instructions](https://docs.odriverobotics.com/v/latest/odrivetool.html#configuration-backup) for more info.
    * `iq_msg_rate_ms` in the config defaults to `0`, but it needs to be approx `100` in order to use `set_power()` 
    * Provide the path to the config file as a string for this parameter.
    * See sample-configs/config.json for a sample odrive config file.
2. (Only with `"serial"` connection) `serial_number`: serial number of the odrive (string).
    * This is not necessary if you only have one odrive connected. See note in Troubleshooting section on multiple serial numbers. 
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
        "odrive_config_file": "local/path/to/motor/config.json"
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
        "odrive_config_file": "local/path/to/motor/config.json"
      },
      "depends_on": [],
      "type": "motor",
      "name": "odrive-motor"
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
