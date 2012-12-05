import sys

# Let's do some dep checking and handle missing ones gracefully
try:
    from PyQt4.QtCore import *
    from PyQt4.QtGui import *
    import PyQt4.QtCore as QtCore

except ImportError:
    print "You need to have PyQT installed to run Electrum in graphical mode."
    print "If you have pip installed try 'sudo pip install pyqt' if you are on Debian/Ubuntu try 'sudo apt-get install python-qt4'."
    sys.exit(0)




from decimal import Decimal as D
from interface import DEFAULT_SERVERS
from util import get_resource_path as rsrc
from i18n import _
import decimal
import exchange_rate
import os.path
import random
import re
import time
import wallet
import webbrowser
import history_widget
import util

import gui_qt
import shutil

bitcoin = lambda v: v * 100000000

def IconButton(filename, parent=None):
    pixmap = QPixmap(filename)
    icon = QIcon(pixmap)
    return QPushButton(icon, "", parent)

class Timer(QThread):
    def run(self):
        while True:
            self.emit(SIGNAL('timersignal'))
            time.sleep(0.5)

def resize_line_edit_width(line_edit, text_input):
    metrics = QFontMetrics(qApp.font())
    # Create an extra character to add some space on the end
    text_input += "A"
    line_edit.setMinimumWidth(metrics.width(text_input))

def load_theme_name(theme_path):
    try:
        with open(os.path.join(theme_path, "name.cfg")) as name_cfg_file:
            return name_cfg_file.read().rstrip("\n").strip()
    except IOError:
        return None


def theme_dirs_from_prefix(prefix):
    if not os.path.exists(prefix):
        return []
    theme_paths = {}
    for potential_theme in os.listdir(prefix):
        theme_full_path = os.path.join(prefix, potential_theme)
        theme_css = os.path.join(theme_full_path, "style.css")
        if not os.path.exists(theme_css):
            continue
        theme_name = load_theme_name(theme_full_path)
        if theme_name is None:
            continue
        theme_paths[theme_name] = prefix, potential_theme
    return theme_paths

def load_theme_paths():
    theme_paths = {}
    prefixes = (util.local_data_dir(), util.appdata_dir())
    for prefix in prefixes:
        theme_paths.update(theme_dirs_from_prefix(prefix))
    return theme_paths


class ElectrumGui(QObject):

    def __init__(self, wallet, config):
        super(QObject, self).__init__()

        self.wallet = wallet
        self.config = config
        self.check_qt_version()
        self.app = QApplication(sys.argv)
        self.wallet.interface.register_callback('peers', self.server_list_changed)


    def check_qt_version(self):
        qtVersion = qVersion()
        if not(int(qtVersion[0]) >= 4 and int(qtVersion[2]) >= 7):
            app = QApplication(sys.argv)
            QMessageBox.warning(None,"Could not start Lite GUI.", "Electrum was unable to load the 'Lite GUI' because it needs Qt version >= 4.7.\nChanging your config to use the 'Classic' GUI")
            self.config.set_key('gui','classic',True)
            sys.exit(0)


    def main(self, url):
        actuator = MiniActuator(self.wallet)
        self.connect(self, SIGNAL("updateservers()"),
                     actuator.update_servers_list)
        # Should probably not modify the current path but instead
        # change the behaviour of rsrc(...)
        old_path = QDir.currentPath()
        actuator.load_theme()

        self.mini = MiniWindow(actuator, self.expand, self.config)
        driver = MiniDriver(self.wallet, self.mini)

        # Reset path back to original value now that loading the GUI
        # is completed.
        QDir.setCurrent(old_path)

        if url:
            self.set_url(url)

        timer = Timer()
        timer.start()
        self.expert = gui_qt.ElectrumWindow(self.wallet, self.config)
        self.expert.app = self.app
        self.expert.connect_slots(timer)
        self.expert.update_wallet()
        self.app.exec_()

    def server_list_changed(self):
        self.emit(SIGNAL("updateservers()"))

    def expand(self):
        """Hide the lite mode window and show pro-mode."""
        self.mini.hide()
        self.expert.show()

    def set_url(self, url):
        payto, amount, label, message, signature, identity, url = \
            self.wallet.parse_url(url, self.show_message, self.show_question)
        self.mini.set_payment_fields(payto, amount)

    def show_message(self, message):
        QMessageBox.information(self.mini, _("Message"), message, _("OK"))

    def show_question(self, message):
        choice = QMessageBox.question(self.mini, _("Message"), message,
                                      QMessageBox.Yes|QMessageBox.No,
                                      QMessageBox.No)
        return choice == QMessageBox.Yes

    def restore_or_create(self):
        qt_gui_object = gui_qt.ElectrumGui(self.wallet, self.app)
        return qt_gui_object.restore_or_create()

