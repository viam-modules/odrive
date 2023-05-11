from typing import ClassVar, Mapping, Any
from typing_extensions import Self

from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import Model, ModelFamily

from viam.components.motor import Motor
from viam.logging import getLogger

from odrive.enums import *
from .odriveCAN import OdriveCAN
from .odriveS1 import OdriveS1

LOGGER = getLogger(__name__)
MINUTE_TO_SECOND = 60

class Odrive(Motor, Reconfigurable):
    MODEL: ClassVar[Model] = Model(ModelFamily("viam-labs", "motor"), "odrive")
    serial_number: str
    max_rpm: float
    odrive_config_file: str
    odrv: Any

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        odrive = cls(config.name)
        print("start")
        if config.attributes.fields["connection_type"].string_value == "canbus":
            odrive.MODEL = ClassVar[Model] = Model(ModelFamily("viam-labs", "motor"), "odrive-can")
            print("here")
            obj = OdriveCAN()
            return obj
        else:
            return OdriveS1.new
