#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2015 Thomas Voegtlin
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

from electrum.i18n import _

descriptions = [
    {
        'name': 'audio_modem',
        'fullname': _('Audio MODEM'),
        'description': ('Provides support for air-gapped transaction signing.\n\n'
                        'Requires http://github.com/romanz/amodem/'),
        'requires': ['amodem'],
        'available_for': ['qt'],
    },
    {
        'name': 'btchipwallet',
        'fullname': _('BTChip Wallet'),
        'description': _('Provides support for BTChip hardware wallet') + '\n\n' + _('Requires github.com/btchip/btchip-python'),
        'requires': ['btchip'],
        'requires_wallet_type': ['btchip'],
        'registers_wallet_type': True,
        'available_for': ['qt'],
    },
    {
        'name': 'cosigner_pool',
        'fullname': _('Cosigner Pool'),
        'description': ' '.join([
            _("This plugin facilitates the use of multi-signatures wallets."),
            _("It sends and receives partially signed transactions from/to your cosigner wallet."),
            _("Transactions are encrypted and stored on a remote server.")
            ]),
        'requires_wallet_type': ['2of2', '2of3'],
        'available_for': ['qt'],
    },
    {
        'name': 'exchange_rate',
        'fullname': _("Exchange rates"),
        'description': """exchange rates, retrieved from blockchain.info, CoinDesk, or Coinbase""",
        'available_for': ['qt'],
    },
    {
        'name': 'greenaddress_instant',
        'fullname': 'GreenAddress instant',
        'description': _("Allows validating if your transactions have instant confirmations by GreenAddress"),
        'available_for': ['qt'],
    },
    {
        'name': 'labels',
        'fullname': _('LabelSync'),
        'description': '%s\n\n%s' % (_("The new and improved LabelSync plugin. This can sync your labels across multiple Electrum installs by using a remote database to save your data. Labels, transactions ids and addresses are encrypted before they are sent to the remote server."), _("The label sync's server software is open-source as well and can be found on github.com/maran/electrum-sync-server")),
        'available_for': ['qt']
    },
    {
        'name': 'openalias',
        'fullname': 'OpenAlias',
        'description': 'Allow for payments to OpenAlias addresses.\nRequires dnspython',
        'requires': ['dns'],
        'available_for': ['qt']
    },
    {
        'name': 'plot',
        'fullname': 'Plot History',
        'description': '\n'.join([
            _("Ability to plot transaction history in graphical mode."),
            _("Warning: Requires matplotlib library.")
        ]),
        'requires': ['matplotlib'],
        'available_for': ['qt'],
    },
    {
        'name':'trezor',
        'fullname': 'Trezor Wallet',
        'description': 'Provides support for Trezor hardware wallet\n\nRequires github.com/trezor/python-trezor',
        'available_for': ['qt'],
        'requires': ['trezorlib'],
        'requires_wallet_type': ['trezor'],
        'registers_wallet_type': True,
        'available_for': ['qt', 'cmdline']
    },
    {
        'name': 'trustedcoin',
        'fullname': _('Two Factor Authentication'),
        'description': ''.join([
            _("This plugin adds two-factor authentication to your wallet."), '<br/>',
            _("For more information, visit"),
            " <a href=\"https://api.trustedcoin.com/#/electrum-help\">https://api.trustedcoin.com/#/electrum-help</a>"
        ]),
        'requires_wallet_type': ['2fa'],
        'registers_wallet_type': True,
        'available_for': ['qt', 'cmdline'],
    },
    {
        'name': 'virtualkeyboard',
        'fullname': 'Virtual Keyboard',
        'description': '%s\n%s' % (_("Add an optional virtual keyboard to the password dialog."), _("Warning: do not use this if it makes you pick a weaker password.")),
        'available_for': ['qt'],
    }
]
