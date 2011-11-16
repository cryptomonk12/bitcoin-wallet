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


import sys, base64, os, re, hashlib, socket, getpass, copy, operator, ast

try:
    import ecdsa  
except:
    print "python-ecdsa does not seem to be installed. Try 'sudo easy_install ecdsa'"
    sys.exit(1)

try:
    import Crypto
    has_encryption = True
except:
    has_encryption = False


############ functions from pywallet ##################### 

addrtype = 0

def hash_160(public_key):
    md = hashlib.new('ripemd160')
    md.update(hashlib.sha256(public_key).digest())
    return md.digest()

def public_key_to_bc_address(public_key):
    h160 = hash_160(public_key)
    return hash_160_to_bc_address(h160)

def hash_160_to_bc_address(h160):
    vh160 = chr(addrtype) + h160
    h = Hash(vh160)
    addr = vh160 + h[0:4]
    return b58encode(addr)

def bc_address_to_hash_160(addr):
    bytes = b58decode(addr, 25)
    return bytes[1:21]

__b58chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
__b58base = len(__b58chars)

def b58encode(v):
    """ encode v, which is a string of bytes, to base58.		
    """

    long_value = 0L
    for (i, c) in enumerate(v[::-1]):
        long_value += (256**i) * ord(c)

    result = ''
    while long_value >= __b58base:
        div, mod = divmod(long_value, __b58base)
        result = __b58chars[mod] + result
        long_value = div
    result = __b58chars[long_value] + result

    # Bitcoin does a little leading-zero-compression:
    # leading 0-bytes in the input become leading-1s
    nPad = 0
    for c in v:
        if c == '\0': nPad += 1
        else: break

    return (__b58chars[0]*nPad) + result

def b58decode(v, length):
    """ decode v into a string of len bytes
    """
    long_value = 0L
    for (i, c) in enumerate(v[::-1]):
        long_value += __b58chars.find(c) * (__b58base**i)

    result = ''
    while long_value >= 256:
        div, mod = divmod(long_value, 256)
        result = chr(mod) + result
        long_value = div
    result = chr(long_value) + result

    nPad = 0
    for c in v:
        if c == __b58chars[0]: nPad += 1
        else: break

    result = chr(0)*nPad + result
    if length is not None and len(result) != length:
        return None

    return result


def Hash(data):
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def EncodeBase58Check(vchIn):
    hash = Hash(vchIn)
    return b58encode(vchIn + hash[0:4])

def DecodeBase58Check(psz):
    vchRet = b58decode(psz, None)
    key = vchRet[0:-4]
    csum = vchRet[-4:]
    hash = Hash(key)
    cs32 = hash[0:4]
    if cs32 != csum:
        return None
    else:
        return key

def PrivKeyToSecret(privkey):
    return privkey[9:9+32]

def SecretToASecret(secret):
    vchIn = chr(addrtype+128) + secret
    return EncodeBase58Check(vchIn)

def ASecretToSecret(key):
    vch = DecodeBase58Check(key)
    if vch and vch[0] == chr(addrtype+128):
        return vch[1:]
    else:
        return False

########### end pywallet functions #######################


def int_to_hex(i, length=1):
    s = hex(i)[2:].rstrip('L')
    s = "0"*(2*length - len(s)) + s
    return s.decode('hex')[::-1].encode('hex')


# password encryption
from Crypto.Cipher import AES
BLOCK_SIZE = 32
PADDING = '{'
pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * PADDING
EncodeAES = lambda c, s: base64.b64encode(c.encrypt(pad(s)))
DecodeAES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(PADDING)


# secp256k1, http://www.oid-info.com/get/1.3.132.0.10
_p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2FL
_r = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141L
_b = 0x0000000000000000000000000000000000000000000000000000000000000007L
_a = 0x0000000000000000000000000000000000000000000000000000000000000000L
_Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798L
_Gy = 0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8L
curve_secp256k1 = ecdsa.ellipticcurve.CurveFp( _p, _a, _b )
generator_secp256k1 = ecdsa.ellipticcurve.Point( curve_secp256k1, _Gx, _Gy, _r )
oid_secp256k1 = (1,3,132,0,10)
SECP256k1 = ecdsa.curves.Curve("SECP256k1", curve_secp256k1, generator_secp256k1, oid_secp256k1 ) 


