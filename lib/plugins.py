#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2015 Thomas Voegtlin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import traceback
import sys
import os
import imp
import pkgutil
import time

from util import *
from i18n import _
from util import profiler, PrintError, DaemonThread
import wallet

class Plugins(DaemonThread):

    @profiler
    def __init__(self, config, is_local, gui_name):
        DaemonThread.__init__(self)
        if is_local:
            find = imp.find_module('plugins')
            plugins = imp.load_module('electrum_plugins', *find)
        else:
            plugins = __import__('electrum_plugins')
        self.pkgpath = os.path.dirname(plugins.__file__)
        self.config = config
        self.hw_wallets = {}
        self.plugins = {}
        self.gui_name = gui_name
        self.descriptions = []
        self.device_manager = DeviceMgr()

        for loader, name, ispkg in pkgutil.iter_modules([self.pkgpath]):
            m = loader.find_module(name).load_module(name)
            d = m.__dict__
            gui_good = gui_name in d.get('available_for', [])
            details = d.get('registers_wallet_type')
            if details:
                self.register_plugin_wallet(name, gui_good, details)
            if not gui_good:
                continue
            self.descriptions.append(d)
            if not d.get('requires_wallet_type') and config.get('use_' + name):
                self.load_plugin(config, name)

    def get(self, name):
        return self.plugins.get(name)

    def count(self):
        return len(self.plugins)

    def load_plugin(self, config, name):
        full_name = 'electrum_plugins.' + name + '.' + self.gui_name
        try:
            p = pkgutil.find_loader(full_name).load_module(full_name)
            plugin = p.Plugin(self, config, name)
            self.add_jobs(plugin.thread_jobs())
            self.plugins[name] = plugin
            self.print_error("loaded", name)
            return plugin
        except Exception:
            self.print_error("cannot initialize plugin", name)
            traceback.print_exc(file=sys.stdout)
            return None

    def close_plugin(self, plugin):
        self.remove_jobs(plugin.thread_jobs())

    def toggle_enabled(self, config, name):
        p = self.get(name)
        config.set_key('use_' + name, p is None, True)
        if p:
            self.plugins.pop(name)
            p.close()
            self.print_error("closed", name)
            return None
        return self.load_plugin(config, name)

    def is_available(self, name, w):
        for d in self.descriptions:
            if d.get('__name__') == name:
                break
        else:
            return False
        deps = d.get('requires', [])
        for dep, s in deps:
            try:
                __import__(dep)
            except ImportError:
                return False
        requires = d.get('requires_wallet_type', [])
        return not requires or w.wallet_type in requires

    def hardware_wallets(self, action):
        wallet_types, descs = [], []
        for name, (gui_good, details) in self.hw_wallets.items():
            if gui_good:
                try:
                    p = self.wallet_plugin_loader(name)
                    if action == 'restore' or p.is_enabled():
                        wallet_types.append(details[1])
                        descs.append(details[2])
                except:
                    self.print_error("cannot load plugin for:", name)
        return wallet_types, descs

    def register_plugin_wallet(self, name, gui_good, details):
        def dynamic_constructor(storage):
            return self.wallet_plugin_loader(name).wallet_class(storage)

        if details[0] == 'hardware':
            self.hw_wallets[name] = (gui_good, details)
        self.print_error("registering wallet %s: %s" %(name, details))
        wallet.wallet_types.append(details + (dynamic_constructor,))

    def wallet_plugin_loader(self, name):
        if not name in self.plugins:
            self.load_plugin(self.config, name)
        return self.plugins[name]

    def run(self):
        jobs = [job for plugin in self.plugins.values()
                for job in plugin.thread_jobs()]
        self.add_jobs(jobs)
        while self.is_running():
            time.sleep(0.1)
            self.run_jobs()
        self.print_error("stopped")


hook_names = set()
hooks = {}

def hook(func):
    hook_names.add(func.func_name)
    return func

def run_hook(name, *args):
    results = []
    f_list = hooks.get(name, [])
    for p, f in f_list:
        if p.is_enabled():
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


class BasePlugin(PrintError):

    def __init__(self, parent, config, name):
        self.parent = parent  # The plugins object
        self.name = name
        self.config = config
        self.wallet = None
        # add self to hooks
        for k in dir(self):
            if k in hook_names:
                l = hooks.get(k, [])
                l.append((self, getattr(self, k)))
                hooks[k] = l

    def diagnostic_name(self):
        return self.name

    def close(self):
        # remove self from hooks
        for k in dir(self):
            if k in hook_names:
                l = hooks.get(k, [])
                l.remove((self, getattr(self, k)))
                hooks[k] = l
        self.parent.close_plugin(self)
        self.on_close()

    def on_close(self):
        pass

    def requires_settings(self):
        return False

    def thread_jobs(self):
        return []

    def is_enabled(self):
        return self.is_available() and self.config.get('use_'+self.name) is True

    def is_available(self):
        return True

    def settings_dialog(self):
        pass


