import asyncio
import time
import argparse
from typing import Any, Optional, Tuple, Dict

from viam.components.motor import Motor
from viam.module.types import Reconfigurable

import odrive
from odrive.enums import *
import fibre.libfibre

class OdriveS1(Motor, Reconfigurable):
    max_rpm: float
    vel_limit: float
    serial_number: str
    odrv: Any

    def __init__(self, max_rpm, vel_limit, serial_number=None):
        self.max_rpm = max_rpm
        self.vel_limit = vel_limit
        self.odrv = odrive.find_any() if not serial_number else odrive.find_any(serial_number=serial_number)
    
    async def set_power(self, power: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        vel = power * (self.max_rpm / 60)
        self.odrv.axis0.controller.config.vel_limit = self.vel_limit
        self.odrv.axis0.controller.config.input_mode = InputMode.PASSTHROUGH
        self.odrv.axis0.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
        self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
        self.odrv.axis0.controller.input_vel = vel
        return

    async def go_for(self, rpm: float, revolutions: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.configure_trap_trajectory(rpm)
        current_position = await self.get_position()
        self.odrv.axis0.controller.input_pos = current_position + revolutions
        return

    async def go_to(self, rpm: float, revolutions: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.configure_trap_trajectory(rpm)
        self.odrv.axis0.controller.input_pos = revolutions
        return

    async def reset_zero_position(self, offset: float, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.odrv.hall_encoder0.set_linear_count(0)

    async def get_position(self, extra: Optional[Dict[str, Any]] = None, **kwargs):
        return self.odrv.axis0.pos_vel_mapper.pos_rel

    async def get_properties(self, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> Motor.Properties:
        return Motor.Properties(position_reporting=False)

    async def stop(self, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.odrv.axis0.requested_state = AxisState.IDLE

    async def is_powered(self, extra: Optional[Dict[str, Any]] = None, **kwargs) -> Tuple[bool, float]:
        return (self.odrv.axis0.requested_state != AxisState.IDLE, self.odrv.axis0.pos_vel_mapper.vel/self.max_rpm)

    async def is_moving(self):
        return abs(self.odrv.axis0.pos_vel_mapper.vel) > .0005
    
    def configure_trap_trajectory(self, rpm) -> None:
        rps = rpm / 60
        self.odrv.axis0.trap_traj.config.vel_limit = rps
        self.odrv.axis0.trap_traj.config.accel_limit = rps
        self.odrv.axis0.trap_traj.config.decel_limit = rps
        self.odrv.axis0.controller.config.vel_limit = self.vel_limit
        self.odrv.axis0.controller.config.input_mode = InputMode.TRAP_TRAJ
        self.odrv.axis0.controller.config.control_mode = ControlMode.POSITION_CONTROL
        self.odrv.axis0.requested_state = AxisState.CLOSED_LOOP_CONTROL
        return

def handle_set_power(args, odrv):
    if not args.power:
        print("--power must be provided in order to set power")
    else:
        odrv.set_power(args.power)

def handle_go(args, odrv):
    if not args.rpm or not args.revolutions:
        print("--rpm and --revolutions must be provided in order to go functions")
    elif args.go_for:
        odrv.go_for(args.rpm, args.revolutions)
    elif args.go_tp:
        odrv.go_to(args.rpm, args.revolutions)

def handle_request(args):
    odrv = OdriveS1(args.max_rpm, args.max_velocity, args.serial_number)
    if args.set_power:
        handle_set_power(args, odrv)
    elif args.go_for or args.go_to:
        handle_go(args, odrv)
    elif args.get_position:
        return odrv.get_position()
    elif args.get_properties:
        return odrv.get_properties()
    elif args.stop:
        return odrv.stop()
    elif args.is_powered:
        return odrv.is_powered()
    elif args.is_moving:
        return odrv.is_moving()

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-rpm', dest='max_rpm', type=int, required=True)
    parser.add_argument('--max-velocity', dest='max_velocity', type=int, required=True)
    parser.add_argument('--serial-number', dest='serial_number', type=int)
    parser.add_argument('--set-power', dest='set_power', action='store_true')
    parser.add_argument('--go-for', dest='go_for', action='store_true')
    parser.add_argument('--go-to', dest='go_to', action='store_true')
    parser.add_argument('--reset_zero_position', dest='reset-zero-position', action='store_true')
    parser.add_argument('--get_position', dest='get-position', action='store_true')
    parser.add_argument('--get_properties', dest='get-properties', action='store_true')
    parser.add_argument('--stop', dest='stop', action='store_true')
    parser.add_argument('--is_powered', dest='is-powered', action='store_true')
    parser.add_argument('--is_moving', dest='is-moving', action='store_true')

    parser.add_argument('--power', dest='power', type=float)
    parser.add_argument('--rpm', dest='rpm', type=float)
    parser.add_argument('--revolutions', dest='revolutions', type=float)
    
    args = parser.parse_args()
    handle_request(args)
    