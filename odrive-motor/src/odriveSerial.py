from typing import ClassVar, Mapping, Any, Dict, Optional, Tuple

from typing_extensions import Self

from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import Model, ModelFamily

from viam.components.motor import Motor
from viam.logging import getLogger

import odrive
from odrive.enums import *
from threading import Thread
import asyncio
import time
from .utils import set_configs

LOGGER = getLogger(__name__)
MINUTE_TO_SECOND = 60

class OdriveSerial(Motor, Reconfigurable):
    MODEL: ClassVar[Model] = Model(ModelFamily("viam", "motor"), "odrive-serial")
    serial_number: str
    odrive_config_file: str
    torque_constant: float
    current_lim: float
    offset: float
    odrv: Any

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        odriveSerial = cls(config.name)
        odriveSerial.serial_number = config.attributes.fields["serial_number"].string_value
        odriveSerial.odrive_config_file = config.attributes.fields["odrive_config_file"].string_value
        odriveSerial.offset = 0

        odriveSerial.odrv = odrive.find_any() if odriveSerial.serial_number == "" else odrive.find_any(serial_number = odriveSerial.serial_number)
        odriveSerial.odrv.clear_errors()
        
        if odriveSerial.odrive_config_file != "":
            set_configs(odriveSerial.odrv, odriveSerial.odrive_config_file)
        
        odriveSerial.torque_constant = odriveSerial.odrv.axis0.config.motor.torque_constant
        odriveSerial.current_lim = odriveSerial.odrv.axis0.config.general_lockin.current

        def periodically_surface_errors(odrv):
            while True:
                asyncio.run(odrv.surface_errors())
                time.sleep(1)

        thread = Thread(target = periodically_surface_errors, args=[odriveSerial])
        thread.setDaemon(True) 
        thread.start()

        return odriveSerial

    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        self.serial_number = config.attributes.fields["serial_number"].string_value
        
        config_file = config.attributes.fields["odrive_config_file"].string_value
        if (config_file != self.odrive_config_file) and config_file != "":
            LOGGER.info("Updating odrive configurations.")
            self.odrive_config_file = config_file
            set_configs(self.odrv, self.odrive_config_file)
            self.torque_constant = self.odrv.axis0.config.motor.torque_constant
            self.current_lim = self.odrv.axis0.config.general_lockin.current

    async def set_power(self, power: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        torque = power * self.current_lim * self.torque_constant
        self.odrv.axis0.controller.config.input_mode = InputMode.PASSTHROUGH
        self.odrv.axis0.controller.config.control_mode = ControlMode.TORQUE_CONTROL
        self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
        await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
        # the line below causes motion.
        self.odrv.axis0.controller.input_torque = torque

    async def go_for(self, rpm: float, revolutions: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        rps = rpm / MINUTE_TO_SECOND
        if revolutions == 0:
            self.odrv.axis0.controller.config.input_mode = InputMode.PASSTHROUGH
            self.odrv.axis0.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
            self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
            await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
            self.odrv.axis0.controller.input_vel = rps
        else:
            await self.configure_trap_trajectory(abs(rpm))
            current_position = await self.get_position()
            if rpm > 0:
                # the line below causes motion.
                self.odrv.axis0.controller.input_pos = current_position + revolutions + self.offset
            else:
                # the line below causes motion.
                self.odrv.axis0.controller.input_pos = current_position - revolutions + self.offset
        await self.wait_and_set_to_idle(rps, revolutions)

    async def go_to(self, rpm: float, revolutions: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        current_position = await self.get_position()
        revolutions = revolutions - current_position
        await self.go_for(rpm, revolutions)

    async def reset_zero_position(self, offset: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        position = await self.get_position()
        self.offset += position

    async def get_position(self, extra: Optional[Dict[str, Any]] = None, **kwargs):
        return self.odrv.axis0.pos_vel_mapper.pos_rel - self.offset

    async def get_properties(self, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> Motor.Properties:
        return Motor.Properties(position_reporting=True)

    async def stop(self, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.odrv.axis0.requested_state = AxisState.IDLE

    async def is_powered(self, extra: Optional[Dict[str, Any]] = None, **kwargs) -> Tuple[bool, float]:
        return (self.odrv.axis0.current_state != AxisState.IDLE and self.odrv.axis0.current_state != AxisState.UNDEFINED, self.odrv.axis0.motor.foc.Iq_setpoint/self.current_lim)

    async def is_moving(self):
        return self.odrv.axis0.current_state != AxisState.IDLE
    
    async def configure_trap_trajectory(self, rpm) -> None:
        rps = rpm / MINUTE_TO_SECOND
        self.odrv.axis0.trap_traj.config.vel_limit = rps
        self.odrv.axis0.controller.config.input_mode = InputMode.TRAP_TRAJ
        self.odrv.axis0.controller.config.control_mode = ControlMode.POSITION_CONTROL
        self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
        await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
    
    async def wait_until_correct_state(self, state):
        while self.odrv.axis0.current_state != state:
            await self.surface_errors()
            continue

    # Function to wait 1.05% of time we expect go for to take, and set the motor to IDLE
    async def wait_and_set_to_idle(self, rps, revolutions):
        time_sleep = abs(revolutions / rps) * 1.05
        await asyncio.sleep(time_sleep)
        if self.odrv.vbus_voltage < .15:
            self.stop()
        else:
            LOGGER.warn(f"voltage ({self.odrv.vbus_voltage}) above expected value (.15) after waiting revolutions / rps * 1.05 = {time_sleep} seconds. Remaining in CLOSED_LOOP_CONTROL mode")
        
    async def surface_errors(self):
        errorCode = self.odrv.axis0.active_errors
        disarmReason = self.odrv.axis0.disarm_reason
        
        if  errorCode != 0:
            await self.stop()
            LOGGER.error(ODriveError(errorCode).name)
        
        if  disarmReason != 0:
            await self.stop()
            LOGGER.error(ODriveError(disarmReason).name)
        
        if errorCode != 0 or disarmReason != 0:
            self.odrv.clear_errors()
