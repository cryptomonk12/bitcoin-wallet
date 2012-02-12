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


class BitcoinWidget(QMainWindow):

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

        tabs.show()

        self.create_status_bar()
        
        self.setGeometry(100,100,750,550)
        self.setWindowTitle( 'Electrum ' + self.wallet.electrum_version )
        self.show()

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
            self.textbox.setText( self.wallet.interface.message )
            self.wallet.interface.was_updated = False
            self.update_history_tab()


    def create_history_tab(self):
        self.history_list = w = QTreeWidget(self)
        w.setColumnCount(5)
        w.setHeaderLabels( ['conf', 'Date','Description','Amount','Balance'])
        return w


    def update_history_tab(self):
        self.history_list.clear()
        balance = 0
        for tx in self.wallet.get_tx_history():
            tx_hash = tx['tx_hash']
            if tx['height']:
                conf = self.wallet.interface.blocks - tx['height'] + 1
                time_str = datetime.datetime.fromtimestamp( tx['nTime']).isoformat(' ')[:-3]
            else:
                conf = 0
                time_str = 'pending'
            v = tx['value']
            balance += v 
            label = self.wallet.labels.get(tx_hash)
            is_default_label = (label == '') or (label is None)
            if is_default_label: label = tx['default_label']
            item = QTreeWidgetItem( [ "%d"%conf, time_str, label, format_satoshis(v,True), format_satoshis(balance)] )
            self.history_list.addTopLevelItem(item)


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

    def create_receive_tab(self):
        self.addresses_list = w = QTreeWidget(self)
        w.setColumnCount(3)
        w.setHeaderLabels( ['Address', 'Label','Tx'])
        return w

    def create_contacts_tab(self):
        self.contacts_list = w = QTreeWidget(self)
        w.setColumnCount(3)
        w.setHeaderLabels( ['Address', 'Label','Tx'])
        return w

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
        w = BitcoinWidget(self.wallet)
        w.connect_slots(s)
        app.exec_()
