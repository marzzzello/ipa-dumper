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
- Install ipadumper with `pip install ipa_dumper`
- Run `ipadumper help`

## Usage

```
usage: ipadumper [-h] [-v {warning,info,debug}]
                 {help,usage,itunes_info,bulk_decrypt,dump,ssh_cmd,install}
                 ...

Automatically install apps on a jailbroken device iOS device and generate a
decrypted ipa packages

positional arguments:
  {help,usage,itunes_info,bulk_decrypt,dump,ssh_cmd,install}
                        Desired action to perform
    help                Print this help message
    usage               Print full usage
    itunes_info         Downloads info about app from iTunes site
    bulk_decrypt        Installs apps, decrypts and uninstalls them
    dump                Decrypts und dumps ipa package
    ssh_cmd             Execute ssh command on device
    install             Opens app in appstore on device and simulates touch
                        input to download and install the app

optional arguments:
  -h, --help            show this help message and exit
  -v {warning,info,debug}, --verbosity {warning,info,debug}
                        Set verbosity level (default: info)


All commands in detail:
itunes_info:
usage: ipadumper itunes_info [-h] itunes_id

Downloads info about app from iTunes site

positional arguments:
  itunes_id   iTunes ID

optional arguments:
  -h, --help  show this help message and exit


Common optional arguments for bulk_decrypt, dump, ssh_cmd, install:
  --device_address HOSTNAME  device address (default: localhost)
  --device_port PORT         device port (default: 22222)
  --ssh_key PATH             Path to ssh keyfile (default: iphone)
  --imagedir PATH            Path to appstore images (default:
                             /home/marcel/.local/lib/python3.9/site-
                             packages/ipadumper/appstore_images/dark_de)
  --base_timeout SECONDS     Base timeout for various things (default: 15)


bulk_decrypt:
usage: ipadumper bulk_decrypt [-h] [--device_address HOSTNAME]
                              [--device_port PORT] [--ssh_key PATH]
                              [--imagedir PATH] [--base_timeout SECONDS]
                              [--parallel PARALLEL]
                              [--timeout_per_MiB SECONDS]
                              itunes_ids output

Installs apps, decrypts and uninstalls them

positional arguments:
  itunes_ids                 File containing lines with iTunes IDs
  output                     Output directory

optional arguments:
                             /home/marcel/.local/lib/python3.9/site-
                             packages/ipadumper/appstore_images/dark_de)
  --parallel PARALLEL        How many apps get installed in parallel (default:
                             3)
  --timeout_per_MiB SECONDS  Timeout per MiB (default: 0.5)


dump:
usage: ipadumper dump [-h] [--device_address HOSTNAME] [--device_port PORT]
                      [--ssh_key PATH] [--imagedir PATH]
                      [--base_timeout SECONDS] [--timeout SECONDS]
                      bundleID PATH

Decrypts und dumps ipa package

positional arguments:
  bundleID                   Bundle ID from app like com.app.name
  PATH                       Output filename

optional arguments:
                             /home/marcel/.local/lib/python3.9/site-
                             packages/ipadumper/appstore_images/dark_de)
  --timeout SECONDS          Frida dump timeout (default: 120)


ssh_cmd:
usage: ipadumper ssh_cmd [-h] [--device_address HOSTNAME] [--device_port PORT]
                         [--ssh_key PATH] [--imagedir PATH]
                         [--base_timeout SECONDS]
                         command

Execute ssh command on device

positional arguments:
  command                    command

optional arguments:
                             /home/marcel/.local/lib/python3.9/site-
                             packages/ipadumper/appstore_images/dark_de)


install:
usage: ipadumper install [-h] [--device_address HOSTNAME] [--device_port PORT]
                         [--ssh_key PATH] [--imagedir PATH]
                         [--base_timeout SECONDS]
                         itunes_id

Opens app in appstore on device and simulates touch input to download and
install the app

positional arguments:
  itunes_id                  iTunes ID

optional arguments:
                             /home/marcel/.local/lib/python3.9/site-
                             packages/ipadumper/appstore_images/dark_de)
```
