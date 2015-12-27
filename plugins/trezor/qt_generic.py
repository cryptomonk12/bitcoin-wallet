from functools import partial
from unicodedata import normalize
import threading

from PyQt4.Qt import QGridLayout, QInputDialog, QPushButton
from PyQt4.Qt import QVBoxLayout, QLabel, SIGNAL
from trezor import TrezorPlugin
from electrum_gui.qt.main_window import ElectrumWindow, StatusBarButton
from electrum_gui.qt.password_dialog import PasswordDialog
from electrum_gui.qt.util import *

from electrum.i18n import _
from electrum.plugins import hook
from electrum.util import PrintError


class QtHandler(PrintError):
    '''An interface between the GUI (here, QT) and the device handling
    logic for handling I/O.  This is a generic implementation of the
    Trezor protocol; derived classes can customize it.'''

    def __init__(self, win, pin_matrix_widget_class, device):
        win.connect(win, SIGNAL('message_done'), self.dialog_stop)
        win.connect(win, SIGNAL('message_dialog'), self.message_dialog)
        win.connect(win, SIGNAL('pin_dialog'), self.pin_dialog)
        win.connect(win, SIGNAL('passphrase_dialog'), self.passphrase_dialog)
        self.win = win
        self.windows = [win]
        self.pin_matrix_widget_class = pin_matrix_widget_class
        self.device = device
        self.done = threading.Event()
        self.dialog = None

    def stop(self):
        self.win.emit(SIGNAL('message_done'))

    def show_message(self, msg, cancel_callback=None):
        self.win.emit(SIGNAL('message_dialog'), msg, cancel_callback)

    def get_pin(self, msg):
        self.done.clear()
        self.win.emit(SIGNAL('pin_dialog'), msg)
        self.done.wait()
        return self.response

    def get_passphrase(self, msg):
        self.done.clear()
        self.win.emit(SIGNAL('passphrase_dialog'), msg)
        self.done.wait()
        return self.passphrase

    def pin_dialog(self, msg):
        # Needed e.g. when renaming label and haven't entered PIN
        self.dialog_stop()
        d = WindowModalDialog(self.windows[-1], _("Enter PIN"))
        matrix = self.pin_matrix_widget_class()
        vbox = QVBoxLayout()
        vbox.addWidget(QLabel(msg))
        vbox.addWidget(matrix)
        vbox.addLayout(Buttons(CancelButton(d), OkButton(d)))
        d.setLayout(vbox)
        if not d.exec_():
            self.response = None  # FIXME: this is lost?
        self.response = str(matrix.get_value())
        self.done.set()

    def passphrase_dialog(self, msg):
        self.dialog_stop()
        d = PasswordDialog(self.windows[-1], None, None, msg, False)
        confirmed, p, phrase = d.run()
        if confirmed:
            phrase = normalize('NFKD', unicode(phrase or ''))
        self.passphrase = phrase
        self.done.set()

    def message_dialog(self, msg, cancel_callback):
        # Called more than once during signing, to confirm output and fee
        self.dialog_stop()
        title = _('Please check your %s device') % self.device
        dialog = self.dialog = WindowModalDialog(self.windows[-1], title)
        l = QLabel(msg)
        vbox = QVBoxLayout(dialog)
        if cancel_callback:
            vbox.addLayout(Buttons(CancelButton(dialog)))
            dialog.connect(dialog, SIGNAL('rejected()'), cancel_callback)
        vbox.addWidget(l)
        dialog.show()

    def dialog_stop(self):
        if self.dialog:
            self.dialog.hide()
            self.dialog = None

    def pop_window(self):
        self.windows.pop()

    def push_window(self, window):
        self.windows.append(window)


