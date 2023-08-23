"""
This files odrive model with the Viam Registry.
"""

from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.components.motor import Motor
from .odriveSerial import OdriveSerial
from .odriveCAN import OdriveCAN

Registry.register_resource_creator(Motor.SUBTYPE, OdriveSerial.MODEL, ResourceCreatorRegistration(OdriveSerial.new, OdriveSerial.validate))
Registry.register_resource_creator(Motor.SUBTYPE, OdriveCAN.MODEL, ResourceCreatorRegistration(OdriveCAN.new, OdriveCAN.validate))
