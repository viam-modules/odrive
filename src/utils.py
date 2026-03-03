import odrive
import json
from functools import reduce
from collections.abc import MutableMapping

# thank you to https://stackoverflow.com/questions/31174295/getattr-and-setattr-on-nested-objects/31174427?noredirect=1#comment86638618_31174427 for rsettr and rgettr

def rsetattr(obj, attr, val):
    pre, _, post = attr.rpartition('.')
    return setattr(rgetattr(obj, pre) if pre else obj, post, val)

def rgetattr(obj, attr, *args):
    def _getattr(obj, attr):
        return getattr(obj, attr, *args)
    return reduce(_getattr, [obj] + attr.split('.'))

def set_configs(odrv, config_path):
    with open(config_path) as json_file:
        configs = json.load(json_file)

    for k,v in flatten(configs).items():
        rsetattr(odrv, k, v)
    