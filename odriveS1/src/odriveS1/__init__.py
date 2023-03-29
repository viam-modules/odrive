"""
This file odriveS1 model  with the Viam Registry.
"""

from viam.resource.registry import Registry
from viam.components.motor import Motor
from .odriveS1 import OdriveS1

Registry.register_resource_creator(Motor.SUBTYPE, OdriveS1.MODEL, OdriveS1.new)