class DeviceMgr(PrintError):
    '''Manages hardware clients.  A client communicates over a hardware
    channel with the device.  A client is a pair: a device ID (serial
    number) and hardware port.  If either change then a different
    client is instantiated.

    In addition to tracking device IDs, the device manager tracks
    hardware wallets and manages wallet pairing.  A device ID may be
    paired with a wallet when it is confirmed that the hardware device
    matches the wallet, i.e. they have the same master public key.  A
    device ID can be unpaired if e.g. it is wiped.

    Because of hotplugging, a wallet must request its client
    dynamically each time it is required, rather than caching it
    itself.

    The device manager is shared across plugins, so just one place
    does hardware scans when needed.  By tracking device serial
    numbers the number of necessary hardware scans is reduced, e.g. if
    a device is plugged into a different port the wallet is
    automatically re-paired.

    Wallets are informed on connect / disconnect / unpairing events.
    It must implement connected(), disconnected() and unpaired()
    callbacks.  Being connected implies a pairing.  Being disconnected
    doesn't.  Callbacks can happen in any thread context, and we do
    them without holding the lock.

    This plugin is thread-safe.  Currently only USB is implemented.
    '''

    # Client lookup types.  CACHED will look up in our client cache
    # only.  PRESENT will do a scan if there is no client in the cache.
    # PAIRED will try and pair the wallet, which will involve requesting
    # a PIN and passphrase if they are enabled
    (CACHED, PRESENT, PAIRED) = range(3)

    def __init__(self):
        super(DeviceMgr, self).__init__()
        # Keyed by wallet.  The value is the device_id if the wallet
        # has been paired, and None otherwise.
        self.wallets = {}
        # A list of clients.  We create a client for every device present
        # that is of a registered hardware type
        self.clients = []
        # What we recognise.  Keyed by (vendor_id, product_id) pairs,
        # the value is a handler for those devices.  The handler must
        # implement
        self.recognised_hardware = {}
        # For synchronization
        self.lock = threading.RLock()

    def register_devices(self, handler, device_pairs):
        for pair in device_pairs:
            self.recognised_hardware[pair] = handler

    def close_client(self, client):
        with self.lock:
            if client in self.clients:
                self.clients.remove(client)
                client.close()

    def close_wallet(self, wallet):
        # Remove the wallet from our list; close any client
        with self.lock:
            device_id = self.wallets.pop(wallet, None)
            self.close_client(self.client_by_device_id(device_id))

    def clients_of_type(self, classinfo):
        with self.lock:
            return [client for client in self.clients
                    if isinstance(client, classinfo)]

    def client_by_device_id(self, device_id):
        with self.lock:
            for client in self.clients:
                if client.device_id() == device_id:
                    return client
            return None

    def wallet_by_device_id(self, device_id):
        with self.lock:
            for wallet, wallet_device_id in self.wallets.items():
                if wallet_device_id == device_id:
                    return wallet
            return None

    def paired_wallets(self):
        with self.lock:
            return [wallet for (wallet, device_id) in self.wallets.items()
                    if device_id is not None]

    def pair_wallet(self, wallet, client):
        assert client in self.clients
        self.print_error("paired:", wallet, client)
        self.wallets[wallet] = client.device_id()
        client.pair_wallet(wallet)
        wallet.connected()

    def scan_devices(self):
        # All currently supported hardware libraries use hid, so we
        # assume it here.  This can be easily abstracted if necessary.
        # Note this import must be local so those without hardware
        # wallet libraries are not affected.
        import hid

        self.print_error("scanning devices...")

        # First see what's connected that we know about
        devices = {}
        for d in hid.enumerate(0, 0):
            product_key = (d['vendor_id'], d['product_id'])
            device_id = d['serial_number']
            path = d['path']

            handler = self.recognised_hardware.get(product_key)
            if handler:
                devices[device_id] = (handler, path, product_key)

        # Now find out what was disconnected
        with self.lock:
            disconnected = [client for client in self.clients
                            if not client.device_id() in devices]

        # Close disconnected clients after informing their wallets
        for client in disconnected:
            wallet = self.wallet_by_device_id(client.device_id())
            if wallet:
                wallet.disconnected()
            self.close_client(client)

        # Now see if any new devices are present.
        for device_id, (handler, path, product_key) in devices.items():
            try:
                client = handler.create_client(path, product_key)
            except BaseException as e:
                self.print_error("could not create client", str(e))
                client = None
            if client:
                self.print_error("client created for", path)
                with self.lock:
                    self.clients.append(client)
                # Inform re-paired wallet
                wallet = self.wallet_by_device_id(device_id)
                if wallet:
                    self.pair_wallet(wallet, client)

    def get_client(self, wallet, lookup=PAIRED):
        '''Returns a client for the wallet, or None if one could not be
        found.'''
        with self.lock:
            device_id = self.wallets.get(wallet)
            client = self.client_by_device_id(device_id)
            if client:
                return client

        if lookup == DeviceMgr.CACHED:
            return None

        first_address, derivation = wallet.first_address()
        # Wallets don't have a first address in the install wizard
        # until account creation
        if not first_address:
            self.print_error("no first address for ", wallet)
            return None

        # We didn't find it, so scan for new devices.  We scan as
        # little as possible: some people report a USB scan is slow on
        # Linux when a Trezor is plugged in
        self.scan_devices()

        with self.lock:
            # Maybe the scan found it?  If the wallet has a device_id
            # from a prior pairing, we can determine success now.
            if device_id:
                return self.client_by_device_id(device_id)

            # Stop here if no wake and we couldn't find it.
            if lookup == DeviceMgr.PRESENT:
                return None

            # The wallet has not been previously paired, so get the
            # first address of all unpaired clients and compare.
            for client in self.clients:
                # If already paired skip it
                if self.wallet_by_device_id(client.device_id()):
                    continue
                # This will trigger a PIN/passphrase entry request
                if client.first_address(wallet, derivation) == first_address:
                    self.pair_wallet(wallet, client)
                    return client

            # Not found
            return None
