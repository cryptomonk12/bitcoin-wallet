#!/usr/bin/python

# python setup.py sdist --format=zip,gztar

from distutils.core import setup
import os, sys, platform, imp

version = imp.load_source('version', 'lib/version.py')
util = imp.load_source('version', 'lib/util.py')

if sys.version_info[:3] < (2,6,0):
    sys.exit("Error: Electrum requires Python version >= 2.6.0...")

data_files = []
if (len(sys.argv) > 1 and (sys.argv[1] == "sdist")) or (platform.system() != 'Windows' and platform.system() != 'Darwin'):
    print "Including all files"
    data_files += [
        ('/usr/share/applications/',['electrum.desktop']),
        ('/usr/share/app-install/icons/',['icons/electrum.png'])
    ]
    if not os.path.exists('locale'):
        os.mkdir('locale')
    for lang in os.listdir('locale'):
        if os.path.exists('locale/%s/LC_MESSAGES/electrum.mo'%lang):
            data_files.append(  ('/usr/share/locale/%s/LC_MESSAGES'%lang, ['locale/%s/LC_MESSAGES/electrum.mo'%lang]) )

data_files += [
    (util.appdata_dir(), ["data/README"]),
    (os.path.join(util.appdata_dir(), "cleanlook"), [
        "data/cleanlook/name.cfg",
        "data/cleanlook/style.css"
    ]),
    (os.path.join(util.appdata_dir(), "dark"), [
        "data/dark/background.png",
        "data/dark/name.cfg",
        "data/dark/style.css"
    ])
]

if os.path.exists("data/blockchain_headers"):
    data_files.append( (util.appdata_dir(), ["data/blockchain_headers"]) )

setup(name = "Electrum",
    version = version.ELECTRUM_VERSION,
    install_requires = ['slowaes','ecdsa'],
    package_dir = {'electrum': 'lib'},
    scripts= ['electrum'],
    data_files = data_files,
    py_modules = ['electrum.version',
                  'electrum.wallet',
                  'electrum.interface',
                  'electrum.gui',
                  'electrum.gui_qt',
                  'electrum.gui_lite',
                  'electrum.gui_text',
                  'electrum.exchange_rate',
                  'electrum.icons_rc',
                  'electrum.mnemonic',
                  'electrum.pyqrnative',
                  'electrum.qrscanner',
                  'electrum.history_widget',
                  'electrum.simple_config',
                  'electrum.socks',
                  'electrum.bmp',
                  'electrum.msqr',
                  'electrum.util',
                  'electrum.bitcoin',
                  'electrum.deserialize',
                  'electrum.verifier',
                  'electrum.i18n'],
    description = "Lightweight Bitcoin Wallet",
    author = "thomasv",
    author_email = "thomasv@gitorious",
    license = "GNU GPLv3",
    url = "http://electrum-desktop.com",
    long_description = """Lightweight Bitcoin Wallet""" 
)