def filter(s): 
    out = re.sub('( [^\n]*|)\n','',s)
    out = out.replace(' ','')
    out = out.replace('\n','')
    return out

def raw_tx( inputs, outputs, for_sig = None ):
    s  = int_to_hex(1,4)                                     +   '     version\n' 
    s += int_to_hex( len(inputs) )                           +   '     number of inputs\n'
    for i in range(len(inputs)):
        _, _, p_hash, p_index, p_script, pubkey, sig = inputs[i]
        s += p_hash.decode('hex')[::-1].encode('hex')        +  '     prev hash\n'
        s += int_to_hex(p_index,4)                           +  '     prev index\n'
        if for_sig is None:
            sig = sig + chr(1)                               # hashtype
            script  = int_to_hex( len(sig))                  +  '     push %d bytes\n'%len(sig)
            script += sig.encode('hex')                      +  '     sig\n'
            pubkey = chr(4) + pubkey
            script += int_to_hex( len(pubkey))               +  '     push %d bytes\n'%len(pubkey)
            script += pubkey.encode('hex')                   +  '     pubkey\n'
        elif for_sig==i:
            script = p_script                                +  '     scriptsig \n'
        else:
            script=''
        s += int_to_hex( len(filter(script))/2 )             +  '     script length \n'
        s += script
        s += "ffffffff"                                      +  '     sequence\n'
    s += int_to_hex( len(outputs) )                          +  '     number of outputs\n'
    for output in outputs:
        addr, amount = output
        s += int_to_hex( amount, 8)                          +  '     amount: %d\n'%amount 
        script = '76a9'                                      # op_dup, op_hash_160
        script += '14'                                       # push 0x14 bytes
        script += bc_address_to_hash_160(addr).encode('hex')
        script += '88ac'                                     # op_equalverify, op_checksig
        s += int_to_hex( len(filter(script))/2 )             +  '     script length \n'
        s += script                                          +  '     script \n'
    s += int_to_hex(0,4)                                     # lock time
    if for_sig is not None: s += int_to_hex(1, 4)            # hash type
    return s

class InvalidPassword(Exception):
    pass



