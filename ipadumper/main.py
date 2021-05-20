# stdlib
from argparse import ArgumentParser
from importlib.metadata import metadata
from os import path

# internal
from ipadumper.appledl import AppleDL
from ipadumper.utils import itunes_info


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

    # Create parent subparser for with common arguments
    parent_parser = ArgumentParser(add_help=False)
    parent_parser.add_argument('--device_address', help='device address (default: %(default)s)', default='localhost')
    parent_parser.add_argument('--device_port', help='device port (default: %(default)s)', default='22222')
    parent_parser.add_argument('--ssh_key', help='Path to ssh keyfile (default: %(default)s)', default='iphone')

    # package dir +
    imagedir = path.join('appstore_images', 'dark_de')
    parent_parser.add_argument('--imagedir', help='Path to appstore images (default: %(default)s)', default=imagedir)
    parent_parser.add_argument(
        '--base_timeout',
        help='Base timeout for various things (default: %(default)s)',
        type=float,
        default=15,
        metavar='SECONDS',
    )

    # Subparsers based on parent

    # bulk_decrypt
    parser_bulk_decrypt = subparsers.add_parser(
        'bulk_decrypt', parents=[parent_parser], help='Installs apps, decrypts and uninstalls them'
    )
    parser_bulk_decrypt.add_argument('itunes_ids', help='File containing lines with iTunes IDs', metavar='PATH')
    parser_bulk_decrypt.add_argument('output', help='Output directory', metavar='PATH')
    parser_bulk_decrypt.add_argument(
        '--parallel', help='How many apps get installed in parallel (default: %(default)s)', type=int, default=3
    )
    parser_bulk_decrypt.add_argument(
        '--timeout_per_MiB', help='Timeout per MiB (default: %(default)s)', type=float, default=0.5, metavar='SECONDS'
    )

    # dump
    parser_dump = subparsers.add_parser('dump', parents=[parent_parser], help='Decrypts und dumps ipa package')
    parser_dump.add_argument('bundleID', help='Bundle ID from app like com.app.name')
    parser_dump.add_argument('output', help='Output filename', metavar='PATH')
    parent_parser.add_argument(
        '--timeout',
        help='Base timeout for various things (default: %(default)s)',
        type=float,
        default=120,
        metavar='SECONDS',
    )
    # ssh_cmd
    parser_ssh_cmd = subparsers.add_parser('ssh_cmd', parents=[parent_parser], help='Execute ssh command on device')
    parser_ssh_cmd.add_argument('command', help='command')

    # itunes_info
    parser_itunes_info = subparsers.add_parser('itunes_info', help='Downloads info about app from iTunes site')
    parser_itunes_info.add_argument('itunes_id', help='iTunes ID', type=int)

    # itunes_info
    parser_install = subparsers.add_parser(
        'install', help='Opens app in appstore on device and simulates touch input to download and install the app'
    )
    parser_install.add_argument('itunes_id', help='iTunes ID', type=int)

    args = parser.parse_args()
    print(vars(args))
    if args.command == 'help' or args.command is None:
        parser.print_help()
        exit()

    if args.command == 'itunes_info':
        itunes_info(args.itunes_id, log_level='debug')
    else:
        a = AppleDL(
            device_address=args.device_address,
            local_ssh_port=args.device_port,
            ssh_key_filename=args.ssh_key,
            image_base_path_local=args.imagedir,
            timeout=args.base_timeout,
            log_level=args.verbosity,
        )
        if not a.running:
            exit(1)
        if args.command == 'bulk_decrypt':
            with open(args.itunes_ids) as fp:
                itunes_ids = fp.read().splitlines()

            a.bulk_decrypt(
                itunes_ids, timeout_per_MiB=args.timeout_per_MiB, parallel=args.parallel, output_directory=args.output
            )
        elif args.command == 'dump':
            exitcode = a.dump(args.bundleID, args.output, args.timeout)
        elif args.command == 'ssh_cmd':
            exitcode, _, _ = a.ssh_cmd(args.command)
        elif args.command == 'install':
            exitcode = a.install(args.itunes_id)

        a.cleanup()

    exit(exitcode)

    def test():
        whatsapp = 310633997
        instagram = 389801252
        dualmessenger = 1530021020
        snapchat = 447188370
        # megaphoto = 471883260
        ids = [whatsapp, instagram, dualmessenger, snapchat]

        a = AppleDL(log_level='debug')
        a.wake_up_device()
        a.bulk_decrypt(ids)

        for t in a.dump_threads:
            print(f'found thread {t.name} waiting to finish')
            t.join()

        # print('success:', a.install(whatsapp))
        # time.sleep(10)
        # a.wake_up_device()
        # a.dump('net.whatsapp.WhatsApp', 'net.whatsapp.WhatsApp_ar4.ipa')
        # print(a.itunes_info(whatsapp))
        a.cleanup()
        # cmd = 'pwd && ls -l'
        # a.ssh_cmd(cmd)
        # a.itunes_info('')
        # bundleId = 'com.ookla.speedtest'
        # r = a.is_installed(bundleId)
        # print(f'{bundleId} installed?: {r}')

        # a03e9884e94d4f88a543f2d009854530e2f5270c  net.whatsapp.WhatsApp.ipa
