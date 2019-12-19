from typing import Callable, TYPE_CHECKING, Optional, Union

from kivy.app import App
from kivy.factory import Factory
from kivy.properties import ObjectProperty
from kivy.lang import Builder
from decimal import Decimal
from kivy.clock import Clock

from electrum.util import InvalidPassword
from electrum.gui.kivy.i18n import _

if TYPE_CHECKING:
    from ...main_window import ElectrumWindow
    from electrum.wallet import Abstract_Wallet
    from electrum.storage import WalletStorage

Builder.load_string('''

<PasswordDialog@Popup>
    id: popup
    title: 'Electrum'
    message: ''
    BoxLayout:
        size_hint: 1, 1
        orientation: 'vertical'
        Widget:
            size_hint: 1, 0.05
        BoxLayout:
            size_hint: 1, None
            orientation: 'horizontal'
            Label:
                size_hint: 0.70, None
                font_size: '20dp'
                text: root.message
                text_size: self.width, None
            Label:
                size_hint: 0.23, None
                font_size: '9dp'
                text: _('Generic password')
            CheckBox:
                size_hint: 0.07, None
                id: cb_generic_password
                on_active:
                    box_generic_password.visible = self.active
                    kb.disabled = box_generic_password.visible
                    textinput_generic_password.focus = box_generic_password.visible
        Widget:
            size_hint: 1, 0.05
        BoxLayout:
            orientation: 'horizontal'
            id: box_generic_password
            visible: False
            size_hint_y: 0.05
            opacity: 1 if self.visible else 0
            disabled: not self.visible
            WizardTextInput:
                id: textinput_generic_password
                valign: 'center'
                multiline: False
                on_text_validate:
                    popup.on_password(self.text, is_generic=True)
                password: True
                size_hint: 0.9, None
                unfocus_on_touch: False
            Button:
                size_hint: 0.1, None
                valign: 'center'
                background_normal: 'atlas://electrum/gui/kivy/theming/light/eye1'
                background_down: self.background_normal
                height: '50dp'
                width: '50dp'
                padding: '5dp', '5dp'
                on_release:
                    textinput_generic_password.password = False if textinput_generic_password.password else True
        Label:
            id: label_pin
            visible: not box_generic_password.visible
            size_hint_y: 0.05
            opacity: 1 if self.visible else 0
            disabled: not self.visible
            font_size: '50dp'
            text: '*'*len(kb.password) + '-'*(6-len(kb.password))
            size: self.texture_size
        Widget:
            size_hint: 1, 0.05
        GridLayout:
            id: kb
            size_hint: 1, None
            height: self.minimum_height
            update_amount: popup.update_password
            password: ''
            on_password: popup.on_password(self.password)
            spacing: '2dp'
            cols: 3
            KButton:
                text: '1'
            KButton:
                text: '2'
            KButton:
                text: '3'
            KButton:
                text: '4'
            KButton:
                text: '5'
            KButton:
                text: '6'
            KButton:
                text: '7'
            KButton:
                text: '8'
            KButton:
                text: '9'
            KButton:
                text: 'Clear'
            KButton:
                text: '0'
            KButton:
                text: '<'
''')


class PasswordDialog(Factory.Popup):

    def init(self, app: 'ElectrumWindow', *,
             wallet: Union['Abstract_Wallet', 'WalletStorage'] = None,
             msg: str, on_success: Callable = None, on_failure: Callable = None,
             is_change: int = 0):
        self.app = app
        self.wallet = wallet
        self.message = msg
        self.on_success = on_success
        self.on_failure = on_failure
        self.ids.kb.password = ''
        self.ids.textinput_generic_password.text = ''
        self.success = False
        self.is_change = is_change
        self.pw = None
        self.new_password = None
        self.title = 'Electrum' + ('  -  ' + self.wallet.basename() if self.wallet else '')
        self.ids.cb_generic_password.active = False

    def check_password(self, password):
        if self.is_change > 1:
            return True
        try:
            self.wallet.check_password(password)
            return True
        except InvalidPassword as e:
            return False

    def on_dismiss(self):
        if not self.success:
            if self.on_failure:
                self.on_failure()
            else:
                # keep dialog open
                return True
        else:
            if self.on_success:
                args = (self.pw, self.new_password) if self.is_change else (self.pw,)
                Clock.schedule_once(lambda dt: self.on_success(*args), 0.1)

    def update_password(self, c):
        kb = self.ids.kb
        text = kb.password
        if c == '<':
            text = text[:-1]
        elif c == 'Clear':
            text = ''
        else:
            text += c
        kb.password = text

    def on_password(self, pw: str, *, is_generic=False):
        if is_generic:
            if len(pw) < 6:
                self.app.show_error(_('Password is too short (min {} characters)').format(6))
                return
        if len(pw) >= 6:
            if self.check_password(pw):
                if self.is_change == 0:
                    self.success = True
                    self.pw = pw
                    self.message = _('Please wait...')
                    self.dismiss()
                elif self.is_change == 1:
                    self.pw = pw
                    self.message = _('Enter new PIN')
                    self.ids.kb.password = ''
                    self.ids.textinput_generic_password.text = ''
                    self.is_change = 2
                elif self.is_change == 2:
                    self.new_password = pw
                    self.message = _('Confirm new PIN')
                    self.ids.kb.password = ''
                    self.ids.textinput_generic_password.text = ''
                    self.is_change = 3
                elif self.is_change == 3:
                    self.success = pw == self.new_password
                    self.dismiss()
            else:
                self.app.show_error(_('Wrong PIN'))
                self.ids.kb.password = ''
