from PyQt4.Qt import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QThread, SIGNAL
import PyQt4.QtCore as QtCore
from binascii import unhexlify
from binascii import hexlify
from struct import pack,unpack
from sys import stderr
from time import sleep
from base64 import b64encode, b64decode

from electrum_gui.qt.password_dialog import make_password_dialog, run_password_dialog
from electrum_gui.qt.util import ok_cancel_buttons
from electrum.account import BIP32_Account
from electrum.bitcoin import EC_KEY, EncodeBase58Check, DecodeBase58Check, public_key_to_bc_address, bc_address_to_hash_160
from electrum.i18n import _
from electrum.plugins import BasePlugin
from electrum.transaction import deserialize
from electrum.wallet import NewWallet

from lib.util import format_satoshis
import hashlib

try:
    from usb.core import USBError
    from btchip.btchipComm import getDongle, DongleWait
    from btchip.btchip import btchip
    from btchip.btchipUtils import compress_public_key,format_transaction, get_regular_input_script
    from btchip.bitcoinTransaction import bitcoinTransaction
    BTCHIP = True
except ImportError:
    BTCHIP = False

def log(msg):
    stderr.write("%s\n" % msg)
    stderr.flush()

def give_error(message):
    QMessageBox.warning(QDialog(), _('Warning'), _(message), _('OK'))
    raise Exception(message)

class Plugin(BasePlugin):

    def fullname(self): return 'BTChip Wallet'

    def description(self): return 'Provides support for BTChip hardware wallet\n\nRequires github.com/btchip/btchip-python'

    def __init__(self, gui, name):
        BasePlugin.__init__(self, gui, name)
        self._is_available = self._init()
        self.wallet = None

    def _init(self):
        return BTCHIP

    def is_available(self):
        #if self.wallet is None:
        #    return self._is_available
        #if self.wallet.storage.get('wallet_type') == 'btchip':
        #    return True
        #return False
        return self._is_available

    def set_enabled(self, enabled):
        self.wallet.storage.put('use_' + self.name, enabled)

    def is_enabled(self):
        if not self.is_available():
            return False

        if not self.wallet or self.wallet.storage.get('wallet_type') == 'btchip':
            return True

        return self.wallet.storage.get('use_' + self.name) is True

    def enable(self):
        return BasePlugin.enable(self)

    def load_wallet(self, wallet):
        self.wallet = wallet

    def add_wallet_types(self, wallet_types):
        wallet_types.append(('btchip', _("BTChip wallet"), BTChipWallet))

    def installwizard_restore(self, wizard, storage):
        wallet = BTChipWallet(storage)
        try:
            wallet.create_main_account(None)
        except BaseException as e:
            QMessageBox.information(None, _('Error'), str(e), _('OK'))
            return
        return wallet

    def send_tx(self, tx):
        try:
            self.wallet.sign_transaction(tx, None, None)
        except Exception as e:
            tx.error = str(e)


