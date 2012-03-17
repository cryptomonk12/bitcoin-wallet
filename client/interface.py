#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2011 thomasv@gitorious
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


import random, socket, ast

        
import thread, traceback, sys, time, json

DEFAULT_TIMEOUT = 5
DEFAULT_SERVERS = ['ecdsa.org','electrum.novit.ro']  # list of default servers


class Interface:
    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.servers = DEFAULT_SERVERS                            # actual list from IRC
        self.rtime = 0
        self.blocks = 0 
        self.message = ''
        self.was_updated = True # fixme: use a semaphore
        self.is_up_to_date = False # True after the first poll

        self.is_connected = False
        self.disconnected_event = threading.Event()
        self.disconnected_event.clear()

    def send_tx(self, data):
        out = self.handler('transaction.broadcast', data )
        return out

    def get_servers(self):
        pass

    def start_session(self, wallet):
        pass


class NativeInterface(Interface):
    """This is the original Electrum protocol. It uses polling, and a non-persistent tcp connection"""

    def __init__(self, host, port):
        Interface.__init__(self, host, port)

    def start_session(self, wallet):
        addresses = wallet.all_addresses()
        version = wallet.electrum_version
        out = self.handler('session.new', [ version, addresses ] )
        self.session_id, self.message = ast.literal_eval( out )
        thread.start_new_thread(self.poll_thread, (wallet,))

    def update_session(self, addresses):
        out = self.handler('session.update', [ self.session_id, addresses ] )
        return out    

    def handler(self, method, params = ''):
        import time
        cmds = {'session.new':'new_session',
                'peers':'peers',
                'session.poll':'poll',
                'session.update':'update_session',
                'transaction.broadcast':'tx',
                'address.get_history':'h',
                'address.subscribe':'address.subscribe'
                }
        cmd = cmds[method]
        if type(params) != type(''): params = repr( params )
        t1 = time.time()
        request = repr ( (cmd, params) ) + "#"
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(DEFAULT_TIMEOUT)
        s.connect(( self.host if cmd!='peers' else self.peers_server, self.port) )
        s.send( request )
        out = ''
        while 1:
            msg = s.recv(1024)
            if msg: out += msg
            else: break
        s.close()
        self.rtime = time.time() - t1
        self.is_connected = True
        if cmd in[ 'peers','h']:
            out = ast.literal_eval( out )
        return out

    def poll_interval(self):
        return 5

    def retrieve_history(self, address):
        out = self.handler('address.get_history', address )
        return out

    def get_history(self, addr, history_callback):
        data = self.retrieve_history(addr)
        apply(history_callback, (addr, data) )
        self.was_updated = True

    def subscribe(self, addr, status_callback):
        status = self.handler('address.subscribe', [ self.session_id, addr ] )
        apply(status_callback, (addr, status) )

    def update_wallet(self, wallet):
        while True:
            changed_addresses = self.poll()
            if changed_addresses:
                self.is_up_to_date = False
            else:
                self.is_up_to_date = True
                break

            for addr, status in changed_addresses.items():
                wallet.receive_status_callback(addr, status)

        #if is_new or wallet.remote_url:
        #    self.was_updated = True
        #    is_new = wallet.synchronize()
        #    wallet.update_tx_history()
        #    wallet.save()
        #    return is_new
        #else:
        #    return False

    def poll(self):
        out = self.handler('session.poll', self.session_id )
        blocks, changed_addr = ast.literal_eval( out )
        if blocks == -1: raise BaseException("session not found")
        self.blocks = int(blocks)
        return changed_addr

    def poll_thread(self, wallet):
        while self.is_connected:
            try:
                self.update_wallet(wallet)
                time.sleep(self.poll_interval())
            except socket.gaierror:
                break
            except socket.error:
                break
            except:
                traceback.print_exc(file=sys.stdout)
                break
            
        self.is_connected = False
        self.disconnected_event.set()

                
    def get_servers(self):
        thread.start_new_thread(self.update_servers_thread, ())

    def update_servers_thread(self):
        # if my server is not reachable, I should get the list from one of the default servers
        # requesting servers could be an independent process
        while True:
            for server in DEFAULT_SERVERS:
                try:
                    self.peers_server = server
                    out = self.handler('peers')
                    self.servers = map( lambda x:x[1], out )
                    # print "Received server list from %s" % self.peers_server, out
                    break
                except socket.timeout:
                    continue
                except socket.error:
                    continue
                except:
                    traceback.print_exc(file=sys.stdout)

            time.sleep(5*60)



