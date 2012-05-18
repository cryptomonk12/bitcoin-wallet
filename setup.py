#!/usr/bin/python

# python setup.py sdist --format=zip,gztar

from distutils.core import setup
from lib.version import ELECTRUM_VERSION as version

setup(name = "Electrum",
    version = version,
    install_requires = ['slowaes','ecdsa'],
    package_dir = {'electrum': 'lib'},
    scripts= ['electrum'],
    data_files=[
          ('/usr/share/app-install/icons/',['electrum.png']),
          ('/usr/share/locale/de/LC_MESSAGES', ['locale/de/LC_MESSAGES/electrum.mo']),
          ('/usr/share/locale/fr/LC_MESSAGES', ['locale/fr/LC_MESSAGES/electrum.mo']),
          ('/usr/share/locale/si/LC_MESSAGES', ['locale/si/LC_MESSAGES/electrum.mo']),
          ],
    py_modules = ['electrum.version',
                  'electrum.wallet',
                  'electrum.interface',
                  'electrum.gui',
                  'electrum.gui_qt',
                  'electrum.icons_rc',
                  'electrum.mnemonic',
                  'electrum.pyqrnative',
                  'electrum.bmp',
                  'electrum.i18n'],
    description = "Lightweight Bitcoin Wallet",
    author = "thomasv",
    license = "GNU GPLv3",
    url = "http://ecdsa/electrum",
    long_description = """Lightweight Bitcoin Wallet""" 
)

if __name__ == '__main__':
    import sys,os
    if len(sys.argv)>1 and sys.argv[1]=='install':
        cmd = "sudo desktop-file-install electrum.desktop"
        try:
            print cmd
            os.system(cmd)
        except:
            pass



