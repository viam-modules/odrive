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
import os
from .utils import set_configs, find_baudrate, rsetattr, find_motor_configs

import can
import cantools
import time

db = cantools.database.load_file("odrive-cansimple.dbc")
bus = can.Bus("can0", bustype="socketcan")

LOGGER = getLogger(__name__)
MINUTE_TO_SECOND = 60.0

class OdriveCAN(Motor, Reconfigurable):
    MODEL: ClassVar[Model] = Model(ModelFamily("viam-labs", "motor"), "odrive-canbus")
    odrive_config_file: str
    offset: float
    baud_rate: str
    odrv: Any
    nodeID: int
    torque_constant: float
    current_soft_max: float

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        odriveCAN = cls(config.name)
        odriveCAN.odrive_config_file = config.attributes.fields["odrive_config_file"].string_value
        odriveCAN.nodeID = int(config.attributes.fields["canbus_node_id"].number_value)
        odriveCAN.torque_constant = 1
        odriveCAN.current_soft_max = 60
        odriveCAN.offset = 0.0

        try:
            odriveCAN.odrv = odrive.find_any()
            if odriveCAN.odrive_config_file != "":
                set_configs(odriveCAN.odrv, odriveCAN.odrive_config_file)
                rsetattr(odriveCAN.odrv, "axis0.config.can.node_id", odriveCAN.nodeID)
                odriveCAN.torque_constant = find_motor_configs(odriveCAN.odrive_config_file, "torque_constant")
                odriveCAN.current_soft_max = find_motor_configs(odriveCAN.odrive_config_file, "current_soft_max")
        except TimeoutError:
            LOGGER.warn("Could not set odrive configurations because no serial odrive connection was found.")

        if config.attributes.fields["canbus_baud_rate"].string_value != "":
            baud_rate = config.attributes.fields["canbus_baud_rate"].string_value
            odriveCAN.baud_rate = baud_rate[0:len(baud_rate)-1] + "000"
        elif odriveCAN.odrive_config_file != "":
            baud_rate = find_baudrate(odriveCAN.odrive_config_file)
            odriveCAN.baud_rate = str(baud_rate)
        else:
            odriveCAN.baud_rate = "250000"

        os.system("sudo ip link set can0 down")
        os.system("sudo ip link set can0 up type can bitrate " + odriveCAN.baud_rate)
        # send an arbitrary message because the first message sent over CAN does not go through
        msg = db.get_message_by_name('Clear_Errors')
        msg = can.Message(arbitration_id=msg.frame_id | odriveCAN.nodeID << 5, is_extended_id=False)
        try:
            bus.send(msg)
        except can.CanError:
            pass

        def periodically_surface_errors(odriveCAN):
            while True:
                asyncio.run(odriveCAN.surface_errors())
                time.sleep(1)

        thread = Thread(target = periodically_surface_errors, args=[odriveCAN])
        thread.setDaemon(True) 
        thread.start()

        return odriveCAN

    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        baud_rate = "250000"
        if config.attributes.fields["canbus_baud_rate"].string_value != "":
            baud_rate = config.attributes.fields["canbus_baud_rate"].string_value
            baud_rate = baud_rate[0:len(baud_rate)-1] + "000"

        if baud_rate != self.baud_rate:
            self.baud_rate = baud_rate
            os.system("sudo ip link set can0 down")
            os.system("sudo ip link set can0 up type can bitrate " + self.baud_rate)
            msg = db.get_message_by_name('Clear_Errors')
            msg = can.Message(arbitration_id=msg.frame_id | self.nodeID << 5, is_extended_id=False)
            try:
                bus.send(msg)
            except can.CanError:
                pass
        
        new_nodeID = config.attributes.fields["canbus_node_id"].number_value
        if new_nodeID != self.nodeID:
            self.set_node_id(new_nodeID)

    async def set_power(self, power: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        torque = power*self.current_soft_max*self.torque_constant

        msg = db.get_message_by_name('Set_Axis_State')
        data = msg.encode({'Axis_Requested_State': 0x08})
        msg = can.Message(arbitration_id=msg.frame_id | self.nodeID << 5, is_extended_id=False, data=data)
        await self.try_send(msg)
        await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)

        msg = db.get_message_by_name('Set_Controller_Mode')
        data = msg.encode({'Control_Mode': 0x01, 'Input_Mode': 0x01})
        msg = can.Message(arbitration_id=0x00B | self.nodeID << 5, is_extended_id=False, data=data)
        await self.try_send(msg)

        msg = db.get_message_by_name('Set_Input_Torque')
        data = msg.encode({'Input_Torque': torque})
        msg = can.Message(arbitration_id=0x00E | self.nodeID << 5, is_extended_id=False, data=data)
        await self.try_send(msg)

    async def go_for(self, rpm: float, revolutions: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        rps = rpm / MINUTE_TO_SECOND

        msg = db.get_message_by_name('Set_Axis_State')
        data = msg.encode({'Axis_Requested_State': 0x08})
        msg = can.Message(arbitration_id=msg.frame_id | self.nodeID << 5, is_extended_id=False, data=data)
        await self.try_send(msg)
        await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)

        if revolutions == 0.0:
            msg = db.get_message_by_name('Set_Controller_Mode')
            data = msg.encode({'Control_Mode': 0x02, 'Input_Mode': 0x01})
            msg = can.Message(arbitration_id=0x00B | self.nodeID << 5, is_extended_id=False, data=data)
            await self.try_send(msg)
            
            msg = db.get_message_by_name('Set_Input_Vel')
            data = msg.encode({'Input_Vel': rps, 'Input_Torque_FF': 0})
            msg = can.Message(arbitration_id=0x00D | self.nodeID << 5, is_extended_id=False, data=data)
            await self.try_send(msg)

        else: 
            msg = db.get_message_by_name('Set_Controller_Mode')
            data = msg.encode({'Control_Mode': 0x03, 'Input_Mode': 0x05})
            msg = can.Message(arbitration_id=0x00B | self.nodeID << 5, is_extended_id=False, data=data)
            await self.try_send(msg)

            msg = db.get_message_by_name('Set_Limits')
            data = msg.encode({'Velocity_Limit': 10.0, 'Current_Limit': 40.0})
            msg = can.Message(arbitration_id=0x00F | self.nodeID << 5, is_extended_id=False, data=data)
            await self.try_send(msg)

            current_position = await self.get_position()
            if rpm > 0.0:
                msg = db.get_message_by_name('Set_Input_Pos')
                goal_position = current_position+revolutions+self.offset
                data = msg.encode({'Input_Pos': (goal_position), 'Vel_FF': 0, 'Torque_FF': 0})
                msg = can.Message(arbitration_id=0x00C | self.nodeID << 5, is_extended_id=False, data=data)
                await self.try_send(msg)
            else:
                msg = db.get_message_by_name('Set_Input_Pos')
                goal_position = current_position-revolutions+self.offset
                data = msg.encode({'Input_Pos': (goal_position), 'Vel_FF': 0, 'Torque_FF': 0})
                msg = can.Message(arbitration_id=0x00C | self.nodeID << 5, is_extended_id=False, data=data)
                await self.try_send(msg)

            await self.wait_and_set_to_idle(goal_position)

    async def go_to(self, rpm: float, revolutions: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        current_position = await self.get_position()
        revolutions = revolutions - current_position
        await self.go_for(rpm, revolutions)

    async def reset_zero_position(self, offset: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        position = await self.get_position()
        self.offset += position

    async def get_position(self, extra: Optional[Dict[str, Any]] = None, **kwargs) -> float:
        msg = db.get_message_by_name('Get_Encoder_Count')
        data1 = msg.encode({'Shadow_Count': 0, 'Count_in_CPR': 4000})
        msg = can.Message(arbitration_id=0x00A | self.nodeID << 5, is_extended_id=False, data=data1)
        await self.try_send(msg)

        for msg in bus:
            if msg.arbitration_id == ((self.nodeID << 5) | 0x004):
                encoderError = db.decode_message('Get_Encoder_Error', msg.data)
                if encoderError != 0x00:
                    LOGGER.error("Encoder error!  Error code: "+str(hex(encoderError)))
                else:
                    break

            if msg.arbitration_id == ((self.nodeID << 5) | 0x009):
                encoderCount = db.decode_message('Get_Encoder_Estimates', msg.data)
                return encoderCount['Pos_Estimate'] - self.offset

        LOGGER.error("Position estimates not received, check that can0 is configured correctly")
        return 0.0
    
    async def get_properties(self, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> Motor.Properties:
        return Motor.Properties(position_reporting=True)
    
    async def stop(self, extra: Optional[Dict[str, Any]] = None, **kwargs):
        msg = db.get_message_by_name('Set_Axis_State')
        data = msg.encode({'Axis_Requested_State': 0x01})
        msg = can.Message(arbitration_id=msg.frame_id | self.nodeID << 5, is_extended_id=False, data=data)
        await self.try_send(msg)

    async def is_powered(self, extra: Optional[Dict[str, Any]] = None, **kwargs) -> Tuple[bool, float]:
        current_power = 0
        for msg in bus:
            if msg.arbitration_id == ((self.nodeID << 5) | db.get_message_by_name('Heartbeat').frame_id):
                current_state = db.decode_message('Heartbeat', msg.data)['Axis_State']
                if (current_state != 0x0) & (current_state != 0x1):
                    msg = db.get_message_by_name('Get_Iq')
                    data = msg.encode({'Iq_Setpoint': 0, 'Iq_Measured': 0})
                    msg = can.Message(arbitration_id=0x014 | self.nodeID << 5, is_extended_id=False, data=data)
                    self.try_send(msg)

                    for msg1 in bus:
                        if msg1.arbitration_id == ((self.nodeID << 5) | 0x014):
                            current = db.decode_message('Get_Iq', msg1.data)['Iq_Setpoint']
                            current_power = current/self.current_soft_max
                            return [True, current_power]
                else:
                    return [False, 0]

    
    async def is_moving(self) -> bool:
        for msg in bus:
            if msg.arbitration_id == ((self.nodeID << 5) | db.get_message_by_name('Heartbeat').frame_id):
                current_state = db.decode_message('Heartbeat', msg.data)['Axis_State']
                if (current_state != 0x0) & (current_state != 0x1):
                    return True
                else:
                    return False
                
    async def do_command(self) -> Dict[str, Any]:
        pass

    async def wait_until_correct_state(self, state):
        for msg in bus:
            current_state = db.decode_message('Heartbeat', msg.data)['Axis_State']
            if current_state == state:
                return
   
    async def wait_and_set_to_idle(self, goal):
        while True:
            position = await self.get_position()
            if abs(position - goal) <= 0.01:
                msg = db.get_message_by_name('Set_Axis_State')
                data = msg.encode({'Axis_Requested_State': 0x01})
                msg = can.Message(arbitration_id=msg.frame_id | self.nodeID << 5, is_extended_id=False, data=data)
                await self.try_send(msg)

    async def try_send(self, msg):
        try:
            bus.send(msg)
        except can.CanError:
            LOGGER.error("Message NOT sent! Please verify can0 is working first")

    async def surface_errors(self):
        for msg in bus:
            if msg.arbitration_id == ((self.nodeID << 5) | db.get_message_by_name('Heartbeat').frame_id):
                errors = db.decode_message('Heartbeat', msg.data)['Axis_Error']
                if errors != 0x0:
                    await self.stop()
                    LOGGER.error("axis:", ODriveError(errors).name)
            
                    self.clear_errors()
    
    async def clear_errors(self):
        msg = db.get_message_by_name('Clear_Errors')
        msg = can.Message(arbitration_id=msg.frame_id | self.nodeID << 5, is_extended_id=False)
        await self.try_send(msg)

    async def set_node_id(self, new_nodeID):
        msg = db.get_message_by_name('Set_Axis_Node_ID')
        data = msg.encode({'Axis_Node_ID': new_nodeID})
        msg = can.Message(arbitration_id=msg.frame_id | self.nodeID << 5, is_extended_id=False, data=data)
        await self.try_send(msg)
        self.nodeID = new_nodeID