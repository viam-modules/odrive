# Odrive S1 Modular Component

## Getting Started
* See the [odrive documentation](https://docs.odriverobotics.com/v/latest/getting-started.html) on how to configure and tune your motor properly
* Update the sample config as following:
 * Update the `max_rpm` (int) of your motor
 * Update the `executable_path` (string) to the location of `run.sh` on your machine
* Provide the config on app.viam.com

## Optional Configs
There are two additional, optional configs:
1. `odrive_config_file`: path to a json file with your odrive configs (string)
  * Extract your configurations from your odrive. To do so you must have `odrivetool` installed. See the [Odrive instructions](https://docs.odriverobotics.com/v/latest/odrivetool.html) on how to do this.
  * After installing `odrivetool` run `odrivetool backup-config config.json` to extract your configs to a file called `config.json`. See [Odrive instructions](https://docs.odriverobotics.com/v/latest/odrivetool.html#configuration-backup) for more info.
  * Provide the path to the config file as a string for this parameter.
  * See sample-configs/config.json for a sample odrive config file.
2. `serial_number`: serial number of the odrive (string).
  * This is not necessary if you only have one odrive connected. See note in Troubleshooting section on multiple serial numbers. 


## Sample Viam Config
```json
{
  "modules": [
    {
      "name": "odriveS1",
      "executable_path": "path/to/run.sh"
    }
  ],
  "components": [
    {
      "model": "viam-labs:motor:odriveS1",
      "namespace": "rdk",
      "attributes": {
        "max_rpm": 600
      },
      "depends_on": [],
      "type": "motor",
      "name": "odriveS1"
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
