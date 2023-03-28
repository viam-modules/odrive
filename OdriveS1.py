import asyncio
import argparse
from typing import Any, Optional, Tuple, Dict

from viam.components.motor import Motor
from viam.module.types import Reconfigurable

import odrive
from odrive.enums import *
import fibre.libfibre

MINUTE_TO_SECOND = 60

class OdriveS1(Motor, Reconfigurable):
    max_rpm: float
    vel_limit: float
    serial_number: str
    odrv: Any

    def __init__(self, serial_number=None):
        self.odrv = odrive.find_any() if (not serial_number or serial_number == "") else odrive.find_any(serial_number=serial_number)
    
    def wait_until_correct_state(self, state):
        while self.odrv.axis0.current_state != state:
            continue
    
    def configure_trap_trajectory(self, rpm) -> None:
        rps = rpm / MINUTE_TO_SECOND
        self.odrv.axis0.trap_traj.config.vel_limit = rps
        self.odrv.axis0.trap_traj.config.accel_limit = rps
        self.odrv.axis0.trap_traj.config.decel_limit = rps
        self.odrv.axis0.controller.config.input_mode = InputMode.TRAP_TRAJ
        self.odrv.axis0.controller.config.control_mode = ControlMode.POSITION_CONTROL
        self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
        self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
    
    async def set_power(self, args):
        if not args.power:
            print("--power must be provided in order to set power")
            return 
        
        if not args.max_rpm:
            print("--max-rpm must be provided in order to set power")
            return 
        
        vel = args.power * (args.max_rpm / MINUTE_TO_SECOND)
        self.odrv.axis0.controller.config.input_mode = InputMode.PASSTHROUGH
        self.odrv.axis0.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
        self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
        self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
        # the line below causes motion.
        self.odrv.axis0.controller.input_vel = vel

    async def go_for(self, args):
        if args.rpm == None:
            print("--rpm must be provided in order to use the go functions")
            return 
        if  args.revolutions == None:
            print("--revolutions must be provided in order to use the go functions")
            return 
        if args.offset == None:
            print("--offset must be provided in order to to use the go functions")
            return

        if args.revolutions == 0:
            self.odrv.axis0.controller.config.input_mode = InputMode.PASSTHROUGH
            self.odrv.axis0.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
            self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
            self.wait_until_correct_state(AxisState.CLOSED_LOOP_CONTROL)
            self.odrv.axis0.controller.input_vel = args.rpm / MINUTE_TO_SECOND
        else:
            self.configure_trap_trajectory(args.rpm)
            current_position = await self.get_position(args)
            if args.rpm > 0:
                # the line below causes motion.
                self.odrv.axis0.controller.input_pos = current_position + args.revolutions + args.offset
            else:
                # the line below causes motion.
                self.odrv.axis0.controller.input_pos = current_position - args.revolutions + args.offset
        '''
        Should the state be set back from closed loop control to idle after completion?
        If so, how should we determine when this has completed? When enough time has passed for it to finish based 
        on rpm and revolutions, or when the position is close to what we expect it to be, or other/better ideas?
        '''
   
    async def go_to(self, args):
        current_position = await self.get_position(args)
        args.revolutions = args.revolutions - current_position
        await self.go_for(args)

    async def reset_zero_position(self, float):
        pass

    async def get_position(self, args):
        if args.offset is None:
            print("--offset must be provided in order to get position")
            return
        
        return self.odrv.axis0.pos_vel_mapper.pos_rel - args.offset
   
    async def get_properties(self, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> Motor.Properties:
        return Motor.Properties(position_reporting=False)

    async def stop(self):
        self.odrv.axis0.requested_state = AxisState.IDLE

    async def is_powered(self, args) -> Tuple[bool, float]:
        if not args.max_rpm:
            print("--max-rpm must be provided in order to set power")
            return 
        return (self.odrv.axis0.current_state != AxisState.IDLE and self.odrv.axis0.current_state != AxisState.UNDEFINED, self.odrv.axis0.pos_vel_mapper.vel/(args.max_rpm / MINUTE_TO_SECOND))

    async def is_moving(self):
        return self.odrv.axis0.current_state != AxisState.IDLE

# In order to get the return value from relevant functions in go, we must print the return value. 
async def handle_request(args):
    odrv = OdriveS1(args.serial_number)
    errorCode = odrv.odrv.axis0.active_errors
    if  errorCode != 0:
        await odrv.stop()
        print(ODriveError(errorCode).name)
        return

    if args.set_power:
        await odrv.set_power(args)

    elif args.go_for:
        await odrv.go_for(args)
    
    elif args.go_to:
        await odrv.go_to(args)

    elif args.reset_zero_position:
        print("reset 0 position should be handled in the go file")
    
    elif args.get_position:
        print(await odrv.get_position(args))

    elif args.get_properties:
        print(await odrv.get_properties())
    
    elif args.stop:
        return await odrv.stop()
    
    elif args.is_powered:
        is_powered, power = await odrv.is_powered(args)
        print(f"{is_powered} {power}")

    elif args.is_moving:
        print(await odrv.is_moving())

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-rpm', dest='max_rpm', type=float)
    parser.add_argument('--serial-number', dest='serial_number', type=str)
    parser.add_argument('--set-power', dest='set_power', action='store_true')
    parser.add_argument('--go-for', dest='go_for', action='store_true')
    parser.add_argument('--go-to', dest='go_to', action='store_true')
    parser.add_argument('--reset-zero-position', dest='reset_zero_position', action='store_true')
    parser.add_argument('--get-position', dest='get_position', action='store_true')
    parser.add_argument('--get-properties', dest='get_properties', action='store_true')
    parser.add_argument('--stop', dest='stop', action='store_true')
    parser.add_argument('--is-powered', dest='is_powered', action='store_true')
    parser.add_argument('--is-moving', dest='is_moving', action='store_true')

    parser.add_argument('--power', dest='power', type=float)
    parser.add_argument('--rpm', dest='rpm', type=float)
    parser.add_argument('--revolutions', dest='revolutions', type=float)
    parser.add_argument('--offset', dest='offset', type=float)
    
    args = parser.parse_args()
    asyncio.run(handle_request(args))
    