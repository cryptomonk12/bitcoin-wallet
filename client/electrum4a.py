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



import android
from interface import WalletSynchronizer
from wallet import Wallet
from wallet import format_satoshis
from decimal import Decimal


import datetime


droid = android.Android()
wallet = Wallet()
wallet.set_path("/sdcard/electrum.dat")
wallet.read()







def show_addresses():
    droid.dialogCreateAlert("Addresses:")
    l = []
    for i in range(len(wallet.addresses)):
        addr = wallet.addresses[i]
        l.append( wallet.labels.get(addr,'') + ' ' + addr)

    droid.dialogSetItems(l)
    droid.dialogShow()
    response = droid.dialogGetResponse().result
    droid.dialogDismiss()

    # show qr code
    print response


title = """
        <TextView android:id="@+id/titleTextView" 
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:text="Electrum"
                android:textAppearance="?android:attr/textAppearanceLarge" 
                android:gravity="center"
                android:textColor="0xff0055ff"
                android:textSize="30" >
        </TextView>
"""

def main_layout():
    return """<?xml version="1.0" encoding="utf-8"?>
<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" 
    android:layout_height="match_parent">

<LinearLayout 
        android:id="@+id/background"
        android:orientation="vertical" 
        android:layout_width="match_parent"
        android:layout_height="match_parent" 
        android:background="#ff000022">

        %s

        <TextView android:id="@+id/balanceTextView" 
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:text=""
                android:textAppearance="?android:attr/textAppearanceLarge" 
                android:gravity="left"
                android:textColor="0xffffffff"
                android:padding="10"
                android:textSize="18" >
        </TextView>


        <TextView android:id="@+id/historyTextView" 
                android:layout_width="match_parent"
                android:layout_height="70" 
                android:text="Recent transactions"
                android:textAppearance="?android:attr/textAppearanceLarge" 
                android:gravity="center_vertical|center_horizontal|center">
        </TextView>

        %s

        <TableLayout 
           android:layout_width="match_parent" 
           android:layout_height="wrap_content" 
           android:id="@+id/linearLayout1">
            <TableRow>
                <Button android:id="@+id/buttonHistory" 
                        android:layout_width="wrap_content"
                        android:layout_height="wrap_content" 
                        android:text="History">
                </Button>
                <Button android:id="@+id/buttonSend" 
                        android:layout_width="wrap_content"
                        android:layout_height="wrap_content" 
                        android:text="  Send ">
                </Button>
                <Button android:id="@+id/buttonReceive" 
                        android:layout_width="wrap_content"
                        android:layout_height="wrap_content" 
                        android:text="Receive">
                </Button>
                <Button android:id="@+id/buttonContacts" 
                        android:layout_width="wrap_content"
                        android:layout_height="wrap_content" 
                        android:text="Contacts">
                </Button>
           </TableRow>
        </TableLayout>

</LinearLayout>
</ScrollView>
"""%(title, get_history_layout(15))


payto_layout="""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
 android:id="@+id/background"
 android:orientation="vertical" 
 android:layout_width="match_parent"
 android:layout_height="match_parent" 
 android:background="#ff000022">

        %s

        <TextView android:id="@+id/recipientTextView" 
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:text="Pay to:"
                android:textAppearance="?android:attr/textAppearanceLarge" 
                android:gravity="left">
        </TextView>


        <EditText android:id="@+id/recipient"
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:tag="Tag Me" android:inputType="textCapWords|textPhonetic|number">
        </EditText>

        <LinearLayout android:id="@+id/linearLayout1"
                android:layout_width="match_parent"
                android:layout_height="wrap_content">
                <Button android:id="@+id/buttonQR" android:layout_width="wrap_content"
                        android:layout_height="wrap_content" android:text="Scan QR"></Button>
                <Button android:id="@+id/buttonContacts" android:layout_width="wrap_content"
                        android:layout_height="wrap_content" android:text="Contacts"></Button>
        </LinearLayout>


        <TextView android:id="@+id/labelTextView" 
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:text="Description:"
                android:textAppearance="?android:attr/textAppearanceLarge" 
                android:gravity="left">
        </TextView>

        <EditText android:id="@+id/label"
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:tag="Tag Me" android:inputType="textCapWords|textPhonetic|number">
        </EditText>

        <TextView android:id="@+id/amountLabelTextView" 
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:text="Amount:"
                android:textAppearance="?android:attr/textAppearanceLarge" 
                android:gravity="left">
        </TextView>

        <EditText android:id="@+id/amount"
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:tag="Tag Me" android:inputType="numberDecimal">
        </EditText>

        <LinearLayout android:layout_width="match_parent"
                android:layout_height="wrap_content" android:id="@+id/linearLayout1">
                <Button android:id="@+id/buttonPay" android:layout_width="wrap_content"
                        android:layout_height="wrap_content" android:text="Send"></Button>
                <Button android:id="@+id/buttonCancelSend" android:layout_width="wrap_content"
                        android:layout_height="wrap_content" android:text="Cancel"></Button>
        </LinearLayout>
</LinearLayout>
"""%title


