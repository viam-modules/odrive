import asyncio

from viam.module.module import Module

from models.odriveSerial import OdriveSerial  # noqa: F401  # registers the model with the Viam registry

if __name__ == "__main__":
    asyncio.run(Module.run_from_registry())
