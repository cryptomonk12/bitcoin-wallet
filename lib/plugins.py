from util import print_error
import traceback, sys
from util import *
from i18n import _

plugins = []


def init_plugins(config):
    import imp, pkgutil, __builtin__, os
    global plugins

    if __builtin__.use_local_modules:
        fp, pathname, description = imp.find_module('plugins')
        plugin_names = [name for a, name, b in pkgutil.iter_modules([pathname])]
        plugin_names = filter( lambda name: os.path.exists(os.path.join(pathname,name+'.py')), plugin_names)
        imp.load_module('electrum_plugins', fp, pathname, description)
        plugin_modules = map(lambda name: imp.load_source('electrum_plugins.'+name, os.path.join(pathname,name+'.py')), plugin_names)
    else:
        import electrum_plugins
        plugin_names = [name for a, name, b in pkgutil.iter_modules(electrum_plugins.__path__)]
        plugin_modules = [ __import__('electrum_plugins.'+name, fromlist=['electrum_plugins']) for name in plugin_names]

    for name, p in zip(plugin_names, plugin_modules):
        try:
            plugins.append( p.Plugin(config, name) )
        except Exception:
            print_msg(_("Error: cannot initialize plugin"),p)
            traceback.print_exc(file=sys.stdout)


hook_names = set()
hooks = {}

def hook(func):
    n = func.func_name
    if n not in hook_names:
        hook_names.add(n)
    return func


def run_hook(name, *args):
    results = []
    f_list = hooks.get(name,[])
    for p, f in f_list:
        if not p.is_enabled():
            continue
        try:
            r = f(*args)
        except Exception:
            print_error("Plugin error")
            traceback.print_exc(file=sys.stdout)
            r = False
        if r:
            results.append(r)

    if results:
        assert len(results) == 1, results
        return results[0]


class BasePlugin:

    def __init__(self, config, name):
        self.name = name
        self.config = config
        # add self to hooks
        for k in dir(self):
            if k in hook_names:
                l = hooks.get(k, [])
                l.append((self, getattr(self, k)))
                hooks[k] = l

    def fullname(self):
        return self.name

    def description(self):
        return 'undefined'

    def requires_settings(self):
        return False

    def toggle(self):
        if self.is_enabled():
            if self.disable():
                self.close()
        else:
            if self.enable():
                self.init()

        return self.is_enabled()
    
    def enable(self):
        self.set_enabled(True)
        return True

    def disable(self):
        self.set_enabled(False)
        return True

    def init(self): pass

    def close(self): pass

    def is_enabled(self):
        return self.is_available() and self.config.get('use_'+self.name) is True

    def is_available(self):
        return True

    def set_enabled(self, enabled):
        self.config.set_key('use_'+self.name, enabled, True)

    def settings_dialog(self):
        pass