settings_layout = """<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
        android:id="@+id/background"
        android:orientation="vertical" 
        android:layout_width="match_parent"
        android:layout_height="match_parent" 
        android:background="#ff000000">

        %s

        <TextView android:id="@+id/serverTextView" 
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:text="Server:"
                android:textAppearance="?android:attr/textAppearanceLarge" 
                android:gravity="left">
        </TextView>

        <EditText android:id="@+id/server"
                android:layout_width="match_parent"
                android:layout_height="wrap_content" 
                android:tag="Tag Me" android:inputType="*">
        </EditText>

        <LinearLayout android:layout_width="match_parent"
                android:layout_height="wrap_content" android:id="@+id/linearLayout1">
                <Button android:id="@+id/buttonServer" android:layout_width="wrap_content"
                        android:layout_height="wrap_content" android:text="Server List"></Button>
                <Button android:id="@+id/buttonSave" android:layout_width="wrap_content"
                        android:layout_height="wrap_content" android:text="Save"></Button>
                <Button android:id="@+id/buttonCancel" android:layout_width="wrap_content"
                        android:layout_height="wrap_content" android:text="Cancel"></Button>
        </LinearLayout>

</LinearLayout>
"""%title




def get_history_values(n):
    values = []
    h = wallet.get_tx_history()
    for i in range(n):
        line = h[-i-1]
        v = line['value']
        try:
            dt = datetime.datetime.fromtimestamp( line['timestamp'] )
            if dt.date() == dt.today().date():
                time_str = str( dt.time() )
            else:
                time_str = str( dt.date() )
            conf = 'v'

        except:
            print line['timestamp']
            time_str = 'pending'
            conf = 'o'

        label = line.get('label')
        #if not label: label = line['tx_hash']
        is_default_label = (label == '') or (label is None)
        if is_default_label: label = line['default_label']
        values.append((conf, '  ' + time_str, '  ' + format_satoshis(v,True), '  ' + label ))

    return values


def get_history_layout(n):
    rows = ""
    i = 0
    values = get_history_values(n)
    for v in values:
        a,b,c,d = v
        color = "0xff00ff00" if a == 'v' else "0xffff0000"
        rows += """
        <TableRow>
          <TextView
            android:id="@+id/hl_%d_col1" 
            android:layout_column="0"
            android:text="%s"
            android:textColor="%s"
            android:padding="3" />
          <TextView
            android:id="@+id/hl_%d_col2" 
            android:layout_column="1"
            android:text="%s"
            android:padding="3" />
          <TextView
            android:id="@+id/hl_%d_col3" 
            android:layout_column="2"
            android:text="%s"
            android:padding="3" />
          <TextView
            android:id="@+id/hl_%d_col4" 
            android:layout_column="3"
            android:text="%s"
            android:padding="4" />
        </TableRow>"""%(i,a,color,i,b,i,c,i,d)
        i += 1

    output = """
<TableLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="fill_parent"
    android:layout_height="wrap_content"
    android:stretchColumns="0,1,2,3">
    %s
</TableLayout>"""% rows
    return output

def set_history_layout(n):
    values = get_history_values(n)
    i = 0
    for v in values:
        a,b,c,d = v
        droid.fullSetProperty("hl_%d_col1"%i,"text", a)

        if a == 'v':
            droid.fullSetProperty("hl_%d_col1"%i, "textColor","0xff00ff00")
        else:
            droid.fullSetProperty("hl_%d_col1"%i, "textColor","0xffff0000")

        droid.fullSetProperty("hl_%d_col2"%i,"text", b)
        droid.fullSetProperty("hl_%d_col3"%i,"text", c)
        droid.fullSetProperty("hl_%d_col4"%i,"text", d)

        i += 1


