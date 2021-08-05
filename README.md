![](https://forthebadge.com/images/badges/built-with-love.svg)
![](https://forthebadge.com/images/badges/fuck-it-ship-it.svg)
![](https://forthebadge.com/images/badges/contains-Cat-GIFs.svg)

[![Repo on GitLab](https://img.shields.io/badge/repo-GitLab-fc6d26.svg?style=for-the-badge&logo=gitlab)](https://gitlab.com/marzzzello/ipa-dumper)
[![Repo on GitHub](https://img.shields.io/badge/repo-GitHub-4078c0.svg?style=for-the-badge&logo=github)](https://github.com/marzzzello/ipa-dumper)
[![license](https://img.shields.io/github/license/marzzzello/ipa-dumper.svg?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwYXRoIHN0eWxlPSJmaWxsOiNkZGRkZGQiIGQ9Ik03IDRjLS44MyAwLTEuNS0uNjctMS41LTEuNVM2LjE3IDEgNyAxczEuNS42NyAxLjUgMS41UzcuODMgNCA3IDR6bTcgNmMwIDEuMTEtLjg5IDItMiAyaC0xYy0xLjExIDAtMi0uODktMi0ybDItNGgtMWMtLjU1IDAtMS0uNDUtMS0xSDh2OGMuNDIgMCAxIC40NSAxIDFoMWMuNDIgMCAxIC40NSAxIDFIM2MwLS41NS41OC0xIDEtMWgxYzAtLjU1LjU4LTEgMS0xaC4wM0w2IDVINWMwIC41NS0uNDUgMS0xIDFIM2wyIDRjMCAxLjExLS44OSAyLTIgMkgyYy0xLjExIDAtMi0uODktMi0ybDItNEgxVjVoM2MwLS41NS40NS0xIDEtMWg0Yy41NSAwIDEgLjQ1IDEgMWgzdjFoLTFsMiA0ek0yLjUgN0wxIDEwaDNMMi41IDd6TTEzIDEwbC0xLjUtMy0xLjUgM2gzeiIvPjwvc3ZnPgo=)](LICENSE.md)
[![commit-activity](https://img.shields.io/github/commit-activity/m/marzzzello/ipa-dumper.svg?style=for-the-badge)](https://img.shields.io/github/commit-activity/m/marzzzello/ipa-dumper.svg?style=for-the-badge)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/103207?domain=https%3A%2F%2Fsocial.tchncs.de&logo=mastodon&style=for-the-badge)](https://social.tchncs.de/@marzzzello)

# ipa-dumper

Automatically install apps on a jailbroken device iOS device and generate decrypted IPAs

## Requirements

- Linux device (tested on Arch Linux) with Python 3.7+
- Jailbroken iOS device (tested on iPhone 6s, iOS 14.2)

## Setup

### iOS device

- Set device language to German and theme to dark or **alternativly** make a folder with images of the buttons of your language and theme
- Disable password prompt for installing free apps under settings (Apple account -> Media & Purchases -> Password Settings).
- Connect the device to your computer and make sure to accept the trust dialog
- Install the following packages from Cydia:
  - OpenSSH
  - Open for iOS 11
  - Frida from https://build.frida.re
  - FoulDecrypt from https://repo.misty.moe/apt
  - NoAppThinning from https://n3d1117.github.io
  - ZXTouch from https://zxtouch.net

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
    dump                Decrypt app binary und dump IPA
    ssh_cmd             Execute ssh command on device
    install             Opens app in appstore on device and simulates touch
                        input to download and installs the app

optional arguments:
  -h, --help            show this help message and exit
  -v {warning,info,debug}, --verbosity {warning,info,debug}
                        Set verbosity level (default: info)


All commands in detail:
itunes_info:
usage: ipadumper itunes_info [-h] [--country COUNTRY] itunes_id

Downloads info about app from iTunes site

positional arguments:
  itunes_id          iTunes ID

optional arguments:
  -h, --help         show this help message and exit
  --country COUNTRY  Two letter country code (default: us)


Common optional arguments for bulk_decrypt, dump, ssh_cmd, install:
optional arguments:
  --device_address HOSTNAME  device address (default: localhost)
  --device_port PORT         device port (default: 22222)
  --ssh_key PATH             Path to ssh keyfile (default: iphone)
  --imagedir PATH            Path to appstore images (default:
                             $HOME/.local/lib/python3.9/site-
                             packages/ipadumper/appstore_images)
  --theme THEME              Theme of device dark/light (default: dark)
  --lang LANG                Language of device (2 letter code) (default: en)
  --udid UDID                UDID (Unique Device Identifier) of device
                             (default: None)
  --base_timeout SECONDS     Base timeout for various things (default: 15)


bulk_decrypt:
usage: ipadumper bulk_decrypt [-h] [--device_address HOSTNAME]
                              [--device_port PORT] [--ssh_key PATH]
                              [--imagedir PATH] [--theme THEME] [--lang LANG]
                              [--udid UDID] [--base_timeout SECONDS]
                              [--parallel PARALLEL]
                              [--timeout_per_MiB SECONDS] [--country COUNTRY]
                              itunes_ids output

Installs apps, decrypts and uninstalls them

positional arguments:
  itunes_ids                 File containing lines with iTunes IDs
  output                     Output directory

optional arguments:
  --theme THEME              Theme of device dark/light (default: dark)
  --lang LANG                Language of device (2 letter code) (default: en)
  --udid UDID                UDID (Unique Device Identifier) of device
                             (default: None)
  --parallel PARALLEL        How many apps get installed in parallel (default:
                             3)
  --timeout_per_MiB SECONDS  Timeout per MiB (default: 0.5)
  --country COUNTRY          Two letter country code (default: us)


dump:
usage: ipadumper dump [-h] [--device_address HOSTNAME] [--device_port PORT]
                      [--ssh_key PATH] [--imagedir PATH] [--theme THEME]
                      [--lang LANG] [--udid UDID] [--base_timeout SECONDS]
                      [--frida] [--timeout SECONDS]
                      bundleID PATH

Decrypt app binary und dump IPA

positional arguments:
  bundleID                   Bundle ID from app like com.app.name
  PATH                       Output filename

optional arguments:
  --theme THEME              Theme of device dark/light (default: dark)
  --lang LANG                Language of device (2 letter code) (default: en)
  --udid UDID                UDID (Unique Device Identifier) of device
                             (default: None)
  --frida                    Use Frida instead of FoulDecrypt (default: False)
  --timeout SECONDS          Dump timeout (default: 120)


ssh_cmd:
usage: ipadumper ssh_cmd [-h] [--device_address HOSTNAME] [--device_port PORT]
                         [--ssh_key PATH] [--imagedir PATH] [--theme THEME]
                         [--lang LANG] [--udid UDID] [--base_timeout SECONDS]
                         cmd

Execute ssh command on device

positional arguments:
  cmd                        command

optional arguments:
  --theme THEME              Theme of device dark/light (default: dark)
  --lang LANG                Language of device (2 letter code) (default: en)
  --udid UDID                UDID (Unique Device Identifier) of device
                             (default: None)


install:
usage: ipadumper install [-h] [--device_address HOSTNAME] [--device_port PORT]
                         [--ssh_key PATH] [--imagedir PATH] [--theme THEME]
                         [--lang LANG] [--udid UDID] [--base_timeout SECONDS]
                         itunes_id

Opens app in appstore on device and simulates touch input to download and
installs the app

positional arguments:
  itunes_id                  iTunes ID

optional arguments:
  --theme THEME              Theme of device dark/light (default: dark)
  --lang LANG                Language of device (2 letter code) (default: en)
  --udid UDID                UDID (Unique Device Identifier) of device
                             (default: None)
```
