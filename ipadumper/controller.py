import os

import commentjson

import ipadumper
from ipadumper.appledl import AppleDL
from ipadumper.utils import itunes_info, get_logger


class MultiDevice:
    '''
    Mass downloading and dumping with multiple devices
    '''

    def __init__(self, config_file, itunes_ids_file, log_level='info'):
        self.log_level = log_level
        self.log = get_logger(log_level, name=__name__)

        try:
            with open(config_file) as f:
                self.config = commentjson.load(f)
            with open(itunes_ids_file) as f:
                self.itunes_ids = f
        except FileNotFoundError:
            self.log.error(f'File {config_file} not found')
            return

        default = self.config['default']

        devices = []
        for device in self.config['devices']:
            for key in default:
                device[key] = device.get(key, default[key])
            devices.append(device)

        self.log.debug(commentjson.dumps(devices, indent=2))

        countries = set()
        for device in devices:
            try:
                name = device['name']
                udid = device['udid']
                address = device['address']
                local_ssh_port = device['local_ssh_port']
                ssh_key_filename = device['ssh_key_filename']
                local_zxtouch_port = device['local_zxtouch_port']
                image_base_path_device = device['image_base_path_device']
                image_base_path_local = device['image_base_path_local']
                theme = device['theme']
                lang = device['lang']
                timeout = device['timeout']
                log_level = device['log_level']

                country = device['country']
                parallel = device['parallel']
                timeout_per_MiB = device['timeout_per_MiB']
                output_directory = device['output_directory']
            except KeyError as e:
                self.log.error(f'Config entry {str(e)} is missing')
                return

            countries.add(country)

            if image_base_path_local == '':
                image_base_path_local = os.path.join(os.path.dirname(ipadumper.__file__), 'appstore_images')

            if udid == '' and len(devices) > 1:
                self.log.error('Please specify UDID when multiple devices are used')
                return

            self.log.warning('Not implemented')
            return
            # TODO

            self.log.info(f'Initialising device {name}...')
            AppleDL(
                udid=udid,
                device_address=address,
                local_ssh_port=local_ssh_port,
                ssh_key_filename=ssh_key_filename,
                local_zxtouch_port=local_zxtouch_port,
                image_base_path_device=image_base_path_device,
                image_base_path_local=image_base_path_local,
                theme=theme,
                lang=lang,
                timeout=timeout,
                log_level=log_level,
            )
        for itunes_id in itunes_ids:
            info
            for country in countries:
                itunes_info(intunes_id, country)
