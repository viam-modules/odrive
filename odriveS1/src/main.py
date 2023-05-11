import asyncio
import sys

from viam.proto.app.robot import ComponentConfig
from viam.components.motor import Motor
from viam.module.module import Module
from .odriveS1.odriveSetup import Odrive

async def main(address: str):
    """This function creates and starts a new module, after adding all desired resources.
    Resources must be pre-registered. For an example, see the `odriveS1.__init__.py` file.
    Args:
        address (str): The address to serve the module on
    """
    module = Module(address)
    module.add_model_from_registry(Motor.SUBTYPE, Odrive.MODEL)
    await module.start()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise Exception("Need socket path as command line argument")

    asyncio.run(main(sys.argv[1]))
