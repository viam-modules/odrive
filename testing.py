import asyncio
import time

from viam.robot.client import RobotClient
from viam.rpc.dial import Credentials, DialOptions
from viam.components.motor import Motor


async def connect():
    creds = Credentials(
        type='robot-location-secret',
        payload='npd5y5ej86myjx44kkda5qq9fcptcnmznhfmniftfd7x0xem')
    opts = RobotClient.Options(
        refresh_interval=0,
        dial_options=DialOptions(credentials=creds)
    )
    return await RobotClient.at_address('kimsmac-main.l50o5rvufg.viam.cloud', opts)

async def main():
    robot = await connect()
    
    # odriveS1
    odrive_s_1 = Motor.from_robot(robot, "odriveS1")
    odrive_s_1_return_value = await odrive_s_1.get_position()
    print(f"odriveS1 get_position return value: {odrive_s_1_return_value}")
    odrive_s_1_return_value = await odrive_s_1.is_powered()
    print(f"odriveS1 is_powered return value: {odrive_s_1_return_value}")
    odrive_s_1_return_value = await odrive_s_1.is_moving()
    print(f"odriveS1 is_moving return value: {odrive_s_1_return_value}")

    await odrive_s_1.set_power(.5)
    time.sleep(5)
    await odrive_s_1.stop()
    

    # Don't forget to close the robot when you're done!
    await robot.close()

if __name__ == '__main__':
    asyncio.run(main())
