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

import re,sys

from optparse import OptionParser

from wallet import Wallet
from interface import Interface

if __name__ == '__main__':
    known_commands = ['help', 'validateaddress', 'balance', 'contacts', 'create', 'payto', 'sendtx', 'password', 'newaddress', 'addresses', 'history', 'label', 'gui', 'mktx','seed','import']

    usage = "usage: %prog [options] command args\nCommands: "+ (', '.join(known_commands))

    parser = OptionParser(usage=usage)
    parser.add_option("-w", "--wallet", dest="wallet_path", help="wallet path (default: electrum.dat)")
    parser.add_option("-a", "--all", action="store_true", dest="show_all", default=False, help="show all addresses")
    parser.add_option("-b", "--balance", action="store_true", dest="show_balance", default=False, help="show the balance at listed addresses")
    parser.add_option("-k", "--keys",action="store_true", dest="show_keys",default=False, help="show the private keys of listed addresses")
    parser.add_option("-f", "--fee", dest="tx_fee", default="0.005", help="set tx fee")
    options, args = parser.parse_args()
    try:
        cmd = args[0]
    except:
        cmd = "gui"
    try:
        firstarg = args[1]
    except:
        firstarg = ''

    interface = Interface()
    wallet = Wallet(interface)
    wallet.set_path(options.wallet_path)

    if cmd == 'gui' or re.match('^bitcoin:', cmd):
        import gui
        gui.init_wallet(wallet)
        gui = gui.BitcoinGUI(wallet)
        if re.match('^bitcoin:', cmd):
            o = cmd[8:].split('?')
            address = o[0]
            if len(o)>1:
                params = o[1].split('&')
            else:
                params = []
            cmd = 'gui'
            amount = ''
            label = ''
            for p in params:
                k,v = p.split('=')
                v = urldecode(v)
                if k=='amount': amount = v
                elif k=='label': label = v
                else: print k,v
                
            gui.set_send_tab(address, amount, label)

        gui.main()
        wallet.save()
        sys.exit(0)

    if cmd not in known_commands:
        cmd = 'help'

    if not wallet.read() and cmd not in ['help','create']:
        print "Wallet file not found."
        print "Type 'electrum.py create' to create a new wallet, or provide a path to a wallet with the -d option"
        sys.exit(0)
    
    if cmd == 'create':
        if wallet.read():
            print "remove the existing wallet first!"
            sys.exit(0)
        password = getpass.getpass("Password (hit return if you do not wish to encrypt your wallet):")
        if password:
            password2 = getpass.getpass("Confirm password:")
            if password != password2:
                print "error"
                sys.exit(1)
        else:
            password = None

        host = raw_input("server (default:%s):"%wallet.interface.host)
        port = raw_input("port (default:%d):"%wallet.interface.port)
        fee = raw_input("fee (default:%f):"%(wallet.fee*1e-8))
        if fee: wallet.fee = float(fee)
        if host: wallet.interface.host = host
        if port: wallet.interface.port = int(port)
        seed = raw_input("if you are restoring an existing wallet, enter the seed. otherwise just press enter: ")
        wallet.gap_limit = 5
        if seed:
            wallet.seed = seed
            gap = raw_input("gap limit (default 5):")
            if gap: wallet.gap_limit = int(gap)
            print "recovering wallet..."
            wallet.synchronize()
            if wallet.is_found():
                wallet.fill_addressbook()
                wallet.save()
                print "recovery successful"
            else:
                print "no wallet found"
        else:
            wallet.new_seed(None)
            print "Your seed is", wallet.seed
            print "Please store it safely"
            # generate first key
            wallet.synchronize()

    # check syntax
    if cmd in ['payto', 'mktx']:
        try:
            to_address = args[1]
            amount = int( 100000000 * Decimal(args[2]) )
            label = ' '.join(args[3:])
            if options.tx_fee: 
                options.tx_fee = int( 100000000 * Decimal(options.tx_fee) )
        except:
            firstarg = cmd
            cmd = 'help'

    # open session
    if cmd not in ['password', 'mktx', 'history', 'label', 'contacts', 'help', 'validateaddress']:
        wallet.interface.new_session(wallet.all_addresses(), wallet.electrum_version)
        wallet.update()
        wallet.save()

    # commands needing password
    if cmd in ['payto', 'password', 'mktx', 'seed', 'import' ] or ( cmd=='addresses' and options.show_keys):
        password = getpass.getpass('Password:') if wallet.use_encryption else None
        # check password
        try:
            wallet.pw_decode( wallet.seed, password)
        except:
            print "invalid password"
            exit(1)

    if cmd == 'import':
        keypair = args[1]
        if wallet.import_key(keypair,password):
            print "keypair imported"
        else:
            print "error"
        wallet.save()

    if cmd=='help':
        cmd2 = firstarg
        if cmd2 not in known_commands:
            print "known commands:", ', '.join(known_commands)
            print "help <command> shows the help on a specific command"
        elif cmd2 == 'balance':
            print "Display the balance of your wallet or a specific address. The address does not have to be a owned address (you know the private key)."
            print "syntax: balance [<address>]"
        elif cmd2 == 'contacts':
            print "show your list of contacts"
        elif cmd2 == 'payto':
            print "payto <recipient> <amount> [label]"
            print "create and broadcast a transaction."
            print "<recipient> can be a bitcoin address or a label"
        elif cmd2== 'sendtx':
            print "sendtx <tx>"
            print "broadcast a transaction to the network. <tx> must be in hexadecimal"
        elif cmd2 == 'password':
            print "change your password"
        elif cmd2 == 'newaddress':
            print "create a new receiving address. password is needed."
        elif cmd2 == 'addresses':
            print "show your list of addresses. options: -a, -k, -b"
        elif cmd2 == 'history':
            print "show the transaction history"
        elif cmd2 == 'label':
            print "assign a label to an item"
        elif cmd2 == 'gui':
            print "start the GUI"
        elif cmd2 == 'mktx':
            print "create a signed transaction. password protected"
            print "syntax: mktx <recipient> <amount> [label]"
        elif cmd2 == 'seed':
            print "show generation seed of your wallet. password protected."

    elif cmd == 'seed':
        import mnemonic
        seed = wallet.pw_decode( wallet.seed, password)
        print seed, '"'+' '.join(mnemonic.mn_encode(seed))+'"'

    elif cmd == 'validateaddress':
        addr = args[1]
        print wallet.is_valid(addr)

    elif cmd == 'balance':
        try:
            addrs = args[1:]
        except:
            pass
        if addrs == []:
            c, u = wallet.get_balance()
            if u:
                print c*1e-8, u*1e-8
            else:
                print c*1e-8
        else:
            for addr in addrs:
                c, u = wallet.get_addr_balance(addr)
                if u:
                    print "%s %s, %s" % (addr, c*1e-8, u*1e-8)
                else:
                    print "%s %s" % (addr, c*1e-8)

    elif cmd in [ 'contacts']:
        for addr in wallet.addressbook:
            print addr, "   ", wallet.labels.get(addr)

    elif cmd in [ 'addresses']:
        for addr in wallet.all_addresses():
            if options.show_all or not wallet.is_change(addr):
                label = wallet.labels.get(addr)
                _type = ''
                if wallet.is_change(addr): _type = "[change]"
                if addr in wallet.imported_keys.keys(): _type = "[imported]"
                if label is None: label = ''
                if options.show_balance:
                    h = wallet.history.get(addr,[])
                    ni = no = 0
                    for item in h:
                        if item['is_in']:  ni += 1
                        else:              no += 1
                    b = "%d %d %f"%(no, ni, wallet.get_addr_balance(addr)[0]*1e-8)
                else: b=''
                if options.show_keys:
                    pk = wallet.get_private_key2(addr, password)
                    addr = addr + ':' + SecretToASecret(pk)
                print addr, b, _type, label

    if cmd == 'history':
        lines = wallet.get_tx_history()
        b = 0 
        for line in lines:
            import datetime
            v = 1.*line['value']/1e8
            b += v
            v_str = "%f"%v if v<0 else "+%f"%v
            try:
                time_str = datetime.datetime.fromtimestamp( line['nTime']) 
            except:
                print line['nTime']
                time_str = 'pending'
            label = line.get('label')
            if not label: label = line['tx_hash']
            else: label = label + ' '*(64 - len(label) )

            print time_str, " ", label, " ", v_str, " ", "%f"%b
        print "# balance: ", b

    elif cmd == 'label':
        try:
            tx = args[1]
            label = ' '.join(args[2:])
        except:
            print "syntax:  label <tx_hash> <text>"
            sys.exit(1)
        wallet.labels[tx] = label
        wallet.save()
            
    elif cmd in ['payto', 'mktx']:
        for k, v in wallet.labels.items():
            if v == to_address:
                to_address = k
                print "alias", to_address
                break
        try:
            tx = wallet.mktx( to_address, amount, label, password, fee = options.tx_fee )
        except BaseException, e:
            print e
            tx = None

        if tx and cmd=='payto': 
            r, h = wallet.sendtx( tx )
            print h
        else:
            print tx

    elif cmd == 'sendtx':
        tx = args[1]
        r, h = wallet.sendtx( tx )
        print h

    elif cmd == 'newaddress':
        s, a = wallet.get_new_address()
        print a

    elif cmd == 'password':
        try:
            seed = wallet.pw_decode( wallet.seed, password)
        except:
            print "sorry"
            sys.exit(1)
        new_password = getpass.getpass('New password:')
        if new_password == getpass.getpass('Confirm new password:'):
            wallet.use_encryption = (new_password != '')
            wallet.seed = wallet.pw_encode( seed, new_password)
            for k in wallet.imported_keys.keys():
                a = wallet.imported_keys[k]
                b = wallet.pw_decode(a, password)
                c = wallet.pw_encode(b, new_password)
                wallet.imported_keys[k] = c
            wallet.save()
        else:
            print "error: mismatch"