class MiniWindow(QDialog):

    def __init__(self, actuator, expand_callback, config):
        super(MiniWindow, self).__init__()

        self.actuator = actuator
        self.config = config

        self.btc_balance = None
        self.quote_currencies = ["EUR", "USD", "GBP"]
        self.actuator.set_configured_currency(self.set_quote_currency)
        self.exchanger = exchange_rate.Exchanger(self)
        # Needed because price discovery is done in a different thread
        # which needs to be sent back to this main one to update the GUI
        self.connect(self, SIGNAL("refresh_balance()"), self.refresh_balance)

        self.balance_label = BalanceLabel(self.change_quote_currency)
        self.balance_label.setObjectName("balance_label")

        self.receive_button = QPushButton(_("&Receive"))
        self.receive_button.setObjectName("receive_button")
        self.receive_button.setDefault(True)
        self.receive_button.clicked.connect(self.copy_address)

        # Bitcoin address code
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText(_("Enter a Bitcoin address..."))
        self.address_input.setObjectName("address_input")


        self.address_input.textEdited.connect(self.address_field_changed)
        resize_line_edit_width(self.address_input,
                               "1BtaFUr3qVvAmwrsuDuu5zk6e4s2rxd2Gy")

        self.address_completions = QStringListModel()
        address_completer = QCompleter(self.address_input)
        address_completer.setCaseSensitivity(False)
        address_completer.setModel(self.address_completions)
        self.address_input.setCompleter(address_completer)

        address_layout = QHBoxLayout()
        address_layout.addWidget(self.address_input)

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText(_("... and amount"))
        self.amount_input.setObjectName("amount_input")
        # This is changed according to the user's displayed balance
        self.amount_validator = QDoubleValidator(self.amount_input)
        self.amount_validator.setNotation(QDoubleValidator.StandardNotation)
        self.amount_validator.setDecimals(8)
        self.amount_input.setValidator(self.amount_validator)

        # This removes the very ugly OSX highlighting, please leave this in :D
        self.address_input.setAttribute(Qt.WA_MacShowFocusRect, 0)
        self.amount_input.setAttribute(Qt.WA_MacShowFocusRect, 0)
        self.amount_input.textChanged.connect(self.amount_input_changed)

        self.send_button = QPushButton(_("&Send"))
        self.send_button.setObjectName("send_button")
        self.send_button.setDisabled(True);
        self.send_button.clicked.connect(self.send)

        main_layout = QGridLayout(self)

        main_layout.addWidget(self.balance_label, 0, 0)
        main_layout.addWidget(self.receive_button, 0, 1)

        main_layout.addWidget(self.address_input, 1, 0, 1, -1)

        main_layout.addWidget(self.amount_input, 2, 0)
        main_layout.addWidget(self.send_button, 2, 1)

        self.history_list = history_widget.HistoryWidget()
        self.history_list.setObjectName("history")
        self.history_list.hide()
        self.history_list.setAlternatingRowColors(True)
        main_layout.addWidget(self.history_list, 3, 0, 1, -1)

        menubar = QMenuBar()
        electrum_menu = menubar.addMenu(_("&Bitcoin"))

        servers_menu = electrum_menu.addMenu(_("&Servers"))
        servers_group = QActionGroup(self)
        self.actuator.set_servers_gui_stuff(servers_menu, servers_group)
        self.actuator.populate_servers_menu()
        electrum_menu.addSeparator()

        brain_seed = electrum_menu.addAction(_("&BrainWallet Info"))
        brain_seed.triggered.connect(self.actuator.show_seed_dialog)
        quit_option = electrum_menu.addAction(_("&Quit"))
        quit_option.triggered.connect(self.close)

        view_menu = menubar.addMenu(_("&View"))
        extra_menu = menubar.addMenu(_("&Extra"))

        backup_wallet = extra_menu.addAction( _("&Create wallet backup"))
        backup_wallet.triggered.connect(self.backup_wallet)

        expert_gui = view_menu.addAction(_("&Classic GUI"))
        expert_gui.triggered.connect(expand_callback)
        themes_menu = view_menu.addMenu(_("&Themes"))
        selected_theme = self.actuator.selected_theme()
        theme_group = QActionGroup(self)
        for theme_name in self.actuator.theme_names():
            theme_action = themes_menu.addAction(theme_name)
            theme_action.setCheckable(True)
            if selected_theme == theme_name:
                theme_action.setChecked(True)
            class SelectThemeFunctor:
                def __init__(self, theme_name, toggle_theme):
                    self.theme_name = theme_name
                    self.toggle_theme = toggle_theme
                def __call__(self, checked):
                    if checked:
                        self.toggle_theme(self.theme_name)
            delegate = SelectThemeFunctor(theme_name, self.toggle_theme)
            theme_action.toggled.connect(delegate)
            theme_group.addAction(theme_action)
        view_menu.addSeparator()
        show_history = view_menu.addAction(_("Show History"))
        show_history.setCheckable(True)
        show_history.toggled.connect(self.show_history)

        help_menu = menubar.addMenu(_("&Help"))
        the_website = help_menu.addAction(_("&Website"))
        the_website.triggered.connect(self.the_website)
        help_menu.addSeparator()
        report_bug = help_menu.addAction(_("&Report Bug"))
        report_bug.triggered.connect(self.show_report_bug)
        show_about = help_menu.addAction(_("&About"))
        show_about.triggered.connect(self.show_about)
        main_layout.setMenuBar(menubar)

        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.close)
        close_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        close_shortcut.activated.connect(self.close)

        g = self.config.get("winpos-lite",[4, 25, 351, 149])
        self.setGeometry(g[0], g[1], g[2], g[3])

        show_hist = self.config.get("gui_show_history",False)
        show_history.setChecked(show_hist)
        self.show_history(show_hist)
        
        self.setWindowIcon(QIcon(":electrum.png"))
        self.setWindowTitle("Electrum")
        self.setWindowFlags(Qt.Window|Qt.MSWindowsFixedSizeDialogHint)
        self.layout().setSizeConstraint(QLayout.SetFixedSize)
        self.setObjectName("main_window")
        self.show()

    def toggle_theme(self, theme_name):
        old_path = QDir.currentPath()
        self.actuator.change_theme(theme_name)
        # Recompute style globally
        qApp.style().unpolish(self)
        qApp.style().polish(self)
        QDir.setCurrent(old_path)

    def closeEvent(self, event):
        g = self.geometry()
        self.config.set_key("winpos-lite", [g.left(),g.top(),g.width(),g.height()],True)
        self.config.set_key("gui_show_history", self.history_list.isVisible(),True)
        
        super(MiniWindow, self).closeEvent(event)
        qApp.quit()

    def set_payment_fields(self, dest_address, amount):
        self.address_input.setText(dest_address)
        self.address_field_changed(dest_address)
        self.amount_input.setText(amount)

    def activate(self):
        pass

    def deactivate(self):
        pass

    def set_quote_currency(self, currency):
        """Set and display the fiat currency country."""
        assert currency in self.quote_currencies
        self.quote_currencies.remove(currency)
        self.quote_currencies.insert(0, currency)
        self.refresh_balance()

    def change_quote_currency(self):
        self.quote_currencies = \
            self.quote_currencies[1:] + self.quote_currencies[0:1]
        self.actuator.set_config_currency(self.quote_currencies[0])
        self.refresh_balance()

    def refresh_balance(self):
        if self.btc_balance is None:
            # Price has been discovered before wallet has been loaded
            # and server connect... so bail.
            return
        self.set_balances(self.btc_balance)
        self.amount_input_changed(self.amount_input.text())

    def set_balances(self, btc_balance):
        """Set the bitcoin balance and update the amount label accordingly."""
        self.btc_balance = btc_balance
        quote_text = self.create_quote_text(btc_balance)
        if quote_text:
            quote_text = "(%s)" % quote_text
        btc_balance = "%.2f" % (btc_balance / bitcoin(1))
        self.balance_label.set_balance_text(btc_balance, quote_text)
        self.setWindowTitle("Electrum - %s BTC" % btc_balance)

    def amount_input_changed(self, amount_text):
        """Update the number of bitcoins displayed."""
        self.check_button_status()

        try:
            amount = D(str(amount_text))
        except decimal.InvalidOperation:
            self.balance_label.show_balance()
        else:
            quote_text = self.create_quote_text(amount * bitcoin(1))
            if quote_text:
                self.balance_label.set_amount_text(quote_text)
                self.balance_label.show_amount()
            else:
                self.balance_label.show_balance()

    def create_quote_text(self, btc_balance):
        """Return a string copy of the amount fiat currency the 
        user has in bitcoins."""
        quote_currency = self.quote_currencies[0]
        quote_balance = self.exchanger.exchange(btc_balance, quote_currency)
        if quote_balance is None:
            quote_text = ""
        else:
            quote_text = "%.2f %s" % ((quote_balance / bitcoin(1)),
                                      quote_currency)
        return quote_text

    def send(self):
        if self.actuator.send(self.address_input.text(),
                              self.amount_input.text(), self):
            self.address_input.setText("")
            self.amount_input.setText("")

    def check_button_status(self):
        """Check that the bitcoin address is valid and that something
        is entered in the amount before making the send button clickable."""
        try:
            value = D(str(self.amount_input.text())) * 10**8
        except decimal.InvalidOperation:
            value = None
        # self.address_input.property(...) returns a qVariant, not a bool.
        # The == is needed to properly invoke a comparison.
        if (self.address_input.property("isValid") == True and
            value is not None and 0 < value <= self.btc_balance):
            self.send_button.setDisabled(False)
        else:
            self.send_button.setDisabled(True)

    def address_field_changed(self, address):
        if self.actuator.is_valid(address):
            self.check_button_status()
            self.address_input.setProperty("isValid", True)
            self.recompute_style(self.address_input)
        else:
            self.send_button.setDisabled(True)
            self.address_input.setProperty("isValid", False)
            self.recompute_style(self.address_input)

        if len(address) == 0:
            self.address_input.setProperty("isValid", None)
            self.recompute_style(self.address_input)

    def recompute_style(self, element):
        self.style().unpolish(element)
        self.style().polish(element)

    def copy_address(self):
        receive_popup = ReceivePopup(self.receive_button)
        self.actuator.copy_address(receive_popup)

    def update_completions(self, completions):
        self.address_completions.setStringList(completions)

    def update_history(self, tx_history):
        from util import format_satoshis
        for item in tx_history[-10:]:
            tx_hash, conf, is_mine, value, fee, balance, timestamp = item
            label = self.actuator.wallet.get_label(tx_hash)[0]
            #amount = D(value) / 10**8
            v_str = format_satoshis(value, True)
            self.history_list.append(label, v_str)

    def acceptbit(self):
        self.actuator.acceptbit(self.quote_currencies[0])

    def the_website(self):
        webbrowser.open("http://electrum-desktop.com")

    def show_about(self):
        QMessageBox.about(self, "Electrum",
            _("Electrum's focus is speed, with low resource usage and simplifying Bitcoin. You do not need to perform regular backups, because your wallet can be recovered from a secret phrase that you can memorize or write on paper. Startup times are instant because it operates in conjuction with high-performance servers that handle the most complicated parts of the Bitcoin system.\n\nSend donations to 1JwTMv4GWaPdf931N6LNPJeZBfZgZJ3zX1"))

    def show_report_bug(self):
        QMessageBox.information(self, "Electrum - " + _("Reporting Bugs"),
            _("Email bug reports to %s") % "genjix" + "@" + "riseup.net")

    def show_history(self, toggle_state):
        if toggle_state:
            self.history_list.show()
        else:
            self.history_list.hide()

    def backup_wallet(self):
        try:
          folderName = QFileDialog.getExistingDirectory(QWidget(), 'Select folder to save a copy of your wallet to', os.path.expanduser('~/'))
          if folderName:
            sourceFile = util.user_dir() + '/electrum.dat'
            shutil.copy2(sourceFile, str(folderName))
            QMessageBox.information(None,"Wallet backup created", "A copy of your wallet file was created in '%s'" % str(folderName))
        except (IOError, os.error), reason:
          QMessageBox.critical(None,"Unable to create backup", "Electrum was unable copy your wallet file to the specified location.\n" + str(reason))




