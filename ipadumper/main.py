# stdlib
from argparse import ArgumentParser, HelpFormatter
from importlib.metadata import metadata
from os import path

# internal
import ipadumper
from ipadumper.appledl import AppleDL
from ipadumper.utils import itunes_info
from ipadumper.controller import MultiDevice


class F(HelpFormatter):
    def __init__(self, *args, **kwargs):
        kwargs['max_help_position'] = 30
        super().__init__(*args, **kwargs)


def main():
    parser = ArgumentParser(description=metadata(__package__)['Summary'])
    parser.add_argument(
        '-v',
        '--verbosity',
        help='Set verbosity level (default: %(default)s)',
        choices=['warning', 'info', 'debug'],
        default='info',
    )
    subparsers = parser.add_subparsers(help='Desired action to perform', dest='command')

    # help
    subparsers.add_parser('help', help='Print this help message')

    # usage
    subparsers.add_parser('usage', help='Print full usage')

    # itunes_info
    d = 'Downloads info about app from iTunes site'
    parser_itunes_info = subparsers.add_parser('itunes_info', help=d, description=d)
    parser_itunes_info.add_argument('itunes_id', help='iTunes ID', type=int)
    parser_itunes_info.add_argument('--country', help='Two letter country code (default: %(default)s)', default='us')

    # multi dump
    d = 'Download, install,dump and uninstall apps using multiple devices in parallel'
    parser_itunes_info = subparsers.add_parser('multidump', help=d, description=d)
    parser_itunes_info.add_argument('config_file', help='config file', default='config.json', metavar='PATH')

    # Create parent subparser for with common arguments
    parent_parser = ArgumentParser(add_help=False, formatter_class=F)
    parent_parser.add_argument(
        '--device_address', help='device address (default: %(default)s)', default='localhost', metavar='HOSTNAME'
    )
    parent_parser.add_argument(
        '--local_ssh_port',
        help='local port to be forwarded to SSH on the device. 0 means random free port (default: %(default)s)',
        default=0,
        type=int,
        metavar='PORT',
    )
    parent_parser.add_argument(
        '--local_zxtouch_port',
        help='local port to be forwarded to ZXTouch on the device. 0 means random free port (default: %(default)s)',
        default=0,
        type=int,
        metavar='PORT',
    )
    parent_parser.add_argument(
        '--ssh_key', help='Path to ssh keyfile (default: %(default)s)', default='iphone', metavar='PATH'
    )
    imagedir = path.join(path.dirname(ipadumper.__file__), 'appstore_images')
    parent_parser.add_argument(
        '--imagedir', help='Path to appstore images (default: %(default)s)', default=imagedir, metavar='PATH'
    )
    parent_parser.add_argument('--theme', help='Theme of device dark/light (default: %(default)s)', default='dark')
    parent_parser.add_argument('--lang', help='Language of device (2 letter code) (default: %(default)s)', default='en')
    parent_parser.add_argument(
        '--udid', help='UDID (Unique Device Identifier) of device (default: %(default)s)', default=None, metavar='UDID'
    )
    parent_parser.add_argument(
        '--base_timeout',
        help='Base timeout for various things (default: %(default)s)',
        type=float,
        default=15,
        metavar='SECONDS',
    )

    # Subparsers based on parent

    # bulk_decrypt
    d = 'Installs apps, decrypts and uninstalls them'
    parser_bulk_decrypt = subparsers.add_parser(
        'bulk_decrypt', parents=[parent_parser], help=d, description=d, formatter_class=F
    )
    parser_bulk_decrypt.add_argument('itunes_ids', help='File containing lines with iTunes IDs')
    parser_bulk_decrypt.add_argument('output', help='Output directory')
    parser_bulk_decrypt.add_argument(
        '--parallel', help='How many apps get installed in parallel (default: %(default)s)', type=int, default=3
    )
    parser_bulk_decrypt.add_argument(
        '--timeout_per_MiB', help='Timeout per MiB (default: %(default)s)', type=float, default=0.5, metavar='SECONDS'
    )
    parser_bulk_decrypt.add_argument('--country', help='Two letter country code (default: %(default)s)', default='us')

    # dump
    d = 'Decrypt app binary und dump IPA'
    parser_dump = subparsers.add_parser('dump', parents=[parent_parser], help=d, description=d, formatter_class=F)
    parser_dump.add_argument('bundleID', help='Bundle ID from app like com.app.name')
    parser_dump.add_argument('output', help='Output filename', metavar='PATH')
    parser_dump.add_argument(
        '--frida', help='Use Frida instead of FoulDecrypt (default: %(default)s)', action='store_true'
    )
    parser_dump.add_argument(
        '--nocopy',
        help='FoulDecrypt: decrypt and package inplace without copying '
        + '(faster but app is broken afterwards) (default: %(default)s)',
        action='store_true',
    )
    parser_dump.add_argument(
        '--timeout',
        help='Dump timeout (default: %(default)s)',
        type=float,
        default=120,
        metavar='SECONDS',
    )
    # ssh_cmd
    d = 'Execute ssh command on device'
    parser_ssh_cmd = subparsers.add_parser('ssh_cmd', parents=[parent_parser], help=d, description=d, formatter_class=F)
    parser_ssh_cmd.add_argument('cmd', help='command')

    # install
    d = 'Opens app in appstore on device and simulates touch input to download and installs the app'
    parser_install = subparsers.add_parser('install', parents=[parent_parser], help=d, description=d, formatter_class=F)
    parser_install.add_argument('itunes_id', help='iTunes ID', type=int)

    args = parser.parse_args()
    # print(vars(args))

    if args.command == 'help' or args.command is None:
        parser.print_help()
        exit()

    if args.command == 'usage':
        parser.print_help()
        print('\n\nAll commands in detail:\nitunes_info:')
        parser_itunes_info.print_help()

        parentsubparsers = [parser_bulk_decrypt, parser_dump, parser_ssh_cmd, parser_install]
        commonargs = ['-h, --help', '--device_address', '--local_ssh_port', '--ssh_key', '--imagedir', '--base_timeout']
        parentsubparsers_str = []
        for p in parentsubparsers:
            parentsubparsers_str.append(p.prog.split(' ')[1])

        print(f'\n\nCommon optional arguments for {", ".join(parentsubparsers_str)}:')
        print('\n'.join(parent_parser.format_help().splitlines()[4:]))
        match = f'(default: {imagedir})'
        for p, p_str in zip(parentsubparsers, parentsubparsers_str):
            h = p.format_help()
            hn = ''
            for line in h.splitlines():
                add = True
                for arg in commonargs:
                    if line.lstrip().startswith(arg) or (line.lstrip() != '' and line.lstrip() in match):
                        add = False
                if add:
                    hn += line + '\n'
            hn = hn.rstrip('optional arguments:\n')
            print(f"\n\n{p_str}:\n{hn}")
        exit()
    exitcode = 0
    if args.command == 'itunes_info':
        itunes_info(args.itunes_id, log_level='debug', country=args.country)
    elif args.command == 'multidump':
        MultiDevice(args.config_file, log_level=args.verbosity)
    else:
        a = AppleDL(
            udid=args.udid,
            device_address=args.device_address,
            ssh_key_filename=args.ssh_key,
            local_ssh_port=args.local_ssh_port,
            local_zxtouch_port=args.local_zxtouch_port,
            image_base_path_local=args.imagedir,
            theme=args.theme,
            lang=args.lang,
            timeout=args.base_timeout,
            log_level=args.verbosity,
            init=False,
        )
        if not a.running:
            exit(1)
        if args.command == 'bulk_decrypt':
            if a.init_all():
                with open(args.itunes_ids) as fp:
                    itunes_ids = fp.read().splitlines()
                itunes_ids = [int(i) for i in itunes_ids]

                a.bulk_decrypt(
                    itunes_ids,
                    timeout_per_MiB=args.timeout_per_MiB,
                    parallel=args.parallel,
                    output_directory=args.output,
                )
        elif args.command == 'dump':
            if args.frida:
                exitcode = a.dump_frida(args.bundleID, args.output, args.timeout)
            else:
                exitcode = a.dump_fouldecrypt(args.bundleID, args.output, args.timeout, copy=not args.nocopy)
        elif args.command == 'ssh_cmd':
            exitcode, stdout, stderr = a.ssh_cmd(args.cmd)
            print(stdout)
            print(stderr)
        elif args.command == 'install':
            exitcode = a.install(args.itunes_id)

        a.cleanup()

    exit(exitcode)
