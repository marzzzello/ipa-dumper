# Requirements:

# ipa-dumper

Automatically install apps on a jailbroken device iOS device and generate a decrypted ipa packages

## Requirements

- Linux device (tested on Arch Linux) with Python 3.7+
- Jailbroken iOS device (tested on iPhone 6s, iOS 14.2)

## Setup

### iOS device

- Set device language to German and theme to dark or **alternativly** make a folder with images of the buttons of your language and theme
- Connect the device to your computer and make sure to accept the trust dialog
- Install the following packages from Cydia:
  - OpenSSH
  - Open for iOS 11
  - Frida from https://build.frida.re
  - NoAppThinning from https://n3d1117.github.io
  - ZXTouch from https://zxtouch.net
- not needed

  - Activator from https://rpetri.ch/repo
  - AutoTouch
  - bfdecrypt from https://level3tjg.xyz/repo/
  - plutil

### Linux device

- connect to iOS device via USB
- Setup OpenSSH (needs to work with keyfile):

  - run `ssh-keygen -t ed25519 -f iphone`
  - run `iproxy 22 22222`
  - run `ssh-copy-id -p 22222 -i iphone root@localhost` (default password is `alpine`)

- Install [ideviceinstaller](https://github.com/libimobiledevice/ideviceinstaller) (this should also install iproxy/libusbmuxd as requirement)
- Install ipa_dumper with `pip install ipa_dumper`
- Run `ipa_dumper --help`

## Usage

TODO