class BalanceLabel(QLabel):

    SHOW_CONNECTING = 1
    SHOW_BALANCE = 2
    SHOW_AMOUNT = 3

    def __init__(self, change_quote_currency, parent=None):
        super(QLabel, self).__init__(_("Connecting..."), parent)
        self.change_quote_currency = change_quote_currency
        self.state = self.SHOW_CONNECTING
        self.balance_text = ""
        self.amount_text = ""

    def mousePressEvent(self, event):
        """Change the fiat currency selection if window background is clicked."""
        if self.state != self.SHOW_CONNECTING:
            self.change_quote_currency()

    def set_balance_text(self, btc_balance, quote_text):
        """Set the amount of bitcoins in the gui."""
        if self.state == self.SHOW_CONNECTING:
            self.state = self.SHOW_BALANCE
        self.balance_text = "<span style='font-size: 18pt'>%s</span> <span style='font-size: 10pt'>BTC</span> <span style='font-size: 10pt'>%s</span>" % (btc_balance, quote_text)
        if self.state == self.SHOW_BALANCE:
            self.setText(self.balance_text)

    def set_amount_text(self, quote_text):
        self.amount_text = "<span style='font-size: 10pt'>%s</span>" % quote_text
        if self.state == self.SHOW_AMOUNT:
            self.setText(self.amount_text)

    def show_balance(self):
        if self.state == self.SHOW_AMOUNT:
            self.state = self.SHOW_BALANCE
            self.setText(self.balance_text)

    def show_amount(self):
        if self.state == self.SHOW_BALANCE:
            self.state = self.SHOW_AMOUNT
            self.setText(self.amount_text)