def update_layout():

    if not wallet.interface.is_connected:
        text = "Not connected..."
    elif wallet.blocks == 0:
        text = "Server not ready"
    elif not wallet.up_to_date:
        text = "Synchronizing..."
    else:
        c, u = wallet.get_balance()
        text = "Balance:"+format_satoshis(c) 
        if u : text += '['+ format_satoshis(u,True)+']'

    droid.fullSetProperty("balanceTextView", "text", text)

    if wallet.was_updated and wallet.up_to_date:
        wallet.was_updated = False
        set_history_layout(15)
        droid.vibrate()



def recipient_dialog():
    title = 'Pay to:'
    message = ('Select recipient')
    droid.dialogCreateAlert(title, message)
    droid.dialogSetItems(wallet.addressbook)
    droid.dialogShow()
    response = droid.dialogGetResponse()
    result = response.result.get('item')
    droid.dialogDismiss()
    if result is not None:
        addr = wallet.addressbook[result]
        return addr


def pay_to(recipient, amount, fee, label):

    if wallet.use_encryption:
        password  = droid.dialogGetPassword('Password').result
        print "password", password
    else:
        password = None

    droid.dialogCreateSpinnerProgress("Electrum", "signing transaction...")
    droid.dialogShow()
    tx = wallet.mktx( recipient, amount, label, password, fee)
    print tx
    droid.dialogDismiss()

    if tx:
        r, h = wallet.sendtx( tx )
        droid.dialogCreateAlert('tx sent', h)
        droid.dialogSetPositiveButtonText('OK')
        droid.dialogShow()
        response = droid.dialogGetResponse().result
        droid.dialogDismiss()
        return h
    else:
        return 'error'







if not wallet.file_exists:
    droid.dialogCreateAlert("wallet file not found")
    droid.dialogSetPositiveButtonText('OK')
    droid.dialogShow()
    resp = droid.dialogGetResponse().result
    print resp

    code = droid.scanBarcode()
    r = code.result
    if r:
        seed = r['extras']['SCAN_RESULT']
    else:
        exit(1)

    droid.dialogCreateAlert('seed', seed)
    droid.dialogSetPositiveButtonText('OK')
    droid.dialogSetNegativeButtonText('Cancel')
    droid.dialogShow()
    response = droid.dialogGetResponse().result
    droid.dialogDismiss()
    print response

    wallet.seed = str(seed)
    wallet.init_mpk( wallet.seed )
    droid.dialogCreateSpinnerProgress("Electrum", "recovering wallet...")
    droid.dialogShow()
    WalletSynchronizer(wallet,True).start()
    wallet.update()
    wallet.save()
    droid.dialogDismiss()
    droid.vibrate()

    if wallet.is_found():
        # history and addressbook
        wallet.update_tx_history()
        wallet.fill_addressbook()
        droid.dialogCreateAlert("recovery successful")
        droid.dialogShow()
        wallet.save()
    else:
        droid.dialogCreateSpinnerProgress("wallet not found")
        droid.dialogShow()
        exit(1)

else:
    WalletSynchronizer(wallet,True).start()


def add_menu():
    droid.addOptionsMenuItem("Settings","settings",None,"")
    droid.addOptionsMenuItem("Quit","quit",None,"")

add_menu()


def main_loop():
    droid.fullShow(main_layout())
    update_layout()
    out = None
    while out is None:

        event = droid.eventWait(1000).result  # wait for 1 second
        if not event:
            update_layout()
            continue

        print "got event in main loop", event

        if event["name"]=="click":
            id=event["data"]["id"]

            if id=="buttonSend":
                out = 'payto'

            elif id=="buttonReceive":
                show_addresses()

        elif event["name"]=="settings":
            out = 'settings'

        elif event["name"]=="key":
            if event["data"]["key"] == '4':
                out = 'quit'

        elif event["name"]=="quit":
            out = 'quit'

        # print droid.fullSetProperty("background","backgroundColor","0xff7f0000")
        # elif event["name"]=="screen":
        #    if event["data"]=="destroy":
        #        out = 'exit'

    return out
                    