class QtPlugin(TrezorPlugin):
    # Derived classes must provide the following class-static variables:
    #   icon_file
    #   pin_matrix_widget_class

    def create_handler(self, window):
        return QtHandler(window, self.pin_matrix_widget_class, self.device)

    @hook
    def load_wallet(self, wallet, window):
        self.print_error("load_wallet")
        self.wallet = wallet
        self.wallet.plugin = self
        self.button = StatusBarButton(QIcon(self.icon_file), self.device,
                                      partial(self.settings_dialog, window))
        if type(window) is ElectrumWindow:
            window.statusBar().addPermanentWidget(self.button)
        if self.handler is None:
            self.handler = self.create_handler(window)
        msg = self.wallet.sanity_check()
        if msg:
            window.show_error(msg)

    @hook
    def installwizard_load_wallet(self, wallet, window):
        if type(wallet) != self.wallet_class:
            return
        self.load_wallet(wallet, window)

    @hook
    def installwizard_restore(self, wizard, storage):
        if storage.get('wallet_type') != self.wallet_class.wallet_type:
            return
        seed = wizard.enter_seed_dialog(_("Enter your %s seed") % self.device,
                                        None, func=lambda x: True)
        if not seed:
            return
        wallet = self.wallet_class(storage)
        self.wallet = wallet
        handler = self.create_handler(wizard)
        msg = "\n".join([_("Please enter your %s passphrase.") % self.device,
                         _("Press OK if you do not use one.")])
        passphrase = handler.get_passphrase(msg)
        if passphrase is None:
            return
        password = wizard.password_dialog()
        wallet.add_seed(seed, password)
        wallet.add_cosigner_seed(seed, 'x/', password, passphrase)
        wallet.create_main_account(password)
        # disable plugin as this is a free-standing wallet
        self.set_enabled(False)
        return wallet

    @hook
    def receive_menu(self, menu, addrs):
        if (not self.wallet.is_watching_only() and
                self.atleast_version(1, 3) and len(addrs) == 1):
            menu.addAction(_("Show on %s") % self.device,
                           lambda: self.show_address(addrs[0]))

    def show_address(self, address):
        self.wallet.check_proper_device()
        try:
            address_path = self.wallet.address_id(address)
            address_n = self.get_client().expand_path(address_path)
        except Exception, e:
            self.give_error(e)
        try:
            self.get_client().get_address('Bitcoin', address_n, True)
        except Exception, e:
            self.give_error(e)
        finally:
            self.handler.stop()

    def settings_dialog(self, window):

        def rename():
            title = _("Set Device Label")
            msg = _("Enter new label:")
            response = QInputDialog().getText(dialog, title, msg)
            if not response[1]:
                return
            new_label = str(response[0])
            try:
                client.change_label(new_label)
            finally:
                self.handler.stop()
            device_label.setText(new_label)

        def update_pin_info():
            features = client.features
            pin_label.setText(noyes[features.pin_protection])
            pin_button.setText(_("Change") if features.pin_protection
                               else _("Set"))
            clear_pin_button.setVisible(features.pin_protection)

        def set_pin(remove):
            try:
                client.set_pin(remove=remove)
            finally:
                self.handler.stop()
            update_pin_info()

        client = self.get_client()
        features = client.features
        noyes = [_("No"), _("Yes")]
        bl_hash = features.bootloader_hash.encode('hex').upper()
        bl_hash = "%s...%s" % (bl_hash[:10], bl_hash[-10:])
        info_tab = QWidget()
        layout = QGridLayout(info_tab)
        device_label = QLabel(features.label)
        rename_button = QPushButton(_("Rename"))
        rename_button.clicked.connect(rename)
        pin_label = QLabel()
        pin_button = QPushButton()
        pin_button.clicked.connect(partial(set_pin, False))
        clear_pin_button = QPushButton(_("Clear"))
        clear_pin_button.clicked.connect(partial(set_pin, True))
        update_pin_info()

        version = "%d.%d.%d" % (features.major_version,
                                features.minor_version,
                                features.patch_version)
        rows = [
            (_("Bootloader Hash"), bl_hash),
            (_("Device ID"), features.device_id),
            (_("Device Label"), device_label, rename_button),
            (_("Firmware Version"), version),
            (_("Language"), features.language),
            (_("Has Passphrase"), noyes[features.passphrase_protection]),
            (_("Has PIN"), pin_label, pin_button, clear_pin_button)
        ]

        for row_num, items in enumerate(rows):
            for col_num, item in enumerate(items):
                widget = item if isinstance(item, QWidget) else QLabel(item)
                layout.addWidget(widget, row_num, col_num)

        dialog = WindowModalDialog(None, _("%s Settings") % self.device)
        vbox = QVBoxLayout()
        tabs = QTabWidget()
        tabs.addTab(info_tab, _("Information"))
        tabs.addTab(QWidget(), _("Advanced"))
        vbox.addWidget(tabs)
        vbox.addStretch(1)
        vbox.addLayout(Buttons(CloseButton(dialog)))

        dialog.setLayout(vbox)
        self.handler.push_window(dialog)
        try:
            dialog.exec_()
        finally:
            self.handler.pop_window()
