from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMenu, QHBoxLayout, QLabel, QVBoxLayout, QGridLayout, QLineEdit,
                             QPushButton, QAbstractItemView, QComboBox)
from PyQt5.QtGui import QFont, QStandardItem, QBrush

from electrum.util import bh2u, NotEnoughFunds, NoDynamicFeeEstimates
from electrum.i18n import _
from electrum.lnchannel import AbstractChannel, PeerState
from electrum.wallet import Abstract_Wallet
from electrum.lnutil import LOCAL, REMOTE, format_short_channel_id, LN_MAX_FUNDING_SAT
from electrum.lnworker import LNWallet

from .util import (MyTreeView, WindowModalDialog, Buttons, OkButton, CancelButton,
                   EnterButton, WaitingDialog, MONOSPACE_FONT, ColorScheme)
from .amountedit import BTCAmountEdit, FreezableLineEdit
from .util import WWLabel
from .fee_slider import FeeSlider, FeeComboBox

import asyncio
from .util import read_QIcon


class SwapDialog(WindowModalDialog):

    def __init__(self, window):
        WindowModalDialog.__init__(self, window, _('Submarine Swap'))
        self.window = window
        self.config = window.config
        self.swap_manager = self.window.wallet.lnworker.swap_manager
        self.network = window.network
        self.normal_fee = 0
        self.lockup_fee = 0
        self.claim_fee = self.swap_manager.get_tx_fee()
        self.percentage = 0
        self.min_amount = 0
        self.max_amount = 0
        vbox = QVBoxLayout(self)
        vbox.addWidget(WWLabel('Swap lightning funds for on-chain funds if you need to increase your receiving capacity. This service is powered by the Boltz backend.'))
        self.send_amount_e = BTCAmountEdit(self.window.get_decimal_point)
        self.recv_amount_e = BTCAmountEdit(self.window.get_decimal_point)
        self.send_button = QPushButton('')
        self.recv_button = QPushButton('')
        self.send_follows = False
        self.is_reverse = True
        self.send_amount_e.follows = False
        self.recv_amount_e.follows = False
        self.send_button.clicked.connect(self.toggle_direction)
        self.recv_button.clicked.connect(self.toggle_direction)
        self.send_amount_e.textChanged.connect(self.on_send_edited)
        self.recv_amount_e.textChanged.connect(self.on_recv_edited)
        fee_slider = FeeSlider(self.window, self.config, self.fee_slider_callback)
        fee_combo = FeeComboBox(fee_slider)
        fee_slider.update()
        self.fee_label = QLabel()
        self.percentage_label = QLabel()
        h = QGridLayout()
        h.addWidget(QLabel(_('You send')+':'), 2, 0)
        h.addWidget(self.send_amount_e, 2, 1)
        h.addWidget(self.send_button, 2, 2)
        h.addWidget(QLabel(_('You receive')+':'), 3, 0)
        h.addWidget(self.recv_amount_e, 3, 1)
        h.addWidget(self.recv_button, 3, 2)
        h.addWidget(QLabel(_('Swap fee')+':'), 4, 0)
        h.addWidget(self.percentage_label, 4, 1)
        h.addWidget(QLabel(_('Mining fees')+':'), 5, 0)
        h.addWidget(self.fee_label, 5, 1)
        h.addWidget(fee_slider, 6, 1)
        h.addWidget(fee_combo, 6, 2)
        vbox.addLayout(h)
        vbox.addStretch(1)
        ok_button = OkButton(self)
        ok_button.setDefault(True)
        vbox.addLayout(Buttons(CancelButton(self), ok_button))
        self.update()

    def fee_slider_callback(self, dyn, pos, fee_rate):
        if dyn:
            if self.config.use_mempool_fees():
                self.config.set_key('depth_level', pos, False)
            else:
                self.config.set_key('fee_level', pos, False)
        else:
            self.config.set_key('fee_per_kb', fee_rate, False)
        # read claim_fee from config
        self.claim_fee = self.swap_manager.get_tx_fee()
        if self.send_follows:
            self.on_recv_edited()
        else:
            self.on_send_edited()
        self.update()

    def toggle_direction(self):
        self.is_reverse = not self.is_reverse
        self.send_amount_e.setAmount(None)
        self.recv_amount_e.setAmount(None)
        self.update()

    def on_send_edited(self):
        if self.send_amount_e.follows:
            return
        self.send_amount_e.setStyleSheet(ColorScheme.DEFAULT.as_stylesheet())
        amount = self.send_amount_e.get_amount()
        self.recv_amount_e.follows = True
        self.recv_amount_e.setAmount(self.get_recv_amount(amount))
        self.recv_amount_e.setStyleSheet(ColorScheme.BLUE.as_stylesheet())
        self.recv_amount_e.follows = False
        self.send_follows = False

    def on_recv_edited(self):
        if self.recv_amount_e.follows:
            return
        self.recv_amount_e.setStyleSheet(ColorScheme.DEFAULT.as_stylesheet())
        amount = self.recv_amount_e.get_amount()
        self.send_amount_e.follows = True
        self.send_amount_e.setAmount(self.get_send_amount(amount))
        self.send_amount_e.setStyleSheet(ColorScheme.BLUE.as_stylesheet())
        self.send_amount_e.follows = False
        self.send_follows = True

    def on_pairs(self, pairs):
        fees = pairs['pairs']['BTC/BTC']['fees']
        self.percentage = fees['percentage']
        self.normal_fee = fees['minerFees']['baseAsset']['normal']
        self.lockup_fee = fees['minerFees']['baseAsset']['reverse']['lockup']
        #self.claim_fee = fees['minerFees']['baseAsset']['reverse']['claim']
        limits = pairs['pairs']['BTC/BTC']['limits']
        self.min_amount = limits['minimal']
        self.max_amount = limits['maximal']
        self.update()

    def update(self):
        self.send_button.setIcon(read_QIcon("lightning.png" if self.is_reverse else "bitcoin.png"))
        self.recv_button.setIcon(read_QIcon("lightning.png" if not self.is_reverse else "bitcoin.png"))
        fee = self.lockup_fee + self.claim_fee if self.is_reverse else self.normal_fee
        self.fee_label.setText(self.window.format_amount(fee) + ' ' + self.window.base_unit())
        self.percentage_label.setText('%.2f'%self.percentage + '%')

    def set_minimum(self):
        self.send_amount_e.setAmount(self.min_amount)

    def set_maximum(self):
        self.send_amount_e.setAmount(self.max_amount)

    def get_recv_amount(self, send_amount):
        if send_amount is None:
            return
        if send_amount < self.min_amount or send_amount > self.max_amount:
            return
        x = send_amount
        if self.is_reverse:
            x = int(x * (100 - self.percentage) / 100)
            x -= self.lockup_fee
            x -= self.claim_fee
        else:
            x -= self.normal_fee
            x = int(x * (100 - self.percentage) / 100)
        if x < 0:
            return
        return x

    def get_send_amount(self, recv_amount):
        if not recv_amount:
            return
        x = recv_amount
        if self.is_reverse:
            x += self.lockup_fee
            x += self.claim_fee
            x = int(x * 100 / (100 - self.percentage)) + 1
        else:
            x = int(x * 100 / (100 - self.percentage)) + 1
            x += self.normal_fee
        return x

    def run(self):
        self.window.run_coroutine_from_thread(self.swap_manager.get_pairs(), self.on_pairs)
        if not self.exec_():
            return
        if self.is_reverse:
            lightning_amount = self.send_amount_e.get_amount()
            onchain_amount = self.recv_amount_e.get_amount() + self.claim_fee
            coro = self.swap_manager.reverse_swap(lightning_amount, onchain_amount)
            self.window.run_coroutine_from_thread(coro)
        else:
            lightning_amount = self.recv_amount_e.get_amount()
            onchain_amount = self.send_amount_e.get_amount()
            self.window.protect(self.do_normal_swap, (lightning_amount, onchain_amount))

    def do_normal_swap(self, lightning_amount, onchain_amount, password):
        coro = self.swap_manager.normal_swap(lightning_amount, onchain_amount, password)
        self.window.run_coroutine_from_thread(coro)