def ok_cancel_buttons(dialog):
    row_layout = QHBoxLayout()
    row_layout.addStretch(1)
    ok_button = QPushButton(_("OK"))
    row_layout.addWidget(ok_button)
    ok_button.clicked.connect(dialog.accept)
    cancel_button = QPushButton(_("Cancel"))
    row_layout.addWidget(cancel_button)
    cancel_button.clicked.connect(dialog.reject)
    return row_layout

class PasswordDialog(QDialog):

    def __init__(self, parent):
        super(QDialog, self).__init__(parent)

        self.setModal(True)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        main_layout = QVBoxLayout(self)
        message = _('Please enter your password')
        main_layout.addWidget(QLabel(message))

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(QLabel(_('Password')), 1, 0)
        grid.addWidget(self.password_input, 1, 1)
        main_layout.addLayout(grid)

        main_layout.addLayout(ok_cancel_buttons(self))
        self.setLayout(main_layout) 

    def run(self):
        if not self.exec_():
            return
        return unicode(self.password_input.text())

class ReceivePopup(QDialog):

    def leaveEvent(self, event):
        self.close()

    def setup(self, address):
        label = QLabel(_("Copied your Bitcoin address to the clipboard!"))
        address_display = QLineEdit(address)
        address_display.setReadOnly(True)
        resize_line_edit_width(address_display, address)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(label)
        main_layout.addWidget(address_display)

        self.setMouseTracking(True)
        self.setWindowTitle("Electrum - " + _("Receive Bitcoin payment"))
        self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint|
                            Qt.MSWindowsFixedSizeDialogHint)
        self.layout().setSizeConstraint(QLayout.SetFixedSize)
        #self.setFrameStyle(QFrame.WinPanel|QFrame.Raised)
        #self.setAlignment(Qt.AlignCenter)

    def popup(self):
        parent = self.parent()
        top_left_pos = parent.mapToGlobal(parent.rect().bottomLeft())
        self.move(top_left_pos)
        center_mouse_pos = self.mapToGlobal(self.rect().center())
        QCursor.setPos(center_mouse_pos)
        self.show()

