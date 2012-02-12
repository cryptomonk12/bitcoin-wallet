import sys, time, datetime

# todo: see PySide

from PyQt4.QtGui import *
from PyQt4.QtCore import *
import PyQt4.QtCore as QtCore
import PyQt4.QtGui as QtGui

from wallet import format_satoshis

def restore_create_dialog(wallet):
    pass

class Sender(QtCore.QThread):
    def run(self):
        while True:
            self.emit(QtCore.SIGNAL('testsignal'))
            time.sleep(0.5)


class ElectrumWindow(QMainWindow):

    def __init__(self, wallet):
        QMainWindow.__init__(self)
        self.wallet = wallet

        tabs = QTabWidget(self)
        tabs.addTab(self.create_history_tab(), 'History')
        tabs.addTab(self.create_send_tab(),    'Send')
        tabs.addTab(self.create_receive_tab(), 'Receive')
        tabs.addTab(self.create_contacts_tab(),'Contacts')
        tabs.addTab(self.create_wall_tab(),    'Wall')
        tabs.setMinimumSize(600, 400)
        tabs.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.setCentralWidget(tabs)
        self.create_status_bar()
        self.setGeometry(100,100,750,400)
        self.setWindowTitle( 'Electrum ' + self.wallet.electrum_version + ' - Qt')
        self.show()

        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)


    def connect_slots(self, sender):
        self.connect(sender, QtCore.SIGNAL('testsignal'), self.update_wallet)


    def update_wallet(self):
        if self.wallet.interface.is_connected:
            if self.wallet.interface.blocks == 0:
                text = "Server not ready"
            elif not self.wallet.interface.was_polled:
                text = "Synchronizing..."
            else:
                c, u = self.wallet.get_balance()
                text =  "Balance: %s "%( format_satoshis(c) )
                if u: text +=  "[%s unconfirmed]"%( format_satoshis(u,True) )
        else:
            text = "Not connected"
        self.statusBar().showMessage(text)

        if self.wallet.interface.was_updated:
            self.wallet.interface.was_updated = False
            self.textbox.setText( self.wallet.interface.message )
            self.update_history_tab()
            self.update_receive_tab()
            self.update_contacts_tab()


    def create_history_tab(self):
        self.history_list = w = QTreeWidget(self)
        w.setColumnCount(5)
        w.setColumnWidth(0, 40) 
        w.setColumnWidth(1, 140) 
        w.setColumnWidth(2, 340) 
        w.setHeaderLabels( ['', 'Date', 'Description', 'Amount', 'Balance'] )
        return w

    def update_history_tab(self):
        self.history_list.clear()
        balance = 0
        for tx in self.wallet.get_tx_history():
            tx_hash = tx['tx_hash']
            if tx['height']:
                conf = self.wallet.interface.blocks - tx['height'] + 1
                time_str = datetime.datetime.fromtimestamp( tx['nTime']).isoformat(' ')[:-3]
                icon = QIcon("icons/gtk-apply.svg")
            else:
                conf = 0
                time_str = 'pending'
                icon = QIcon("icons/gtk-execute")
            v = tx['value']
            balance += v 
            label = self.wallet.labels.get(tx_hash)
            is_default_label = (label == '') or (label is None)
            if is_default_label: label = tx['default_label']
            item = QTreeWidgetItem( [ '', time_str, label, format_satoshis(v,True), format_satoshis(balance)] )

            item.setIcon(0, icon)
            self.history_list.insertTopLevelItem(0,item)


    def create_send_tab(self):
        w = QWidget()

        paytoEdit = QtGui.QLineEdit()
        descriptionEdit = QtGui.QLineEdit()
        amountEdit = QtGui.QLineEdit()
        feeEdit = QtGui.QLineEdit()

        grid = QtGui.QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel('Pay to'), 1, 0)
        grid.addWidget(paytoEdit, 1, 1)

        grid.addWidget(QLabel('Description'), 2, 0)
        grid.addWidget(descriptionEdit, 2, 1)

        grid.addWidget(QLabel('Amount'), 3, 0)
        grid.addWidget(amountEdit, 3, 1)
        
        grid.addWidget(QLabel('Fee'), 4, 0)
        grid.addWidget(feeEdit, 4, 1)
        
        w.setLayout(grid) 
        w.show()

        w2 = QWidget()
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(w)
        vbox.addStretch(1)
        w2.setLayout(vbox)

        return w2

    def make_address_list(self, is_recv):
        w = QTreeWidget(self)
        w.setColumnCount(3)
        w.setColumnWidth(0, 330) 
        w.setColumnWidth(1, 330) 
        w.setColumnWidth(2, 20) 
        w.setHeaderLabels( ['Address', 'Label','Tx'])
        return w

    def create_receive_tab(self):
        self.receive_list = self.make_address_list(True)
        return self.receive_list


    def update_receive_tab(self):
        self.receive_list.clear()
        for address in self.wallet.all_addresses():
            if self.wallet.is_change(address):continue
            label = self.wallet.labels.get(address,'')
            n = 0 
            h = self.wallet.history.get(address,[])
            for item in h:
                if not item['is_in'] : n=n+1
            tx = "None" if n==0 else "%d"%n
            item = QTreeWidgetItem( [ address, label, tx] )
            self.receive_list.addTopLevelItem(item)

    def create_contacts_tab(self):
        self.contacts_list = self.make_address_list(False)
        return self.contacts_list

    def update_contacts_tab(self):
        self.contacts_list.clear()
        for alias, v in self.wallet.aliases.items():
            s, target = v
            label = self.wallet.labels.get(alias)
            item = QTreeWidgetItem( [ alias, label, '-'] )
            self.contacts_list.addTopLevelItem(item)
            
        for address in self.wallet.addressbook:
            label = self.wallet.labels.get(address,'')
            n = 0 
            for item in self.wallet.tx_history.values():
                if address in item['outputs'] : n=n+1
            tx = "None" if n==0 else "%d"%n
            item = QTreeWidgetItem( [ address, label, tx] )
            self.contacts_list.addTopLevelItem(item)


    def create_wall_tab(self):
        self.textbox = textbox = QTextEdit(self)
        textbox.setReadOnly(True)
        return textbox

    def create_status_bar(self):
        sb = QStatusBar()
        sb.setFixedHeight(20)
        self.setStatusBar(sb)


class BitcoinGUI():

    def __init__(self, wallet):
        self.wallet = wallet

    def main(self):
        s = Sender()
        s.start()
        app = QApplication(sys.argv)
        w = ElectrumWindow(self.wallet)
        w.connect_slots(s)
        app.exec_()
