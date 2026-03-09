import sys
import types

if "pkg_resources" not in sys.modules:
    mod = types.ModuleType("pkg_resources")
    mod.iter_entry_points = lambda group, name=None: iter([])
    sys.modules["pkg_resources"] = mod