class Wallet:
    def __init__(self, wallet_dir):

        self.gap_limit = 5           # configuration
        self.host = 'ecdsa.org'
        self.port = 50000
        self.fee = 0.005
        self.version = 1

        # saved fields
        self.use_encryption = False
        self.addresses = []
        self.seed = ''               # encrypted
        self.private_keys = repr([]) # encrypted
        self.change_addresses = []   # index of addresses used as change
        self.status = {}             # current status of addresses
        self.history = {}
        self.labels = {}             # labels for addresses and transactions
        self.addressbook = []        # outgoing addresses, for payments
        self.blocks = 0 

        # not saved
        self.message = ''
        self.tx_history = {}
        self.rtime = 0

        self.init_path(wallet_dir)


    def init_path(self, wallet_dir):
        if wallet_dir is None:
            if "HOME" in os.environ:
                wallet_dir = os.path.join( os.environ["HOME"], '.electrum')
            elif "LOCALAPPDATA" in os.environ:
                wallet_dir = os.path.join( os.environ["LOCALAPPDATA"], 'Electrum' )
            elif "APPDATA" in os.environ:
                wallet_dir = os.path.join( os.environ["APPDATA"],  'Electrum' )
            else:
                print "No home directory found in environment variables."
                raise

        if not os.path.exists( wallet_dir ):
            os.mkdir( wallet_dir ) 

        self.path = os.path.join( wallet_dir, 'electrum.dat')

    def new_seed(self, password):
        seed = "%032x"%ecdsa.util.randrange( pow(2,128) )
        self.seed = wallet.pw_encode( seed, password)

    def is_mine(self, address):
        return address in self.addresses

    def is_change(self, address):
        if not self.is_mine(address): 
            return False
        k = self.addresses.index(address)
        return k in self.change_addresses

    def is_valid(self,addr):
        ADDRESS_RE = re.compile('[1-9A-HJ-NP-Za-km-z]{26,}\\Z')
        return ADDRESS_RE.match(addr)

    def create_new_address(self, for_change, password):
        seed = self.pw_decode( self.seed, password)
        # strenghtening
        for i in range(100000):
            oldseed = seed
            seed = hashlib.sha512(seed + oldseed).digest()
        i = len( self.addresses ) - len(self.change_addresses) if not for_change else len(self.change_addresses)
        seed = Hash( "%d:%d:"%(i,for_change) + seed )
        order = generator_secp256k1.order()
        secexp = ecdsa.util.randrange_from_seed__trytryagain( seed, order )
        secret = SecretToASecret( ('%064x' % secexp).decode('hex') )
        private_key = ecdsa.SigningKey.from_secret_exponent( secexp, curve = SECP256k1 )
        public_key = private_key.get_verifying_key()
        address = public_key_to_bc_address( '04'.decode('hex') + public_key.to_string() )
        try:
            private_keys = ast.literal_eval( self.pw_decode( self.private_keys, password) )
            private_keys.append(secret)
        except:
            raise InvalidPassword("")
        self.private_keys = self.pw_encode( repr(private_keys), password)
        self.addresses.append(address)
        if for_change: self.change_addresses.append( len(self.addresses) - 1 )
        self.history[address] = []
        self.status[address] = None
        self.save()
        return address


    def recover(self, password):
        seed = self.pw_decode( self.seed, password)
        # todo: recover receiving addresses from tx
        is_found = False
        while True:
            addr = self.create_new_address(True, password)
            self.history[addr] = h = self.retrieve_history(addr)
            self.status[addr] = h[-1]['blk_hash'] if h else None
            #print "recovering", addr
            if self.status[addr] is not None: 
                is_found = True
            else:
                break

        num_gap = 0
        while True:
            addr = self.create_new_address(False, password)
            self.history[addr] = h = self.retrieve_history(addr)
            self.status[addr] = h[-1]['blk_hash'] if h else None
            #print "recovering", addr
            if self.status[addr] is None:
                num_gap += 1
                if num_gap == self.gap_limit: break
            else:
                is_found = True
                num_gap = 0

        if not is_found: return False

        # remove limit-1 addresses. [ this is ok, because change addresses are at the beginning of the list]
        n = self.gap_limit
        self.addresses = self.addresses[:-n]
        private_keys = ast.literal_eval( self.pw_decode( self.private_keys, password))
        private_keys = private_keys[:-n]
        self.private_keys = self.pw_encode( repr(private_keys), password)

        # history and addressbook
        self.update_tx_history()
        for tx in self.tx_history.values():
            if tx['value']<0:
                for i in tx['outputs']:
                    if not self.is_mine(i) and i not in self.addressbook:
                        self.addressbook.append(i)
        # redo labels
        self.update_tx_labels()
        return True

    def save(self):
        s = repr( (self.version, self.use_encryption, self.fee, self.host, self.port, self.blocks,
                   self.seed, self.addresses, self.private_keys, 
                   self.change_addresses, self.status, self.history, 
                   self.labels, self.addressbook) )
        f = open(self.path,"w")
        f.write(s)
        f.close()

    def read(self):
        try:
            f = open(self.path,"r")
            data = f.read()
            f.close()
        except:
            return False
        try:
            sequence = ast.literal_eval( data )
            (self.version, self.use_encryption, self.fee, self.host, self.port, self.blocks, 
             self.seed, self.addresses, self.private_keys, 
             self.change_addresses, self.status, self.history, 
             self.labels, self.addressbook) = sequence
        except:
            raise BaseException("version error.")
        self.update_tx_history()
        return True
        
    def get_new_address(self, password):
        n = 0 
        for addr in self.addresses[-self.gap_limit:]:
            if self.history[addr] == []: 
                n = n + 1
        if n < self.gap_limit:
            try:
                new_address = self.create_new_address(False, password)
            except InvalidPassword:
                return False, "wrong password"
            self.save()
            return True, new_address
        else:
            return False, "The last %d addresses in your list have never been used. You should use them first, or increase the allowed gap size in your preferences. "%self.gap_limit

    def get_addr_balance(self, addr):
        h = self.history.get(addr)
        c = u = 0
        for item in h:
            v = item['value']
            if item['height']:
                c += v
            else:
                u += v
        return c, u

    def get_balance(self):
        conf = unconf = 0
        for addr in self.addresses: 
            c, u = self.get_addr_balance(addr)
            conf += c
            unconf += u
        return conf, unconf

    def use_http(self): 
        return self.port in [80,8080,443]

    def request(self, request ):
        import time
        t1 = time.time()

        if self.use_http():
            import httplib, urllib
            params = urllib.urlencode({'q':request})
            headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
            conn = httplib.HTTPConnection(self.host)
            conn.request("POST", "/electrum.php", params, headers)
            response = conn.getresponse()
            if response.status == 200:
                out = response.read()
            else: out = ''
            conn.close()
        else:
            request += "#"
            s = socket.socket( socket.AF_INET, socket.SOCK_STREAM)
            s.connect(( self.host, self.port))
            s.send( request )
            out = ''
            while 1:
                msg = s.recv(1024)
                if msg: out += msg
                else: break
            s.close()

        self.rtime = time.time() - t1
        return out

    def retrieve_message(self):
        if not self.message:
            self.message = self.request( repr ( ('msg', '')))

    def send_tx(self, data):
        return self.request( repr ( ('tx', data )))

    def retrieve_history(self, address):
        return ast.literal_eval( self.request( repr ( ('h', address ))) )

    def poll(self):
        return ast.literal_eval( self.request( repr ( ('poll', self.session_id ))))

    def new_session(self):
        self.session_id, self.message = ast.literal_eval( self.request( repr ( ('session', repr(self.addresses) ))))
        
    def update(self):
        blocks, changed_addresses = self.poll()
        if blocks == -1: raise BaseException("session not found")
        self.blocks = int(blocks)
        for addr, blk_hash in changed_addresses.items():
            if self.status[addr] != blk_hash:
                print "updating history for", addr
                self.history[addr] = self.retrieve_history(addr)
                self.status[addr] = blk_hash
        self.update_tx_history()
        if changed_addresses:
            return True
        else:
            return False

    def choose_inputs_outputs( self, to_addr, amount, fee, password):
        """ todo: minimize tx size """

        amount = int( 1e8*amount )
        fee = int( 1e8*fee )
        total = 0 
        inputs = []
        for addr in self.addresses:
            h = self.history.get(addr)
            for item in h:
                if item.get('raw_scriptPubKey'):
                    v = item.get('value')
                    total += v
                    inputs.append((addr, v, item['tx_hash'], item['pos'], item['raw_scriptPubKey'], None, None) )
                    if total >= amount + fee: break
            if total >= amount + fee: break
        else:
            print "not enough funds: %d %d"%(total, fee)
            return False, "not enough funds: %d %d"%(total, fee)
        outputs = [ (to_addr, amount) ]
        change_amount = total - ( amount + fee )
        if change_amount != 0:
            # first look for unused change addresses 
            for addr in self.addresses:
                i = self.addresses.index(addr)
                if i not in self.change_addresses: continue
                if self.history.get(addr): continue
                change_address = addr
                break
            else:
                change_address = self.create_new_address(True, password)
                print "new change address", change_address
            outputs.append( (change_address,  change_amount) )
        return inputs, outputs

    def sign_inputs( self, inputs, outputs, password ):
        s_inputs = []
        for i in range(len(inputs)):
            addr, v, p_hash, p_pos, p_scriptPubKey, _, _ = inputs[i]
            private_key = self.get_private_key(addr, password)
            public_key = private_key.get_verifying_key()
            pubkey = public_key.to_string()
            tx = filter( raw_tx( inputs, outputs, for_sig = i ) )
            sig = private_key.sign_digest( Hash( tx.decode('hex') ), sigencode = ecdsa.util.sigencode_der )
            assert public_key.verify_digest( sig, Hash( tx.decode('hex') ), sigdecode = ecdsa.util.sigdecode_der)
            s_inputs.append( (addr, v, p_hash, p_pos, p_scriptPubKey, pubkey, sig) )
        return s_inputs

    def pw_encode(self, s, password):
        if password:
            secret = Hash(password)
            cipher = AES.new(secret)
            return EncodeAES(cipher, s)
        else:
            return s

    def pw_decode(self, s, password):
        if password:
            secret = Hash(password)
            cipher = AES.new(secret)
            return DecodeAES(cipher, s)
        else:
            return s

    def get_private_key( self, addr, password ):
        try:
            private_keys = ast.literal_eval( self.pw_decode( self.private_keys, password ) )
        except:
            raise InvalidPassword("")
        k = self.addresses.index(addr)
        secret = private_keys[k]
        b = ASecretToSecret(secret)
        secexp = int( b.encode('hex'), 16)
        private_key = ecdsa.SigningKey.from_secret_exponent( secexp, curve=SECP256k1 )
        public_key = private_key.get_verifying_key()
        assert addr == public_key_to_bc_address( chr(4) + public_key.to_string() )
        return private_key

    def get_tx_history(self):
        lines = self.tx_history.values()
        lines = sorted(lines, key=operator.itemgetter("nTime"))
        return lines

    def update_tx_history(self):
        self.tx_history= {}
        for addr in self.addresses:
            for tx in self.history[addr]:
                tx_hash = tx['tx_hash']
                line = self.tx_history.get(tx_hash)
                if not line:
                    self.tx_history[tx_hash] = copy.copy(tx)
                    line = self.tx_history.get(tx_hash)
                else:
                    line['value'] += tx['value']
                if line['blk_hash'] == 'mempool':
                    line['nTime'] = 1e12
        self.update_tx_labels()

    def update_tx_labels(self):
        for tx in self.tx_history.values():
            default_label = ''
            if tx['value']<0:
                for o_addr in tx['outputs']:
                    if not self.is_change(o_addr):
                        dest_label = self.labels.get(o_addr)
                        if dest_label:
                            default_label = 'to: ' + dest_label
                        else:
                            default_label = 'to: ' + o_addr
            else:
                for o_addr in tx['outputs']:
                    if self.is_mine(o_addr) and not self.is_change(o_addr):
                        dest_label = self.labels.get(o_addr)
                        if dest_label:
                            default_label = 'at: ' + dest_label
                        else:
                            default_label = 'at: ' + o_addr
            tx['default_label'] = default_label

    def mktx(self, to_address, amount, label, password, fee=None):
        if fee is None: fee = self.fee
        try:
            inputs, outputs = wallet.choose_inputs_outputs( to_address, amount, fee, password )
            if not inputs:
                return False, "Not enough funds"
            s_inputs = wallet.sign_inputs( inputs, outputs, password )
        except InvalidPassword:
            return False, "Wrong password"
        tx = filter( raw_tx( s_inputs, outputs ) )
        return True, tx

    def sendtx(self, tx):
        tx_hash = Hash(tx.decode('hex') )[::-1].encode('hex')
        out = self.send_tx(tx)
        if out != tx_hash:
            return False, "error: " + out
        if to_address not in self.addressbook:
            self.addressbook.append(to_address)
        if label: 
            wallet.labels[tx_hash] = label
        wallet.save()
        return True, out


    