class BTChipWallet(NewWallet):
    wallet_type = 'btchip'

    def __init__(self, storage):
        NewWallet.__init__(self, storage)
        self.transport = None
        self.client = None
        self.mpk = None
        self.device_checked = False

    def get_action(self):
        if not self.accounts:
            return 'create_accounts'

    def can_create_accounts(self):
        return True

    def can_change_password(self):
        return False

    def has_seed(self):
        return False

    def is_watching_only(self):
        return False

    def get_client(self, noPin=False):
        if not BTCHIP:
            give_error('please install github.com/btchip/btchip-python')

        aborted = False
        if not self.client or self.client.bad:
            try:
                d = getDongle(True)
                d.setWaitImpl(DongleWaitQT(d))
                self.client = btchip(d)
                firmware = self.client.getFirmwareVersion()['version'].split(".")
                if int(firmware[0]) <> 1 or int(firmware[1]) <> 4:
                    aborted = True
                    give_error("Unsupported firmware version")
                if int(firmware[2]) < 8:
                    aborted = True
                    give_error("Please update your firmware - 1.4.8 or higher is necessary")
                if not noPin:
                    # Immediately prompts for the PIN
                    confirmed, p, pin = self.password_dialog("Enter your BTChip PIN")                
                    if not confirmed:
                        aborted = True
                        give_error('Aborted by user')
                    pin = pin.encode()                    
                    self.client.verifyPin(pin)
            except Exception, e:
                if not aborted:
                    give_error("Could not connect to your BTChip dongle. Please verify access permissions or PIN")
                else:
                    raise e
            self.client.bad = False
            self.device_checked = False
            self.proper_device = False
        return self.client

    def address_id(self, address):
        account_id, (change, address_index) = self.get_address_index(address)
        # FIXME review
        return "44'/0'/%s'/%d/%d" % (account_id, change, address_index)

    def create_main_account(self, password):
        self.create_account('Main account', None) #name, empty password

    def derive_xkeys(self, root, derivation, password):
        # FIXME review
        derivation = derivation.replace(self.root_name,"44'/0'/")
        xpub = self.get_public_key(derivation)
        return xpub, None

    def get_public_key(self, bip32_path):
        # S-L-O-W - we don't handle the fingerprint directly, so compute it manually from the previous node        
        # This only happens once so it's bearable
        self.get_client() # prompt for the PIN before displaying the dialog if necessary        
        waitDialog.start("Computing master public key")
        try:            
            splitPath = bip32_path.split('/')
            fingerprint = 0        
            if len(splitPath) > 1:
                prevPath = "/".join(splitPath[0:len(splitPath) - 1])
                nodeData = self.get_client().getWalletPublicKey(prevPath)
                publicKey = compress_public_key(nodeData['publicKey'])
                h = hashlib.new('ripemd160')
                h.update(hashlib.sha256(publicKey).digest())
                fingerprint = unpack(">I", h.digest()[0:4])[0]            
            nodeData = self.get_client().getWalletPublicKey(bip32_path)
            publicKey = compress_public_key(nodeData['publicKey'])
            depth = len(splitPath)
            lastChild = splitPath[len(splitPath) - 1].split('\'')
            if len(lastChild) == 1:
                childnum = int(lastChild[0])
            else:
                childnum = 0x80000000 | int(lastChild[0])        
            xpub = "0488B21E".decode('hex') + chr(depth) + self.i4b(fingerprint) + self.i4b(childnum) + str(nodeData['chainCode']) + str(publicKey)
        except Exception, e:
            give_error(e)
        finally:
            waitDialog.emit(SIGNAL('dongle_done'))

        return EncodeBase58Check(xpub)

    def get_master_public_key(self):
        if not self.mpk:
            self.mpk = self.get_public_key("44'/0'")
        return self.mpk

    def i4b(self, x):
        return pack('>I', x)

    def add_keypairs(self, tx, keypairs, password):
        #do nothing - no priv keys available
        pass

    def decrypt_message(self, pubkey, message, password):
        give_error("Not supported")

    def sign_message(self, address, message, password):
        address_path = self.address_id(address)
        waitDialog.start("Signing Message ...")
        aborted = False
        try:
            info = self.get_client().signMessagePrepare(address_path, message)
            pin = ""
            if info['confirmationNeeded']:                
                # TODO : handle different confirmation types. For the time being only supports keyboard 2FA
                confirmed, p, pin = self.password_dialog()
                if not confirmed:
                    aborted = True
                    give_error('Aborted by user')
                pin = pin.encode()
                self.client.bad = True
                self.get_client(True)
            signature = self.get_client().signMessageSign(pin)
        except Exception, e:
            if not aborted:
                give_error(e)
            else:
                raise e
        finally:
            if waitDialog.waiting:
                waitDialog.emit(SIGNAL('dongle_done'))

        # Parse the ASN.1 signature

        rLength = signature[3]
        r = signature[4 : 4 + rLength]
        sLength = signature[4 + rLength + 1]
        s = signature[4 + rLength + 2:]
        if rLength == 33:
            r = r[1:]
        if sLength == 33:
            s = s[1:]
        r = str(r)
        s = str(s)

        # And convert it

        for i in range(4):
            sig = b64encode( chr(27 + i + 4) + r + s)
            try:
                EC_KEY.verify_message(address, sig, message)
                return sig
            except Exception:
                continue
        else:
            raise Exception("error: cannot sign message")

    def choose_tx_inputs( self, amount, fixed_fee, num_outputs, domain = None, coins = None ):
        # Overloaded to get the fee, as BTChip recomputes the change amount
        inputs, total, fee = super(BTChipWallet, self).choose_tx_inputs(amount, fixed_fee, num_outputs, domain, coins)
        self.lastFee = fee
        return inputs, total, fee

    def sign_transaction(self, tx, keypairs, password):
        if tx.error or tx.is_complete():
            return        
        inputs = []
        inputsPaths = []
        pubKeys = []
        trustedInputs = []
        redeemScripts = []        
        signatures = []
        preparedTrustedInputs = []
        changePath = "" 
        changeAmount = None
        output = None
        outputAmount = None
        use2FA = False
        aborted = False
        # Fetch inputs of the transaction to sign
        for txinput in tx.inputs:
            if ('is_coinbase' in txinput and txinput['is_coinbase']):
                give_error("Coinbase not supported")     # should never happen
            inputs.append([ self.transactions[txinput['prevout_hash']].raw, 
                             txinput['prevout_n'] ])        
            address = txinput['address']
            inputsPaths.append(self.address_id(address))
            pubKeys.append(self.get_public_keys(address))

        # Recognize outputs - only one output and one change is authorized
        if len(tx.outputs) > 2: # should never happen
            give_error("Transaction with more than 2 outputs not supported")
        for type, address, amount in tx.outputs:        
            assert type == 'address'
            if self.is_change(address):
                changePath = self.address_id(address)
                changeAmount = amount
            else:
                if output <> None: # should never happen
                    give_error("Multiple outputs with no change not supported")
                output = address
                outputAmount = amount

        self.get_client() # prompt for the PIN before displaying the dialog if necessary
        if not self.check_proper_device():
            give_error('Wrong device or password')

        waitDialog.start("Signing Transaction ...")
        try:
            # Get trusted inputs from the original transactions
            for utxo in inputs:
                txtmp = bitcoinTransaction(bytearray(utxo[0].decode('hex')))            
                trustedInputs.append(self.get_client().getTrustedInput(txtmp, utxo[1]))
                # TODO : Support P2SH later
                redeemScripts.append(txtmp.outputs[utxo[1]].script)
            # Sign all inputs
            firstTransaction = True
            inputIndex = 0
            while inputIndex < len(inputs):
                self.get_client().startUntrustedTransaction(firstTransaction, inputIndex, 
                trustedInputs, redeemScripts[inputIndex])
                outputData = self.get_client().finalizeInput(output, format_satoshis(outputAmount), 
                format_satoshis(self.lastFee), changePath)
                if firstTransaction:
                    transactionOutput = outputData['outputData']
                if outputData['confirmationNeeded']:                
                    use2FA = True
                    # TODO : handle different confirmation types. For the time being only supports keyboard 2FA
                    waitDialog.emit(SIGNAL('dongle_done'))
                    confirmed, p, pin = self.password_dialog()
                    if not confirmed:
                        aborted = True
                        give_error('Aborted by user')
                    pin = pin.encode()
                    self.client.bad = True
                    self.get_client(True)
                    waitDialog.start("Signing ...")
                else:
                    # Sign input with the provided PIN
                    signatures.append(self.get_client().untrustedHashSign(inputsPaths[inputIndex],
                    pin))
                    inputIndex = inputIndex + 1
                firstTransaction = False
        except Exception, e:
            if not aborted:
                give_error(e)
            else:
                raise e
        finally:
            if waitDialog.waiting:
                waitDialog.emit(SIGNAL('dongle_done'))

        # Reformat transaction
        inputIndex = 0
        while inputIndex < len(inputs):
            # TODO : Support P2SH later
            inputScript = get_regular_input_script(signatures[inputIndex], pubKeys[inputIndex][0].decode('hex'))        
            preparedTrustedInputs.append([ trustedInputs[inputIndex]['value'], inputScript ])
            inputIndex = inputIndex + 1
        updatedTransaction = format_transaction(transactionOutput, preparedTrustedInputs)
        updatedTransaction = hexlify(updatedTransaction)
        tx.update(updatedTransaction)
        self.client.bad = use2FA

    def check_proper_device(self):
        pubKey = DecodeBase58Check(self.master_public_keys["x/0'"])[45:]
        if not self.device_checked:
            waitDialog.start("Checking device")
            try:
                nodeData = self.get_client().getWalletPublicKey("44'/0'/0'")
            except Exception, e:
                give_error(e)
            finally:
                waitDialog.emit(SIGNAL('dongle_done'))
            pubKeyDevice = compress_public_key(nodeData['publicKey'])
            self.device_checked = True
            if pubKey != pubKeyDevice:
                self.proper_device = False
            else:
                self.proper_device = True

        return self.proper_device

    def password_dialog(self, msg=None):
        if not msg:
            msg = _("Disconnect your BTChip, read the unique second factor PIN, reconnect it and enter the unique second factor PIN")

        d = QDialog()
        d.setModal(1)
        d.setLayout( make_password_dialog(d, None, msg, False) )
        return run_password_dialog(d, None, None)

class DongleWaitingDialog(QThread):
    def __init__(self):
        QThread.__init__(self)
        self.waiting = False

    def start(self, message):
        self.d = QDialog()
        self.d.setModal(1)
        self.d.setWindowTitle('Please Wait')
        self.d.setWindowFlags(self.d.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        l = QLabel(message)
        vbox = QVBoxLayout(self.d)
        vbox.addWidget(l)
        self.d.show()
        if not self.waiting:
            self.waiting = True
            self.d.connect(waitDialog, SIGNAL('dongle_done'), self.stop)

    def stop(self):
        self.d.hide()
        self.waiting = False

if BTCHIP:
    waitDialog = DongleWaitingDialog()

# Tickle the UI a bit while waiting
class DongleWaitQT(DongleWait):
    def __init__(self, dongle):
        self.dongle = dongle

    def waitFirstResponse(self, timeout):
        customTimeout = 0
        while customTimeout < timeout:
            try:
                response = self.dongle.waitFirstResponse(200)
                return response
            except USBError, e:
                if e.backend_error_code == -7:
                    QApplication.processEvents()
                    customTimeout = customTimeout + 100
                    pass
                else:
                    raise e
        raise e
