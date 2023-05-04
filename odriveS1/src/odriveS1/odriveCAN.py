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
from .utils import set_configs

import can
import cantools
import time

db = cantools.database.load_file("odrive-cansimple.dbc")

bus = can.Bus("can0", bustype="socketcan")
axisID = 0x1

LOGGER = getLogger(__name__)
MINUTE_TO_SECOND = 60

class OdriveCAN(Motor, Reconfigurable):
    MODEL: ClassVar[Model] = Model(ModelFamily("viam-labs", "motor"), "odrive")
    serial_number: str
    max_rpm: float
    odrive_config_file: str
    baud_rate: str
    odrv: Any

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        odriveCAN = cls(config.name)
        odriveCAN.offset = 0
        odriveCAN.serial_number = config.attributes.fields["serial_number"].string_value
        odriveCAN.max_rpm = config.attributes.fields["max_rpm"].number_value
        odriveCAN.odrive_config_file = config.attributes.fields["odrive_config_file"].string_value
        odriveCAN.baud_rate = config.attributes.fields["baud_rate"].string_value
        
        os.system("sudo ip link set can0 up type can bitrate" + odriveCAN.baud_rate)

        odriveCAN.odrv = odrive.find_any() if odriveCAN.serial_number == "" else odrive.find_any(serial_number = odriveCAN.serial_number)
        odriveCAN.odrv.clear_errors()
        
        if odriveCAN.odrive_config_file != "":
            set_configs(odriveCAN.odrv, odriveCAN.odrive_config_file)

        def periodically_surface_errors(odrv):
            while True:
                asyncio.run(odrv.surface_errors())
                time.sleep(1)

        thread = Thread(target = periodically_surface_errors, args=[odriveCAN])
        thread.setDaemon(True) 
        thread.start()

        return odriveCAN
    
    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        self.serial_number = config.attributes.fields["serial_number"].string_value
        self.max_rpm = config.attributes.fields["max_rpm"].number_value
        
        baud_rate = config.attributes.fields["baud_rate"].string_value
        if baud_rate != self.baud_rate:
            self.baud_rate = baud_rate
            os.system("sudo ip link set can0 up type can bitrate" + baud_rate)
        
        config_file = config.attributes.fields["odrive_config_file"].string_value
        if (config_file != self.odrive_config_file) and config_file != "":
            LOGGER.info("Updating odrive configurations.")
            self.odrive_config_file = config_file
            set_configs(self.odrv, self.odrive_config_file)

    async def set_power(self, power: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        vel = power * (self.max_rpm / 60)

        msg = db.get_message_by_name('Set_Axis_State')
        data = msg.encode({'Axis_Requested_State': 0x08})
        msg = can.Message(arbitration_id=msg.frame_id | axisID << 5, is_extended_id=False, data=data)
        self.try_send(msg)
        await self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)

        msg = db.get_message_by_name('Set_Controller_Mode')
        data = msg.encode({'Control_Mode': 0x02, 'Input_Mode': 0x01})
        msg = can.Message(arbitration_id=0x00B | axisID << 5, is_extended_id=False, data=data)
        self.try_send(msg)

        msg = db.get_message_by_name('Set_Input_Vel')
        data = msg.encode({'Input_Vel': vel, 'Input_Torque_FF': 0})
        msg = can.Message(arbitration_id=0x00D | axisID << 5, is_extended_id=False, data=data)
        self.try_send(msg)

        msg = db.get_message_by_name('Set_Axis_State')
        data = msg.encode({'Axis_Requested_State': 0x01})
        msg = can.Message(arbitration_id=msg.frame_id | axisID << 5, is_extended_id=False, data=data)
        self.try_send(msg)

    async def go_for(self, rpm: float, revolutions: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        rps = rpm/60.0

        msg = db.get_message_by_name('Set_Axis_State')
        data = msg.encode({'Axis_Requested_State': 0x08})
        msg = can.Message(arbitration_id=msg.frame_id | axisID << 5, is_extended_id=False, data=data)
        self.try_send(msg)

        if revolutions == 0:
            msg = db.get_message_by_name('Set_Controller_Mode')
            data = msg.encode({'Control_Mode': 0x02, 'Input_Mode': 0x01})
            msg = can.Message(arbitration_id=0x00B | axisID << 5, is_extended_id=False, data=data)
            self.try_send(msg)
            
            msg = db.get_message_by_name('Set_Input_Vel')
            data = msg.encode({'Input_Vel': rps, 'Input_Torque_FF': 0})
            msg = can.Message(arbitration_id=0x00D | axisID << 5, is_extended_id=False, data=data)
            self.try_send(msg)

        else: 
            msg = db.get_message_by_name('Set_Controller_Mode')
            data = msg.encode({'Control_Mode': 0x03, 'Input_Mode': 0x05})
            msg = can.Message(arbitration_id=0x00B | axisID << 5, is_extended_id=False, data=data)
            self.try_send(msg)

            msg = db.get_message_by_name('Set_Limits')
            data = msg.encode({'Velocity_Limit': 4.0, 'Current_Limit': 40})
            msg = can.Message(arbitration_id=0x00F | axisID << 5, is_extended_id=False, data=data)
            self.try_send(msg)

            current_position = self.get_position()
            if rpm > 0:
                msg = db.get_message_by_name('Set_Input_Pos')
                data = msg.encode({'Input_Pos': (current_position+revolutions+self.offset), 'Vel_FF': 0, 'Torque_FF': 0})
                msg = can.Message(arbitration_id=0x00C | axisID << 5, is_extended_id=False, data=data)
                self.try_send(msg)
            else:
                msg = db.get_message_by_name('Set_Input_Pos')
                data = msg.encode({'Input_Pos': (current_position-revolutions+self.offset), 'Vel_FF': 0, 'Torque_FF': 0})
                msg = can.Message(arbitration_id=0x00C | axisID << 5, is_extended_id=False, data=data)
                self.try_send(msg)

    async def go_to(self, rpm: float, revolutions: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        current_position = await self.get_position()
        revolutions = revolutions - current_position
        await self.go_for(rpm, revolutions)

    async def reset_zero_position(self, offset: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        position = await self.get_position()
        self.offset += position

    async def get_position(self, extra: Optional[Dict[str, Any]] = None, **kwargs):
        msg = db.get_message_by_name('Get_Encoder_Count')
        data1 = msg.encode({'Shadow_Count': 0, 'Count_in_CPR': 4000})
        msg = can.Message(arbitration_id=0x00A | axisID << 5, is_extended_id=False, data=data1)
        self.try_send(msg)

        for msg in bus:
            if msg.arbitration_id == ((axisID << 5) | 0x004):
                encoderError = db.decode_message('Get_Encoder_Error')
                if encoderError != 0x00:
                    print("Encoder error!  Error code: "+str(hex(encoderError)))
                else:
                    break

            if msg.arbitration_id == ((axisID << 5) | 0x009):
                encoderCount = db.decode_message('Get_Encoder_Estimates', msg.data)
                return encoderCount['Pos_Estimate'] - self.offset

        LOGGER.error("Position estimates not received, check that can0 is configured correctly")
        return 0
    
    async def get_properties(self, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> Motor.Properties:
        return Motor.Properties(position_reporting=True)
    
    async def stop(self, extra: Optional[Dict[str, Any]] = None, **kwargs):
        msg = db.get_message_by_name('Set_Axis_State')
        data = msg.encode({'Axis_Requested_State': 0x01})
        msg = can.Message(arbitration_id=msg.frame_id | axisID << 5, is_extended_id=False, data=data)
        self.try_send(msg)

    async def is_powered(self, extra: Optional[Dict[str, Any]] = None, **kwargs) -> Tuple[bool, float]:
        current_power = 0
        for msg in bus:
            if msg.arbitration_id == ((axisID << 5) | db.get_message_by_name('Heartbeat').frame_id):
                current_state = db.decode_message('Heartbeat', msg.data)['Axis_State']
                if (current_state != 0x0) & (current_state != 0x1):
                    msg = db.get_message_by_name('Get_Encoder_Count')
                    data1 = msg.encode({'Shadow_Count': 0, 'Count_in_CPR': 4000})
                    msg = can.Message(arbitration_id=0x00A | axisID << 5, is_extended_id=False, data=data1)
                    bus.send(msg)

                    for msg1 in bus:
                            if msg1.arbitration_id == ((axisID << 5) | 0x009):
                                encoderCount = db.decode_message('Get_Encoder_Estimates', msg1.data)
                                current_power = encoderCount['Vel_Estimate']/(self.max_rpm/60)
                                print("current power", current_power)

                    return [True, current_power]
                else:
                    return [False, 0]

    
    async def is_moving(self):
        for msg in bus:
            if msg.arbitration_id == ((axisID << 5) | db.get_message_by_name('Heartbeat').frame_id):
                current_state = db.decode_message('Heartbeat', msg.data)['Axis_State']
                if (current_state != 0x0) & (current_state != 0x1):
                    return True
                else:
                    return False

    async def wait_until_correct_state(self, state):
        for msg in bus:
            current_state = db.decode_message('Heartbeat', msg.data)['Axis_State']
            if current_state == state:
                return
   
    async def wait_and_set_to_idle(self, rps, revolutions):
        time_sleep = abs(revolutions / rps) * 1.05
        await asyncio.sleep(time_sleep)
        msg = db.get_message_by_name('Set_Axis_State')
        data = msg.encode({'Axis_Requested_State': 0x01})
        msg = can.Message(arbitration_id=msg.frame_id | axisID << 5, is_extended_id=False, data=data)
        self.try_send(msg)

    async def try_send(msg):
        try:
            bus.send(msg)
        except can.CanError:
            LOGGER.error("Message NOT sent!  Please verify can0 is working first")

    async def surface_errors(self):
        for msg in bus:
            if msg.arbitration_id == ((axisID << 5) | db.get_message_by_name('Heartbeat').frame_id):
                errors = db.decode_message('Heartbeat', msg.data)['Axis_Error']
                if errors != 0x0:
                    await self.stop()
                    LOGGER.error("axis:", ODriveError(errors).name)
            
                    msg = db.get_message_by_name('Clear_Errors')
                    msg = can.Message(arbitration_id=msg.frame_id | axisID << 5, is_extended_id=False)
                    bus.send(msg)