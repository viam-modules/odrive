import argparse
import asyncio

async def get_print():
    if args.test:
        print("hello world")
    else:
        print("goodbye")

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', dest='test', action='store_true')
    args = parser.parse_args()
    asyncio.run(get_print())
