#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2013 ecdsa@github
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

from PyQt4.QtGui import *
from PyQt4.QtCore import *
from electrum.i18n import _
from util import *
import re
import math

def check_password_strength(password):

    '''
    Check the strength of the password entered by the user and return back the same
    :param password: password entered by user in New Password
    :return: password strength Weak or Medium or Strong
    '''
    password = unicode(password)
    n = math.log(len(set(password)))
    num = re.search("[0-9]", password) is not None and re.match("^[0-9]*$", password) is None
    caps = password != password.upper() and password != password.lower()
    extra = re.match("^[a-zA-Z0-9]*$", password) is None
    score = len(password)*( n + caps + num + extra)/20
    password_strength = {0:"Weak",1:"Medium",2:"Strong",3:"Very Strong"}
    return password_strength[min(3, int(score))]

class PasswordDialog(WindowModalDialog):

    PW_NEW, PW_CHANGE, PW_PASSPHRASE = range(0, 3)
    titles = [_("Enter Password"), _("Change Password"), _("Enter Passphrase")]

    def __init__(self, parent, wallet, msg, kind):
        WindowModalDialog.__init__(self, parent, self.titles[kind])
        self.wallet = wallet

        self.pw = QLineEdit()
        self.pw.setEchoMode(2)
        self.new_pw = QLineEdit()
        self.new_pw.setEchoMode(2)
        self.conf_pw = QLineEdit()
        self.conf_pw.setEchoMode(2)
        self.kind = kind

        vbox = QVBoxLayout()
        label = QLabel(msg + "\n")
        label.setWordWrap(True)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(0, 150)
        grid.setColumnMinimumWidth(1, 100)
        grid.setColumnStretch(1,1)

        if kind == self.PW_PASSPHRASE:
            vbox.addWidget(label)
            msgs = [_('Passphrase:'), _('Confirm Passphrase:')]
        else:
            logo_grid = QGridLayout()
            logo_grid.setSpacing(8)
            logo_grid.setColumnMinimumWidth(0, 70)
            logo_grid.setColumnStretch(1,1)

            logo = QLabel()
            logo.setAlignment(Qt.AlignCenter)

            logo_grid.addWidget(logo,  0, 0)
            logo_grid.addWidget(label, 0, 1, 1, 2)
            vbox.addLayout(logo_grid)

            m1 = _('New Password:') if kind == self.PW_NEW else _('Password:')
            msgs = [m1, _('Confirm Password:')]
            if wallet and wallet.use_encryption:
                grid.addWidget(QLabel(_('Current Password:')), 0, 0)
                grid.addWidget(self.pw, 0, 1)
                lockfile = ":icons/lock.png"
            else:
                lockfile = ":icons/unlock.png"
                logo.setPixmap(QPixmap(lockfile).scaledToWidth(36))

        grid.addWidget(QLabel(msgs[0]), 1, 0)
        grid.addWidget(self.new_pw, 1, 1)

        grid.addWidget(QLabel(msgs[1]), 2, 0)
        grid.addWidget(self.conf_pw, 2, 1)
        vbox.addLayout(grid)

        # Password Strength Label
        self.pw_strength = QLabel()
        grid.addWidget(self.pw_strength, 3, 0, 1, 2)
        self.new_pw.textChanged.connect(self.pw_changed)
        self.conf_pw.textChanged.connect(self.check_OKButton)

        self.OKButton = OkButton(self)
        vbox.addStretch(1)
        vbox.addLayout(Buttons(CancelButton(self), self.OKButton))
        self.setLayout(vbox)

    def pw_changed(self):
        password = self.new_pw.text()
        if password:
            colors = {"Weak":"Red", "Medium":"Blue", "Strong":"Green",
                      "Very Strong":"Green"}
            strength = check_password_strength(password)
            label = (_("Password Strength") + ": " + "<font color="
                     + colors[strength] + ">" + strength + "</font>")
        else:
            label = ""
        self.pw_strength.setText(label)
        self.check_OKButton()

    def check_OKButton(self):
        self.OKButton.setEnabled(self.new_pw.text() == self.conf_pw.text())

    def run(self):
        if not self.exec_():
            return False, None, None

        if self.kind == self.PW_CHANGE:
            old_password = unicode(self.pw.text()) or None
        else:
            old_password = None
        new_password = unicode(self.new_pw.text()) or None

        return True, old_password, new_password