def payto_loop():
    droid.fullShow(payto_layout)
    out = None
    while out is None:
        event = droid.eventWait().result
        print "got event in payto loop", event

        if event["name"] == "click":
            id = event["data"]["id"]

            if id=="buttonPay":

                droid.fullQuery()
                recipient = droid.fullQueryDetail("recipient").result.get('text')
                label  = droid.fullQueryDetail("label").result.get('text')
                amount = droid.fullQueryDetail('amount').result.get('text')
                fee    = '0.001'
                amount = int( 100000000 * Decimal(amount) )
                fee    = int( 100000000 * Decimal(fee) )
                result = pay_to(recipient, amount, fee, label)

                droid.dialogCreateAlert('result', result)
                droid.dialogSetPositiveButtonText('OK')
                droid.dialogShow()
                droid.dialogGetResponse()
                droid.dialogDismiss()
                out = 'main'

            elif id=="buttonContacts":
                addr = recipient_dialog()
                droid.fullSetProperty("recipient","text",addr)

            elif id=="buttonQR":
                code = droid.scanBarcode()
                r = code.result
                if r:
                    addr = r['extras']['SCAN_RESULT']
                    if addr:
                        droid.fullSetProperty("recipient","text",addr)
                    
            elif id=="buttonCancelSend":
                out = 'main'

        elif event["name"]=="settings":
            out = 'settings'

        elif event["name"]=="quit":
            out = 'quit'

        elif event["name"]=="key":
            if event["data"]["key"] == '4':
                out = 'main'

        #elif event["name"]=="screen":
        #    if event["data"]=="destroy":
        #        out = 'main'

    return out


def history_loop():
    layout = get_history_layout(15)
    droid.fullShow(layout)
    out = None
    while out is None:
        event = droid.eventWait().result
        print "got event in history loop", event
        if event["name"] == "click":

            if event["data"]["text"] == "OK":
                out = 'main'

        elif event["name"]=="key":
            if event["data"]["key"] == '4':
                out = 'main'

        #elif event["name"]=="screen":
        #    if event["data"]=="destroy":
        #        out = 'main'

    return out

def server_dialog(plist):
    droid.dialogCreateAlert("servers")
    droid.dialogSetItems( plist.keys() )
    droid.dialogShow()
    i = droid.dialogGetResponse().result.get('item')
    droid.dialogDismiss()
    if i is not None:
        response = plist.keys()[i]
        return response

def protocol_dialog(plist):
    options=["TCP","HTTP","native"]
    droid.dialogCreateAlert("Protocol")
    droid.dialogSetSingleChoiceItems(options)



def settings_loop():
    droid.fullShow(settings_layout)
    droid.fullSetProperty("server","text",wallet.server)

    out = None
    while out is None:
        event = droid.eventWait().result
        if event["name"] == "click":

            id = event["data"]["id"]

            if id=="buttonServer":
                plist = {}
                for item in wallet.interface.servers:
                    host, pp = item
                    z = {}
                    for item2 in pp:
                        protocol, port = item2
                        z[protocol] = port
                    plist[host] = z

                host = server_dialog(plist)
                p = plist[host]
                port = p['t']
                srv = host + ':' + port + ':t'
                droid.fullSetProperty("server","text",srv)

            elif id=="buttonSave":
                droid.fullQuery()
                srv = droid.fullQueryDetail("server").result.get('text')
                try:
                    wallet.set_server(srv)
                    out = 'main'
                except:
                    droid.dialogCreateAlert('error')
                    droid.dialogSetPositiveButtonText('OK')
                    droid.dialogShow()
                    droid.dialogGetResponse()
                    droid.dialogDismiss()
                    
            elif id=="buttonCancel":
                out = 'main'

        elif event["name"] == "key":
            if event["data"]["key"] == '4':
                out = 'main'

        elif event["name"]=="quit":
            out = 'quit'

    return out

                


s = 'main'
while True:
    if s == 'main':
        s = main_loop()
    elif s == 'payto':
        s = payto_loop()
    elif s == 'settings':
        s = settings_loop()
    elif s == 'history':
        s = history_loop()
    elif s == 'contacts':
        s = contacts_loop()
    else:
        break

droid.fullDismiss()
droid.makeToast("Bye!")
