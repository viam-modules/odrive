"""
This files OdriveSerial model with the Viam Registry.
"""

from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.components.motor import Motor
from .odriveSerial import OdriveSerial

Registry.register_resource_creator(Motor.SUBTYPE, OdriveSerial.MODEL, ResourceCreatorRegistration(OdriveSerial.new, OdriveSerial.validate))
