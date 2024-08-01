import asyncio
import sys

from viam.components.motor import Motor
from viam.module.module import Module
from .odriveSerial.odriveSerial import OdriveSerial
from .odriveCAN.odriveCAN import OdriveCAN

async def main():
    """This function creates and starts a new module, after adding all desired resources.
    Resources must be pre-registered. For an example, see the `__init__.py` file.
    Args:
        address (str): The address to serve the module on
    """
    module = Module.from_args()
    module.add_model_from_registry(Motor.SUBTYPE, OdriveCAN.MODEL)
    module.add_model_from_registry(Motor.SUBTYPE, OdriveSerial.MODEL)
    await module.start()

if __name__ == "__main__":
    asyncio.run(main())
