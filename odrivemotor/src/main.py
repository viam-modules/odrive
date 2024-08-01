import asyncio
import sys

from viam.components.motor import Motor
from viam.module.module import Module
from .odriveSerial.odriveSerial import OdriveSerial
from .odriveCAN.odriveCAN import OdriveCAN

async def main(address: str):
    """This function creates and starts a new module, after adding all desired resources.
    Resources must be pre-registered. For an example, see the `__init__.py` file.
    Args:
        address (str): The address to serve the module on
    """
    module = Module(address)
    module.add_model_from_registry(Motor.SUBTYPE, OdriveCAN.MODEL)
    module.add_model_from_registry(Motor.SUBTYPE, OdriveSerial.MODEL)
    await module.start()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise Exception("Need socket path as command line argument")

    asyncio.run(main(sys.argv[1]))
