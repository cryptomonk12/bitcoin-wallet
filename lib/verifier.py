#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2012 thomasv@ecdsa.org
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


import threading
import Queue


import util
from bitcoin import *


class SPV(util.DaemonThread):
    """ Simple Payment Verification """

    def __init__(self, network, wallet):
        util.DaemonThread.__init__(self)
        self.wallet = wallet
        self.network = network
        self.merkle_roots    = {}                                  # hashed by me
        self.queue = Queue.Queue()

    def run(self):
        requested_merkle = []
        while self.is_running():
            verified_tx, unverified_tx = self.wallet.get_transactions()
            # request missing tx
            for tx_hash, tx_height in unverified_tx.items():
                if tx_hash not in verified_tx:
                    # do not request merkle branch before headers are available
                    if tx_height > self.network.get_local_height():
                        continue
                    if self.merkle_roots.get(tx_hash) is None and tx_hash not in requested_merkle:
                        if self.network.send([ ('blockchain.transaction.get_merkle',[tx_hash, tx_height]) ], self.queue.put):
                            self.print_error('requesting merkle', tx_hash)
                            requested_merkle.append(tx_hash)
            try:
                r = self.queue.get(timeout=0.1)
            except Queue.Empty:
                continue
            if not r:
                continue

            if r.get('error'):
                self.print_error('Verifier received an error:', r)
                continue

            # 3. handle response
            method = r['method']
            params = r['params']
            result = r['result']

            if method == 'blockchain.transaction.get_merkle':
                tx_hash = params[0]
                self.verify_merkle(tx_hash, result)

        self.print_error("stopped")


    def verify_merkle(self, tx_hash, result):
        tx_height = result.get('block_height')
        pos = result.get('pos')
        merkle_root = self.hash_merkle_root(result['merkle'], tx_hash, pos)
        header = self.network.get_header(tx_height)
        if not header: return
        if header.get('merkle_root') != merkle_root:
            self.print_error("merkle verification failed for", tx_hash)
            return

        # we passed all the tests
        self.merkle_roots[tx_hash] = merkle_root
        self.print_error("verified %s" % tx_hash)
        self.wallet.add_verified_tx(tx_hash, (tx_height, header.get('timestamp'), pos))


    def hash_merkle_root(self, merkle_s, target_hash, pos):
        h = hash_decode(target_hash)
        for i in range(len(merkle_s)):
            item = merkle_s[i]
            h = Hash( hash_decode(item) + h ) if ((pos >> i) & 1) else Hash( h + hash_decode(item) )
        return hash_encode(h)


    def undo_verifications(self, height):
        verified_tx, unverified_tx = self.wallet.get_transactions()
        txs = []
        for tx_hash, item in verified_tx:
            tx_height, timestamp, pos = item
            if tx_height >= height:
                self.print_error("redoing", tx_hash)
                txs.append(tx_hash)
                self.merkle_roots.pop(tx_hash, None)
        self.wallet.unverify_txs(txs)