class MiniActuator:
    """Initialize the definitions relating to themes and 
    sending/recieving bitcoins."""
    
    
    def __init__(self, wallet):
        """Retrieve the gui theme used in previous session."""
        self.wallet = wallet
        self.theme_name = self.wallet.config.get('litegui_theme','Cleanlook')
        self.themes = load_theme_paths()

    def load_theme(self):
        """Load theme retrieved from wallet file."""
        try:
            theme_prefix, theme_path = self.themes[self.theme_name]
        except KeyError:
            util.print_error("Theme not found!", self.theme_name)
            return
        QDir.setCurrent(os.path.join(theme_prefix, theme_path))
        with open(rsrc("style.css")) as style_file:
            qApp.setStyleSheet(style_file.read())

    def theme_names(self):
        """Sort themes."""
        return sorted(self.themes.keys())
    
    def selected_theme(self):
        """Select theme."""
        return self.theme_name

    def change_theme(self, theme_name):
        """Change theme."""
        self.theme_name = theme_name
        self.wallet.config.set_key('litegui_theme',theme_name)
        self.load_theme()
    
    def set_configured_currency(self, set_quote_currency):
        """Set the inital fiat currency conversion country (USD/EUR/GBP) in 
        the GUI to what it was set to in the wallet."""
        currency = self.wallet.config.get('conversion_currency')
        # currency can be none when Electrum is used for the first
        # time and no setting has been created yet.
        if currency is not None:
            set_quote_currency(currency)

    def set_config_currency(self, conversion_currency):
        """Change the wallet fiat currency country."""
        self.wallet.config.set_key('conversion_currency',conversion_currency,True)

    def set_servers_gui_stuff(self, servers_menu, servers_group):
        self.servers_menu = servers_menu
        self.servers_group = servers_group

    def populate_servers_menu(self):
        interface = self.wallet.interface
        if not interface.servers:
            print "No servers loaded yet."
            self.servers_list = []
            for server_string in DEFAULT_SERVERS:
                host, port, protocol = server_string.split(':')
                transports = [(protocol,port)]
                self.servers_list.append((host, transports))
        else:
            print "Servers loaded."
            self.servers_list = interface.servers
        server_names = [details[0] for details in self.servers_list]
        current_server = interface.server.split(":")[0]
        for server_name in server_names:
            server_action = self.servers_menu.addAction(server_name)
            server_action.setCheckable(True)
            if server_name == current_server:
                server_action.setChecked(True)
            class SelectServerFunctor:
                def __init__(self, server_name, server_selected):
                    self.server_name = server_name
                    self.server_selected = server_selected
                def __call__(self, checked):
                    if checked:
                        # call server_selected
                        self.server_selected(self.server_name)
            delegate = SelectServerFunctor(server_name, self.server_selected)
            server_action.toggled.connect(delegate)
            self.servers_group.addAction(server_action)

    def update_servers_list(self):
        # Clear servers_group
        for action in self.servers_group.actions():
            self.servers_group.removeAction(action)
        self.populate_servers_menu()

    def server_selected(self, server_name):
        match = [transports for (host, transports) in self.servers_list
                 if host == server_name]
        assert len(match) == 1
        match = match[0]
        # Default to TCP if available else use anything
        # TODO: protocol should be selectable.
        tcp_port = [port for (protocol, port) in match if protocol == "t"]
        if len(tcp_port) == 0:
            protocol = match[0][0]
            port = match[0][1]
        else:
            protocol = "t"
            port = tcp_port[0]
        server_line = "%s:%s:%s" % (server_name, port, protocol)

        # Should this have exception handling?
        self.wallet.interface.set_server(server_line, self.wallet.config.get("proxy"))

    def copy_address(self, receive_popup):
        """Copy the wallet addresses into the client."""
        addrs = [addr for addr in self.wallet.all_addresses()
                 if not self.wallet.is_change(addr)]
        # Select most recent addresses from gap limit
        addrs = addrs[-self.wallet.gap_limit:]
        copied_address = random.choice(addrs)
        qApp.clipboard().setText(copied_address)
        receive_popup.setup(copied_address)
        receive_popup.popup()

    def waiting_dialog(self, f):
        s = Timer()
        s.start()
        w = QDialog()
        w.resize(200, 70)
        w.setWindowTitle('Electrum')
        l = QLabel('Sending transaction, please wait.')
        vbox = QVBoxLayout()
        vbox.addWidget(l)
        w.setLayout(vbox)
        w.show()
        def ff():
            s = f()
            if s: l.setText(s)
            else: w.close()
        w.connect(s, QtCore.SIGNAL('timersignal'), ff)
        w.exec_()
        w.destroy()

    def send(self, address, amount, parent_window):
        """Send bitcoins to the target address."""
        dest_address = self.fetch_destination(address)

        if dest_address is None or not self.wallet.is_valid(dest_address):
            QMessageBox.warning(parent_window, _('Error'), 
                _('Invalid Bitcoin Address') + ':\n' + address, _('OK'))
            return False

        convert_amount = lambda amount: \
            int(D(unicode(amount)) * bitcoin(1))
        amount = convert_amount(amount)

        if self.wallet.use_encryption:
            password_dialog = PasswordDialog(parent_window)
            password = password_dialog.run()
            if not password:
                return
        else:
            password = None

        fee = 0
        # 0.1 BTC = 10000000
        if amount < bitcoin(1) / 10:
            # 0.001 BTC
            fee = bitcoin(1) / 1000

        try:
            tx = self.wallet.mktx([(dest_address, amount)], "", password, fee)
        except BaseException as error:
            QMessageBox.warning(parent_window, _('Error'), str(error), _('OK'))
            return False

        h = self.wallet.send_tx(tx)

        self.waiting_dialog(lambda: False if self.wallet.tx_event.isSet() else _("Sending transaction, please wait..."))
          
        status, message = self.wallet.receive_tx(h)

        if not status:
            import tempfile
            dumpf = tempfile.NamedTemporaryFile(delete=False)
            dumpf.write(tx)
            dumpf.close()
            print "Dumped error tx to", dumpf.name
            QMessageBox.warning(parent_window, _('Error'), message, _('OK'))
            return False

        QMessageBox.information(parent_window, '',
            _('Your transaction has been sent.') + '\n' + message, _('OK'))
        return True

    def fetch_destination(self, address):
        recipient = unicode(address).strip()

        # alias
        match1 = re.match("^(|([\w\-\.]+)@)((\w[\w\-]+\.)+[\w\-]+)$",
                          recipient)

        # label or alias, with address in brackets
        match2 = re.match("(.*?)\s*\<([1-9A-HJ-NP-Za-km-z]{26,})\>",
                          recipient)
        
        if match1:
            dest_address = \
                self.wallet.get_alias(recipient, True, 
                                      self.show_message, self.question)
            return dest_address
        elif match2:
            return match2.group(2)
        else:
            return recipient

    def is_valid(self, address):
        """Check if bitcoin address is valid."""
        return self.wallet.is_valid(address)

    def acceptbit(self, currency):
        master_pubkey = self.wallet.master_public_key
        url = "http://acceptbit.com/mpk/%s/%s" % (master_pubkey, currency)
        webbrowser.open(url)

    def show_seed_dialog(self):
        gui_qt.ElectrumWindow.show_seed_dialog(self.wallet)