class HttpInterface(NativeInterface):

    def handler(self, method, params = []):
        import urllib2, json, time
        if type(params) != type([]): params = [ params ]
        t1 = time.time()
        data = { 'method':method, 'id':'jsonrpc', 'params':params }
        data_json = json.dumps(data)
        host = 'http://%s:%d'%( self.host if method!='peers' else self.peers_server, self.port )
        req = urllib2.Request(host, data_json, {'content-type': 'application/json'})
        response_stream = urllib2.urlopen(req)
        response = json.loads( response_stream.read() )
        out = response.get('result')
        if not out:
            print response
        self.rtime = time.time() - t1
        self.is_connected = True
        return out




import threading

class TCPInterface(Interface):
    """json-rpc over persistent TCP connection"""

    def __init__(self, host, port):
        Interface.__init__(self, host, port)
        self.message_id = 0
        self.messages = {}

        self.tx_event = threading.Event()
        self.addresses_waiting_for_status = []
        self.addresses_waiting_for_history = []
        # up to date
        self.is_up_to_date = False
        self.up_to_date_event = threading.Event()
        self.up_to_date_event.clear()

    def send(self, method, params = []):
        request = json.dumps( { 'id':self.message_id, 'method':method, 'params':params } )
        self.messages[self.message_id] = (method, params)
        self.s.send( request + '\n' )
        self.message_id += 1

    def listen_thread(self, wallet):
        try:
            self.is_connected = True
            out = ''
            while self.is_connected:
                try: msg = self.s.recv(1024)
                except socket.timeout: continue
                out += msg
                if msg == '': 
                    self.is_connected = False
                    print "disconnected."

                while True:
                    s = out.find('\n')
                    if s==-1: break
                    c = out[0:s]
                    out = out[s+1:]
                    c = json.loads(c)

                    #print c
                    msg_id = c.get('id')
                    result = c.get('result')
                    error = c.get('error')

                    if msg_id is None:
                        print "error: message without ID"
                        continue

                    method, params = self.messages[msg_id]

                    if method == 'server.banner':
                        self.message = result
                        self.was_updated = True

                    elif method == 'server.peers':
                        self.servers = map( lambda x:x[1], result )

                    elif method == 'address.subscribe':
                        addr = params[0]
                        if addr in self.addresses_waiting_for_status:
                            self.addresses_waiting_for_status.remove(addr)
                        wallet.receive_status_callback(addr, result)
                            
                    elif method == 'address.get_history':
                        addr = params[0]
                        if addr in self.addresses_waiting_for_history:
                            self.addresses_waiting_for_history.remove(addr)
                        wallet.receive_history_callback(addr, result)
                        self.was_updated = True

                    elif method == 'transaction.broadcast':
                        self.tx_result = result
                        self.tx_event.set()

                    elif method == 'numblocks.subscribe':
                        self.blocks = result

                    else:
                        print "received message:", c

                    if self.addresses_waiting_for_status or self.addresses_waiting_for_history:
                        self.is_up_to_date = False
                    else:
                        self.is_up_to_date = True
                        self.up_to_date_event.set()
        except:
            traceback.print_exc(file=sys.stdout)

        self.is_connected = False
        self.disconnected_event.set()

    def update_wallet(self,wallet):
        self.up_to_date_event.wait()

    def send_tx(self, data):
        self.tx_event.clear()
        self.send('transaction.broadcast', [data] )
        self.tx_event.wait()
        return self.tx_result

    def subscribe(self, address, callback):
        self.send('address.subscribe', [address])
        self.addresses_waiting_for_status.append(address)
        
    def get_servers(self):
        self.send('server.peers')

    def get_history(self, addr, callback):
        self.send('address.get_history', [addr])
        self.addresses_waiting_for_history.append(addr) 

    def start_session(self, wallet):
        self.s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        self.s.settimeout(1)
        self.s.connect(( self.host, self.port))
        thread.start_new_thread(self.listen_thread, (wallet,))
        self.send('client.version', [wallet.electrum_version])
        self.send('server.banner')
        self.send('numblocks.subscribe')
        for address in wallet.all_addresses():
            self.subscribe(address, wallet.receive_status_callback)






def new_interface(wallet):
    if wallet.host:
        host = wallet.host
    else:
        host = random.choice( DEFAULT_SERVERS )         # random choice when the wallet is created
    port = wallet.port

    if port == 50000:
        interface = NativeInterface(host,port)
    elif port == 50001:
        interface = TCPInterface(host,port)
    elif port in [80, 81, 8080, 8081]:
        interface = HttpInterface(host,port)            
    else:
        print "unknown port number: %d. using native protocol."%port
        interface = NativeInterface(host,port)
        
    return interface
       

def loop_interfaces_thread(wallet):
    while True:
        try:
            wallet.interface.start_session(wallet)
            wallet.interface.get_servers()

            wallet.interface.disconnected_event.wait()
            print "Disconnected"
        except socket.error:
            print "socket error"
            time.sleep(5)
        except:
            traceback.print_exc(file=sys.stdout)
            continue

        print "Starting new session: %s:%d"%(wallet.host,wallet.port)
        wallet.interface = new_interface(wallet)