from optparse import OptionParser

if __name__ == '__main__':
    known_commands = ['help', 'balance', 'contacts', 'create', 'payto', 'sendtx', 'password', 'newaddress', 'addresses', 'history', 'label', 'gui', 'mktx','seed']

    usage = "usage: %prog [options] command args\nCommands: "+ (', '.join(known_commands))

    parser = OptionParser(usage=usage)
    parser.add_option("-d", "--dir", dest="wallet_dir", help="wallet directory")
    parser.add_option("-a", "--all", action="store_true", dest="show_all", default=False, help="show all addresses")
    parser.add_option("-b", "--balance", action="store_true", dest="show_balance", default=False, help="show the balance at listed addresses")
    parser.add_option("-k", "--keys",action="store_true", dest="show_keys",default=False, help="show the private keys of listed addresses")
    parser.add_option("-f", "--fee", dest="tx_fee", default=0.005, help="set tx fee")
    options, args = parser.parse_args()
    try:
        cmd = args[0]
    except:
        cmd = "gui"
    try:
        firstarg = args[1]
    except:
        firstarg = ''

    if cmd not in known_commands:
        cmd = 'help'

    wallet = Wallet(options.wallet_dir)

    if cmd == 'gui':
        import gui
        gui.init_wallet(wallet)
        gui = gui.BitcoinGUI(wallet)
        gui.main()
        wallet.save()
        sys.exit(0)

    if not wallet.read() and cmd != 'help':
        print "Wallet file not found."
        print "Type 'electrum.py create' to create a new wallet, or provide a path to a wallet with the -d option"
        sys.exit(0)
    
    if cmd == 'create':
        if wallet.read():
            print "remove the existing wallet first!"
            sys.exit(0)
        if has_encryption:
            password = getpass.getpass("Password (hit return if you do not wish to encrypt your wallet):")
            if password:
                password2 = getpass.getpass("Confirm password:")
                if password != password2:
                    print "error"
                    sys.exit(1)
        else:
            password = None
            print "in order to use wallet encryption, please install pycrypto  (sudo easy_install pycrypto)"

        host = raw_input("server (default:ecdsa.org):")
        port = raw_input("port (default:50000):")
        fee = raw_input("fee (default 0.005):")
        if fee: wallet.fee = float(fee)
        if host: wallet.host = host
        if port: wallet.port = int(port)
        seed = raw_input("if you are restoring an existing wallet, enter the seed. otherwise just press enter: ")
        wallet.gap_limit = 5
        if seed:
            wallet.seed = seed
            gap = raw_input("gap limit (default 5):")
            if gap: wallet.gap_limit = int(gap)
            print "recovering wallet..."
            r = wallet.recover(password)
            if r:
                print "recovery successful"
                wallet.save()
            else:
                print "no wallet found"
        else:
            wallet.new_seed(None)
            print "Your seed is", wallet.seed
            print "Please store it safely"
            # generate first key
            wallet.create_new_address(False, None)

    # check syntax
    if cmd in ['payto', 'mktx']:
        try:
            to_address = args[1]
            amount = float(args[2])
            label = ' '.join(args[3:])
            if options.tx_fee: options.tx_fee = float(options.tx_fee)
        except:
            firstarg = cmd
            cmd = 'help'

    # open session
    if cmd not in ['password', 'mktx', 'history', 'label','contacts','help']:
        wallet.new_session()
        wallet.update()
        wallet.save()

    # commands needing password
    if cmd in ['payto', 'password', 'newaddress','mktx','seed'] or ( cmd=='addresses' and options.show_keys):
        password = getpass.getpass('Password:') if wallet.use_encryption else None

    if cmd=='help':
        cmd2 = firstarg
        if cmd2 not in known_commands:
            print "known commands:", ', '.join(known_commands)
            print "help <command> shows the help on a specific command"
        elif cmd2 == 'balance':
            print "display the balance of your wallet"
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
        print wallet.seed, '"'+' '.join(mnemonic.mn_encode(wallet.seed))+'"'

    elif cmd == 'balance':
        c, u = wallet.get_balance()
        if u:
            print c*1e-8, u*1e-8
        else:
            print c*1e-8

    elif cmd in [ 'contacts']:
        for addr in wallet.addressbook:
            print addr, "   ", wallet.labels.get(addr)

    elif cmd in [ 'addresses']:
        if options.show_keys: private_keys = ast.literal_eval( wallet.pw_decode( wallet.private_keys, password ) )
        for addr in wallet.addresses:
            if options.show_all or not wallet.is_change(addr):
                label = wallet.labels.get(addr) if not wallet.is_change(addr) else "[change]"
                if label is None: label = ''
                if options.show_balance:
                    h = wallet.history.get(addr)
                    ni = no = 0
                    for item in h:
                        if item['is_in']:  ni += 1
                        else:              no += 1
                    b = "%d %d %f"%(no, ni, wallet.get_addr_balance(addr)[0]*1e-8)
                else: b=''
                pk = private_keys[wallet.addresses.index(addr)] if options.show_keys else ''
                print addr, pk, b, label

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
                break
            print "alias", to_address
        r, h = wallet.mktx( to_address, amount, label, password, fee = options.tx_fee )
        if r and cmd=='payto': 
            r, h = wallet.sendtx( tx )
            print h
        else:
            print h 

    elif cmd=='sendtx':
        tx = args[1]
        r, h = wallet.sendtx( tx )
        print h

    elif cmd == 'newaddress':
        a = wallet.get_new_address()
        if a: 
            print a
        else:
            print "Maximum gap reached. Increase gap in order to create more addresses."

    elif cmd == 'password':
        try:
            seed = wallet.pw_decode( wallet.seed, password)
            private_keys = ast.literal_eval( wallet.pw_decode( wallet.private_keys, password) )
        except:
            print "sorry"
            sys.exit(1)
        new_password = getpass.getpass('New password:')
        if new_password == getpass.getpass('Confirm new password:'):
            wallet.use_encryption = (new_password != '')
            wallet.seed = wallet.pw_encode( seed, new_password)
            wallet.private_keys = wallet.pw_encode( repr( private_keys ), new_password)
            wallet.save()
        else:
            print "error: mismatch"