class MiniDriver(QObject):

    INITIALIZING = 0
    CONNECTING = 1
    SYNCHRONIZING = 2
    READY = 3

    def __init__(self, wallet, window):
        super(QObject, self).__init__()

        self.wallet = wallet
        self.window = window

        self.wallet.interface.register_callback('updated',self.update_callback)
        self.wallet.interface.register_callback('connected', self.update_callback)
        self.wallet.interface.register_callback('disconnected', self.update_callback)

        self.state = None

        self.initializing()
        self.connect(self, SIGNAL("updatesignal()"), self.update)
        self.update_callback()

    # This is a hack to workaround that Qt does not like changing the
    # window properties from this other thread before the runloop has
    # been called from.
    def update_callback(self):
        self.emit(SIGNAL("updatesignal()"))

    def update(self):
        if not self.wallet.interface:
            self.initializing()
        elif not self.wallet.interface.is_connected:
            self.connecting()
        elif not self.wallet.up_to_date:
            self.synchronizing()
        else:
            self.ready()

        if self.wallet.up_to_date:
            self.update_balance()
            self.update_completions()
            self.update_history()

    def initializing(self):
        if self.state == self.INITIALIZING:
            return
        self.state = self.INITIALIZING
        self.window.deactivate()

    def connecting(self):
        if self.state == self.CONNECTING:
            return
        self.state = self.CONNECTING
        self.window.deactivate()

    def synchronizing(self):
        if self.state == self.SYNCHRONIZING:
            return
        self.state = self.SYNCHRONIZING
        self.window.deactivate()

    def ready(self):
        if self.state == self.READY:
            return
        self.state = self.READY
        self.window.activate()

    def update_balance(self):
        conf_balance, unconf_balance = self.wallet.get_balance()
        balance = D(conf_balance + unconf_balance)
        self.window.set_balances(balance)

    def update_completions(self):
        completions = []
        for addr, label in self.wallet.labels.items():
            if addr in self.wallet.addressbook:
                completions.append("%s <%s>" % (label, addr))
        completions = completions + self.wallet.aliases.keys()
        self.window.update_completions(completions)

    def update_history(self):
        tx_history = self.wallet.get_tx_history()
        self.window.update_history(tx_history)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open(rsrc("style.css")) as style_file:
        app.setStyleSheet(style_file.read())
    mini = MiniWindow()
    sys.exit(app.exec_())

