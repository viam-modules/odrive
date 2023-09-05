"""
This files OdriveCAN model with the Viam Registry.
"""

from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.components.motor import Motor
from .odriveCAN.odriveCAN import OdriveCAN

Registry.register_resource_creator(Motor.SUBTYPE, OdriveCAN.MODEL, ResourceCreatorRegistration(OdriveCAN.new, OdriveCAN.validate))
