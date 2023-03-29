import asyncio
import sys

from viam.components.motor import Motor
from viam.module.module import Module
from .odriveS1.odriveS1 import OdriveS1


async def main(address: str):
    """This function creates and starts a new module, after adding all desired resources.
    Resources must be pre-registered. For an example, see the `gizmo.__init__.py` file.
    Args:
        address (str): The address to serve the module on
    """
    module = Module(address)
    module.add_model_from_registry(Motor.SUBTYPE, OdriveS1.MODEL)
    await module.start()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise Exception("Need socket path as command line argument")

    asyncio.run(main(sys.argv[1]))
