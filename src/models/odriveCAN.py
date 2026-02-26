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
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import asyncio
import time
import math
from pathlib import Path

from utils import set_configs, find_baudrate, rsetattr, find_axis_configs

import can
import cantools

MINUTE_TO_SECOND = 60.0

class OdriveCAN(Motor, EasyResource):
    MODEL: ClassVar[Model] = Model(ModelFamily("viam", "odrive"), "canbus")
    odrive_config_file: str
    offset: float
    baud_rate: str
    odrv: Any
    nodeID: int
    torque_constant: float
    current_limit: float
    goal: dict()
    serial_number: str
    db: Any
    bus: Any

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        odriveCAN = cls(config.name)
        odriveCAN.bus = can.Bus("can0", bustype="socketcan")
        odriveCAN.odrive_config_file = config.attributes.fields["odrive_config_file"].string_value
        if ("canbus_node_id" not in config.attributes.fields) or (config.attributes.fields["canbus_node_id"].number_value < 0):
            odriveCAN.logger.error("non negative 'canbus_node_id' is a required config attribute")
        odriveCAN.nodeID = int(config.attributes.fields["canbus_node_id"].number_value)
        odriveCAN.serial_number = config.attributes.fields["serial_number"].string_value
        odriveCAN.torque_constant = 1
        odriveCAN.current_limit = 10
        odriveCAN.offset = 0.0
        odriveCAN.goal = {"position": 0.0, "active": False}

        path = str(Path(__file__).parent.parent / "odrive-cansimple.dbc")
        odriveCAN.db = cantools.database.load_file(path)

        if odriveCAN.odrive_config_file != "":
            if odriveCAN.serial_number == "":
                odriveCAN.logger.info("If you are using multiple Odrive controllers, make sure to add their respective serial_number to each component attributes")
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    if odriveCAN.serial_number == "":
                        odriveCAN.odrv = executor.submit(odrive.find_any).result()
                    else:
                        odriveCAN.odrv = executor.submit(odrive.find_any, serial_number=odriveCAN.serial_number).result()
                odriveCAN.odrv.clear_errors()
                if odriveCAN.odrive_config_file != "":
                    set_configs(odriveCAN.odrv, odriveCAN.odrive_config_file)
                    rsetattr(odriveCAN.odrv, "axis0.config.can.node_id", odriveCAN.nodeID)
                    odriveCAN.torque_constant = find_axis_configs(odriveCAN.odrive_config_file, ["motor", "torque_constant"])
                    odriveCAN.current_limit = find_axis_configs(odriveCAN.odrive_config_file, ["general_lockin", "current"])
            except:
                odriveCAN.logger.error("Could not set odrive configurations because no serial odrive connection was found.")
                pass

        if config.attributes.fields["canbus_baud_rate"].string_value != "":
            baud_rate = config.attributes.fields["canbus_baud_rate"].string_value
            baud_rate = baud_rate.replace("k", "000")
            baud_rate = baud_rate.replace("K", "000")
            odriveCAN.baud_rate = baud_rate
        elif odriveCAN.odrive_config_file != "":
            baud_rate = find_baudrate(odriveCAN.odrive_config_file)
            odriveCAN.baud_rate = str(baud_rate)
        else:
            odriveCAN.baud_rate = "250000"
        
        odriveCAN.logger.info("Remember to run 'sudo ip link set can0 up type can bitrate <baud_rate>' "+
                    "in your terminal. See the README Troubleshooting section for more details.")

        Thread(target=odriveCAN._periodically_surface_errors, daemon=True).start()
        Thread(target=odriveCAN._periodically_check_goal, daemon=True).start()

        return odriveCAN
    
    def _periodically_surface_errors(self):
        while True:
            asyncio.run(self.surface_errors())
            time.sleep(1)

    def _periodically_check_goal(self):
        while True:
            asyncio.run(self.check_goal())
            time.sleep(0.5)

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> Tuple[Sequence[str], Sequence[str]]:
        return [], []

    async def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        if config.attributes.fields["canbus_baud_rate"].string_value != "":
            baud_rate = config.attributes.fields["canbus_baud_rate"].string_value
            baud_rate = baud_rate.replace("k", "000")
            baud_rate = baud_rate.replace("K", "000")
        elif self.odrive_config_file != "":
            baud_rate = find_baudrate(self.odrive_config_file)
            baud_rate = str(baud_rate)
        else:
            baud_rate = self.baud_rate

        if baud_rate != self.baud_rate:
            self.baud_rate = baud_rate
            self.logger.info("Since you changed the baud rate, you must run 'sudo ip link set can0 up type can bitrate <baud_rate>' "+
                         "in your terminal. See the README Troubleshooting section for more details.")
        
        new_nodeID = config.attributes.fields["canbus_node_id"].number_value
        if new_nodeID != self.nodeID:
            await self.set_node_id(new_nodeID)

    async def set_power(self, power: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        if abs(power) < 0.001:
            self.logger.error("Cannot move motor at a power percent that is nearly 0")
        torque = power*self.current_limit*self.torque_constant
        await self.send_can_message('Set_Axis_State', {'Axis_Requested_State': 0x08})
        await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
        await self.send_can_message('Set_Controller_Mode', {'Control_Mode': 0x01, 'Input_Mode': 0x01})
        await self.send_can_message('Set_Input_Torque', {'Input_Torque': torque})

    async def go_for(self, rpm: float, revolutions: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        if abs(rpm) < 0.001:
            self.logger.error("Cannot move motor at an RPM that is nearly 0")
        rps = rpm / MINUTE_TO_SECOND
        await self.send_can_message('Set_Controller_Mode', {'Control_Mode': 0x03, 'Input_Mode': 0x05})
        await self.send_can_message('Set_Traj_Vel_Limit', {'Traj_Vel_Limit': abs(rps)})
        await self.send_can_message('Set_Axis_State', {'Axis_Requested_State': 0x08})
        await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)

        current_position = await self.get_position()
        goal_position = current_position + math.copysign(revolutions, rpm) + self.offset
        await self.send_can_message('Set_Input_Pos', {'Input_Pos': (goal_position), 'Vel_FF': 0, 'Torque_FF': 0})

        self.goal["position"] = goal_position
        self.goal["active"] = True
    
    async def go_to(self, rpm: float, position_revolutions: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        current_position = await self.get_position()
        revolutions = position_revolutions - current_position
        if abs(revolutions) > 0.01:
            await self.go_for(rpm, revolutions)
        else:
            self.logger.info("Already at requested position")
    
    async def set_rpm(self, rpm: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        if abs(rpm) < 0.001:
            self.logger.error("Cannot move motor at an RPM that is nearly 0")
        rps = rpm / MINUTE_TO_SECOND
        await self.send_can_message('Set_Controller_Mode', {'Control_Mode': 0x02, 'Input_Mode': 0x01})
        await self.send_can_message('Set_Axis_State', {'Axis_Requested_State': 0x08})
        await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
        await self.send_can_message('Set_Input_Vel', {'Input_Vel': rps, 'Input_Torque_FF': 0})

    async def reset_zero_position(self, offset: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        position = await self.get_position()
        self.offset += position

    async def get_position(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> float:
        for msg in self.bus:
            if msg.arbitration_id == ((self.nodeID << 5) | self.db.get_message_by_name('Get_Encoder_Estimates').frame_id):
                encoderCount = self.db.decode_message('Get_Encoder_Estimates', msg.data)
                return encoderCount['Pos_Estimate'] - self.offset

        self.logger.error("Position estimates not received, check that can0 is configured correctly")
        return 0.0
    
    async def get_properties(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> Motor.Properties:
        return Motor.Properties(position_reporting=True)
    
    async def stop(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        await self.send_can_message('Set_Axis_State', {'Axis_Requested_State': 0x01})

    async def is_powered(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> Tuple[bool, float]:
        current_power = 0
        for msg in self.bus:
            if msg.arbitration_id == ((self.nodeID << 5) | self.db.get_message_by_name('Heartbeat').frame_id):
                current_state = self.db.decode_message('Heartbeat', msg.data)['Axis_State']
                if (current_state != 0x0) & (current_state != 0x1):
                    for msg1 in self.bus:
                        if msg1.arbitration_id == ((self.nodeID << 5) | self.db.get_message_by_name('Get_Iq').frame_id):
                            current = self.db.decode_message('Get_Iq', msg1.data)['Iq_Setpoint']
                            current_power = current/self.current_limit
                            return [True, current_power]
                else:
                    return [False, 0]

    async def is_moving(self) -> bool:
        for msg in self.bus:
            if msg.arbitration_id == ((self.nodeID << 5) | self.db.get_message_by_name('Get_Encoder_Estimates').frame_id):
                estimates = self.db.decode_message('Get_Encoder_Estimates', msg.data)
                if abs(estimates['Vel_Estimate']) > 0.0:
                    return True
                else:
                    return False
    
    async def get_geometries(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> List[Geometry]:
        return []

    async def do_command(self, command: Mapping[str, ValueTypes], *, timeout: Optional[float] = None, **kwargs) -> Mapping[str, ValueTypes]:
        return {}

    async def wait_until_correct_state(self, state):
        timeout = time.time() + 60
        for msg in self.bus:
            if time.time() > timeout:
                self.logger.error("Unable to set to requested state, setting to idle")
                await self.send_can_message('Set_Axis_State', {'Axis_Requested_State': 0x01})
                return
            if msg.arbitration_id == ((self.nodeID << 5) | self.db.get_message_by_name('Heartbeat').frame_id):
                current_state = self.db.decode_message('Heartbeat', msg.data)['Axis_State']
                if current_state == state:
                    return

    async def surface_errors(self):
        for msg in self.bus:
            if msg.arbitration_id == ((self.nodeID << 5) | self.db.get_message_by_name('Heartbeat').frame_id):
                errors = self.db.decode_message('Heartbeat', msg.data)['Axis_Error']
                if errors != 0x0:
                    await self.stop()
                    self.logger.error(f"axis: {ODriveError(errors)}")
                    await self.clear_errors()

    async def check_goal(self):
        if self.goal["active"]:
            position = await self.get_position()
            if abs(position - self.goal["position"]) < 0.01:
                await self.stop()
                self.goal["active"] = False
    
    async def clear_errors(self):
        await self.send_can_message('Clear_Errors', {})

    async def set_node_id(self, new_nodeID):
        await self.send_can_message('Set_Axis_Node_ID', {'Axis_Node_ID': new_nodeID})
        self.nodeID = new_nodeID

    async def send_can_message(self, name, data):
        msg = self.db.get_message_by_name(name)
        data = msg.encode(data)
        msg = can.Message(arbitration_id=msg.frame_id | self.nodeID << 5, is_extended_id=False, data=data)
        try:
            self.bus.send(msg)
        except can.CanError:
            self.logger.error("Message (" + name + ") NOT sent! Please verify can0 is working first")
            self.logger.info("You may need to run 'sudo ip link set can0 up type can bitrate <baud_rate>' in your terminal. " +
                         "See the README Troubleshooting section for more details.")
