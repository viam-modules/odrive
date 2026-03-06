from typing import ClassVar, Mapping, Any, Dict, Optional, Sequence, Tuple, List

from typing_extensions import Self

from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName, Geometry
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.utils import ValueTypes

from viam.components.motor import Motor

import odrive
from odrive.enums import *
from threading import Thread, Event
from concurrent.futures import ThreadPoolExecutor
import asyncio
import time
import math
from utils import set_configs, rsetattr

MINUTE_TO_SECOND = 60


# TODO: automatically reconnect
# TODO: needs concurrency control for rapidly issued api calls
class OdriveSerial(Motor, EasyResource):
    MODEL: ClassVar[Model] = Model(ModelFamily("viam", "odrive"), "serial")
    serial_number: str
    odrive_config_file: str
    current_lim: float
    odrv: Any
    watchdog_timeout: float
    vel_limit: float
    _stop_event: Any

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        odriveSerial = cls(config.name)
        odriveSerial.serial_number = config.attributes.fields["serial_number"].string_value
        odriveSerial.odrive_config_file = config.attributes.fields["odrive_config_file"].string_value

        # TODO: there must be a better way to do this. asyncio.run is called within the odrive sdk which is not allowed as we are already in an event loop here.
        with ThreadPoolExecutor(max_workers=1) as executor:
            if odriveSerial.serial_number == "":
                odriveSerial.logger.warning("If you are using multiple Odrive controllers, make sure to add their respective serial_number to each component attributes")
                odriveSerial.odrv = executor.submit(odrive.find_any).result()
            else:
                odriveSerial.odrv = executor.submit(odrive.find_any, serial_number=odriveSerial.serial_number).result()
        odriveSerial.odrv.clear_errors()
        
        if odriveSerial.odrive_config_file != "":
            set_configs(odriveSerial.odrv, odriveSerial.odrive_config_file)

        if "overrides" in config.attributes.fields:
            overrides = {k: v.number_value if v.WhichOneof("kind") == "number_value"
                           else v.bool_value if v.WhichOneof("kind") == "bool_value"
                           else v.string_value
                         for k, v in config.attributes.fields["overrides"].struct_value.fields.items()}
            odriveSerial._apply_overrides(overrides)
        
        odriveSerial.current_lim = odriveSerial.odrv.axis0.config.general_lockin.current
        odriveSerial.watchdog_timeout = odriveSerial.odrv.axis0.config.watchdog_timeout
        odriveSerial.vel_limit = odriveSerial.odrv.axis0.controller.config.vel_limit

        odriveSerial._stop_event = Event()
        Thread(target=odriveSerial._periodically_surface_errors, daemon=True).start()

        if odriveSerial.odrv.axis0.config.enable_watchdog:
            odriveSerial.logger.info("Starting watchdog feed thread for axis0, as it is enabled.")
            Thread(target=odriveSerial._periodically_feed_watchdog, daemon=True).start()

        return odriveSerial

    _SPECIAL_FLOATS = {"Infinity": float("inf"), "-Infinity": float("-inf"), "NaN": float("nan")}

    def _apply_overrides(self, overrides: Dict[str, Any]) -> None:
        for key, value in overrides.items():
            if isinstance(value, bool):
                rsetattr(self.odrv, key, value)
            elif isinstance(value, (int, float)):
                rsetattr(self.odrv, key, value)
            elif isinstance(value, str) and value in self._SPECIAL_FLOATS:
                rsetattr(self.odrv, key, self._SPECIAL_FLOATS[value])
            else:
                self.logger.warning(f"Override '{key}' has unsupported value '{value}', skipping")

    def _periodically_surface_errors(self):
        while not self._stop_event.is_set():
            asyncio.run(self.surface_errors())
            self._stop_event.wait(1)

    def _periodically_feed_watchdog(self):
        interval = self.watchdog_timeout / 4
        while not self._stop_event.is_set():
            self.odrv.axis0.watchdog_feed()
            self._stop_event.wait(interval)
        self.logger.debug("Watchdog thread stopped.")


    async def close(self):
        self._stop_event.set()

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> Tuple[Sequence[str], Sequence[str]]:
        return [], []

    # set_power is defined as a percentage of maximum configured velocity
    async def set_power(self, power: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        if not self.odrv.axis0.controller.config.enable_vel_limit:
            raise Exception("set_power requires enable_vel_limit to be True")

        if abs(power) < 0.0001:
            self.logger.debug(f"Power is nearly 0, stopping.")
            await self.stop()
            return

        vel = power * self.vel_limit
        self.odrv.axis0.controller.config.input_mode = InputMode.PASSTHROUGH
        self.odrv.axis0.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
        if self.odrv.axis0.current_state != AxisState.CLOSED_LOOP_CONTROL:
            self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
            await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
        self.odrv.axis0.controller.input_vel = vel


    async def go_for(self, rpm: float, revolutions: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        if abs(rpm) < 0.001:
            self.logger.warn("Requested RPM is nearly 0, stopping.")
            await self.stop()
            return

        rps = rpm / MINUTE_TO_SECOND
        await self.configure_trap_trajectory(abs(rpm))
        current_position = await self.get_position()
        # the line below causes motion.
        self.odrv.axis0.controller.input_pos = current_position + math.copysign(revolutions, rpm)
        await self.wait_and_set_to_idle(rps, revolutions)

    async def go_to(self, rpm: float, position_revolutions: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        current_position = await self.get_position()
        revolutions = position_revolutions - current_position
        await self.go_for(rpm, revolutions)

    async def set_rpm(self, rpm: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        # TODO these should return an error, not just log in
        if abs(rpm) < 0.001:
            self.logger.debug("Cannot move motor at an RPM that is nearly 0, stopping.")
            await self.stop()
            return

        rps = rpm / MINUTE_TO_SECOND
        self.odrv.axis0.controller.config.input_mode = InputMode.PASSTHROUGH
        self.odrv.axis0.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
        if self.odrv.axis0.current_state != AxisState.CLOSED_LOOP_CONTROL:
            self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
            await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
        self.odrv.axis0.controller.input_vel = rps

    async def reset_zero_position(self, offset: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        if await self.is_powered():
            raise Exception("Cannot reset zero position while motor is powered. Motor must be stopped.")

        self.odrv.axis0.pos_estimate = float

    async def get_position(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        return self.odrv.axis0.pos_estimate

    async def get_properties(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> Motor.Properties:
        return Motor.Properties(position_reporting=True)

    async def stop(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        self.odrv.axis0.requested_state = AxisState.IDLE

    async def is_powered(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> Tuple[bool, float]:
        return (self.odrv.axis0.current_state != AxisState.IDLE and self.odrv.axis0.current_state != AxisState.UNDEFINED, self.odrv.axis0.motor.foc.Iq_setpoint/self.current_lim)

    async def is_moving(self):
        return self.odrv.axis0.current_state != AxisState.IDLE

    async def get_geometries(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> List[Geometry]:
        return []


    async def do_command(self, command: Mapping[str, ValueTypes], *, timeout: Optional[float] = None, **kwargs) -> Mapping[str, ValueTypes]:
        # "run" expects an array of objects (for ordering) where each object is a key/value pair to set on the motor.
        if "run" in command:
            # these must be sent in order
            for item in command["run"]:
                self._apply_overrides(item)
        return {}

    async def configure_trap_trajectory(self, rpm) -> None:
        rps = rpm / MINUTE_TO_SECOND
        
        # TODO: vel_limit should be reset to the previous value afterward?
        self.odrv.axis0.trap_traj.config.vel_limit = rps
        self.odrv.axis0.controller.config.input_mode = InputMode.TRAP_TRAJ
        self.odrv.axis0.controller.config.control_mode = ControlMode.POSITION_CONTROL
        if self.odrv.axis0.current_state != AxisState.CLOSED_LOOP_CONTROL:
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
            await self.stop()
        else:
            self.logger.warning(f"voltage ({self.odrv.vbus_voltage}) above expected value (.15) after waiting revolutions / rps * 1.05 = {time_sleep} seconds. Remaining in CLOSED_LOOP_CONTROL mode")
        
    async def surface_errors(self):
        errorCode = self.odrv.axis0.active_errors
        disarmReason = self.odrv.axis0.disarm_reason
        
        if errorCode != 0:
            await self.stop()
            self.logger.error(ODriveError(errorCode).name)

        if disarmReason != 0:
            await self.stop()
            self.logger.error(ODriveError(disarmReason).name)
        
        if errorCode != 0 or disarmReason != 0:
            self.odrv.clear_errors()
