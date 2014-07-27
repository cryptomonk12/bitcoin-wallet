#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2014 Thomas Voegtlin
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

import socket
import time
import sys
import os
import threading
import traceback
import json
import Queue

import util
from network import Network
from util import print_error, print_stderr, parse_json
from simple_config import SimpleConfig



DAEMON_PORT=8001



class ClientThread(threading.Thread):

    def __init__(self, server, s):
        threading.Thread.__init__(self)
        self.server = server
        self.daemon = True
        self.client_pipe = util.SocketPipe(s)
        self.daemon_pipe = util.QueuePipe(send_queue = self.server.network.requests_queue)
        self.server.add_client(self)

    def reading_thread(self):
        while self.running:
            try:
                request = self.client_pipe.get()
            except util.timeout:
                continue
            if request is None:
                self.running = False
                break

            if request.get('method') == 'daemon.stop':
                self.server.stop()
                continue

            self.daemon_pipe.send(request)

    def run(self):
        self.running = True
        threading.Thread(target=self.reading_thread).start()
        while self.running:
            try:
                response = self.daemon_pipe.get()
            except util.timeout:
                continue
            try:
                self.client_pipe.send(response)
            except socket.error:
                self.running = False
                break
        self.server.remove_client(self)





class NetworkServer:

    def __init__(self, config):
        self.config = config
        self.network = Network(config)
        # network sends responses on that queue
        self.network_queue = Queue.Queue()
        self.network.start(self.network_queue)

        self.running = False
        # daemon terminates after period of inactivity
        self.timeout = config.get('daemon_timeout', 5*60)
        self.lock = threading.RLock()

        # each GUI is a client of the daemon
        self.clients = []
        # todo: the daemon needs to know which client subscribed to which address

    def is_running(self):
        with self.lock:
            return self.running

    def stop(self):
        self.network.stop()
        with self.lock:
            self.running = False

    def add_client(self, client):
        for key in ['status','banner','updated','servers','interfaces']:
            value = self.network.get_status_value(key)
            client.daemon_pipe.get_queue.put({'method':'network.status', 'params':[key, value]})
        with self.lock:
            self.clients.append(client)


    def remove_client(self, client):
        with self.lock:
            self.clients.remove(client)
        print_error("client quit:", len(self.clients))



    def main_loop(self):
        self.running = True
        threading.Thread(target=self.listen_thread).start()
        while self.is_running():
            try:
                response = self.network_queue.get(timeout=0.1)
            except Queue.Empty:
                continue
            for client in self.clients:
                client.daemon_pipe.get_queue.put(response)

        print_error("Daemon exiting")

    def listen_thread(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.daemon_port = self.config.get('daemon_port', DAEMON_PORT)
        self.socket.bind(('', self.daemon_port))
        self.socket.listen(5)
        self.socket.settimeout(1)
        t = time.time()
        while self.running:
            try:
                connection, address = self.socket.accept()
            except socket.timeout:
                if not self.clients:
                    if time.time() - t > self.timeout:
                        print_error("Daemon timeout")
                        break
                else:
                    t = time.time()
                continue
            t = time.time()
            client = ClientThread(self, connection)
            client.start()
        self.stop()
        print_error("listen thread exiting")


if __name__ == '__main__':
    import simple_config, util
    config = simple_config.SimpleConfig()
    util.set_verbosity(True)
    server = NetworkServer(config)
    try:
        server.main_loop()
    except KeyboardInterrupt:
        print "Ctrl C - Stopping server"
        sys.exit(1)
