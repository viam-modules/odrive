import odrive
import json
from functools import reduce
from collections.abc import MutableMapping

# thank you to https://stackoverflow.com/questions/6027558/flatten-nested-dictionaries-compressing-keys for flatten

def flatten(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

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

def find_baudrate(config_path):
    with open(config_path) as json_file:
        configs = json.load(json_file)

    if configs["can"]["config"]["baud_rate"]:
        return configs["can"]["config"]["baud_rate"]
    else:
        return 250000
    
def find_axis_configs(config_path, config_params):
    with open(config_path) as json_file:
        configs = json.load(json_file)
    
    value = configs["axis0"]["config"]
    for i in range(len(config_params)):
        value = value[config_params[i]]

    return value
