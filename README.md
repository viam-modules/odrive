# ODrive Modular Component

This module implements the motor driver for ODrive Robotics' [ODrive S1](https://odriverobotics.com/shop/odrive-s1) and [ODrive Pro](https://odriverobotics.com/shop/odrive-pro) motors to be used with [`viam-server`](https://docs.viam.com/get-started/installation/). It only supports serial connectivity. ODrive clones, such as ODESC, may work as well but are not tested.

## Getting Started

The motor must first be wired, configured, and calibrated following [Odrive instructions](https://docs.odriverobotics.com/v/latest/guides/getting-started.html).

Before configuring your board, you must [create a machine](https://docs.viam.com/cloud/machines/#add-a-new-machine).

Navigate to the [**CONFIGURE** tab](https://docs.viam.com/configure/) of your [machine](https://docs.viam.com/fleet/machines/) in the [Viam app](https://app.viam.com/).

## Model viam:odrive:serial  

### Attributes

The following attributes are available for the motor resources available in the Viam ODrive module:

| Name | Type | Inclusion | Description |
| ---- | ---- | --------- | ----------- |
| `serial_number` | string | Optional | The serial number of the ODrive. Can be found using the `odrivetool`. Will be auto-discovered if not provided. Required if multiple motors are connected. |
| `odrive_config_file` | string | Optional | Filepath of a separate JSON file containing your ODrive's  configuration. Overrides settings stored in memory. Typically exported using the `odrivetool backup-config` command. |
| `overrides` | object | Optional | Additional configuration overrides in key/value format. See example below.

Example:
```json
{
  "serial_number": "NUM000",
  "odrive_config_file": "local/path/to/motor/config.json",
  "overrides": {
    "axis0.controller.config.vel_limit": 1,
    "axis0.config.watchdog_timeout": 2,
    "axis0.config.enable_watchdog": true
  }
}
```

**Note**  
There are three levels of motor configuration:
1. Configuration stored in the ODrive controller's memory, set by the `odrivetool`.
2. Optionally, you can define an `odrive_config_file` to override the memory settings (useful if you prefer to manage settings yourself or share settings across motors).
3. Finally, you can use the `overrides` configuration to fine-tune individual settings (especially useful for testing and manual calibration).

**Important**  
You must define `axis0.controller.config.vel_limit` (velocity limit, in rotations per second) in your motor configuration to use the `SetPower` command. The `SetPower` command uses velocity control to set a target velocity as a percentage of the configured `axis0.controller.config.vel_limit` value.

## Next Steps

- To test your ODrive motor, go to the [**Control** tab](https://docs.viam.com/fleet/machines/#control).
- To write code against your ODrive motor, use one of the [available SDKs](https://docs.viam.com/build/program/).
- To view examples using a motor component, explore [these tutorials](https://docs.viam.com/tutorials/).

## License
Copyright 2021-2023 Viam Inc.

Apache 2.0 - See [LICENSE](https://github.com/viamrobotics/odrive/blob/main/LICENSE) file
