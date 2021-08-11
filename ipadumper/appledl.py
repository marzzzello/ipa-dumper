# stdlib
import os
import pathlib
import shutil
import signal
import subprocess
import tempfile
import threading
import time

# external
from cachetools import TTLCache  # dict with timout
from scp import SCPClient  # ssh copy directories
from tqdm import tqdm  # progress bar
from zxtouch import touchtypes, toasttypes
from zxtouch.client import zxtouch  # simulate touch input on device
import frida  # run scripts on device
import paramiko  # ssh

# internal
import ipadumper
from ipadumper.utils import get_logger, itunes_info, progress_helper, free_port


class AppleDL:
    '''
    Downloader instance for a single device
    On inititalization two iproxy process are started: one for ssh and one for zxtouch
    Then a ssh and a frida connection will get established and the template images are copied with scp to the device
    '''

    def __init__(
        self,
        udid=None,
        device_address='localhost',
        ssh_key_filename='iphone',
        local_ssh_port=0,
        local_zxtouch_port=0,
        image_base_path_device='/private/var/mobile/Library/ZXTouch/scripts/appstoredownload.bdl',
        image_base_path_local=os.path.join(os.path.dirname(ipadumper.__file__), 'appstore_images'),
        theme='dark',
        lang='en',
        timeout=15,
        log_level='info',
        init=True,
    ):
        self.udid = udid
        self.device_address = device_address
        self.ssh_key_filename = ssh_key_filename
        self.local_ssh_port = local_ssh_port
        self.local_zxtouch_port = local_zxtouch_port
        self.image_base_path_device = image_base_path_device
        self.image_base_path_local = image_base_path_local
        self.theme = theme
        self.lang = lang
        self.timeout = timeout
        self.log_level = log_level
        self.log = get_logger(log_level, name=__name__)

        signal.signal(signal.SIGINT, self.__signal_handler)
        signal.signal(signal.SIGTERM, self.__signal_handler)

        self.running = True
        self.processes = []
        # self.file_dict = {}
        self.installed_cached = TTLCache(maxsize=1, ttl=2)

        self.log.debug('Logging is set to debug')

        self.init_frida_done = False
        self.init_ssh_done = False
        self.init_zxtouch_done = False
        self.init_images_done = False

        if not self.device_connected():
            self.cleanup()
        elif init is True:
            if not self.init_all():
                self.cleanup()

    def __del__(self):
        if self.running:
            self.cleanup()

    def __signal_handler(self, signum, frame):
        self.log.info('Received exit signal')
        self.cleanup()

    def cleanup(self):
        self.log.debug('Clean up...')
        self.running = False

        self.log.info('Disconnecting from device')
        try:
            self.finished.set()
            self.device.disconnect()
            self.sshclient.close()
        except AttributeError:
            pass

        # close all processes
        for idx, p in enumerate(self.processes, start=1):
            self.log.debug(f'Stopping process {idx}/{len(self.processes)}')
            p.terminate()
            p.wait()

        # threads
        for t in threading.enumerate():
            if t.name != 'MainThread' and t.is_alive():
                self.log.debug(f'Running thread: {t.name}')
        self.log.debug('Clean up done')

    def init_all(self):
        '''
        return success
        '''
        if not self.init_frida() or not self.init_ssh() or not self.init_zxtouch or not self.init_images():
            return False
        return True

    def device_connected(self):
        '''
        return True if a device is available else return False
        '''
        if self.udid is None:
            returncode = subprocess.call(
                ['ideviceinfo'], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if returncode == 0:
                return True
            else:
                self.log.error('No device found')
                return False
        else:
            returncode = subprocess.call(
                ['ideviceinfo', '--udid', self.udid], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if returncode == 0:
                return True
            else:
                self.log.error(f'Device {self.udid} not found')
                return False

    def init_frida(self):
        '''
        set frida device
        return success
        '''
        try:
            if self.udid is None:
                self.frida_device = frida.get_usb_device()
            else:
                self.frida_device = frida.get_device(self.udid)
        except frida.InvalidArgumentError:
            self.log.error('No Frida USB device found')
            return False

        self.init_frida_done = True
        return True

    def init_ssh(self):
        '''
        Initializing SSH connection to device
        return success
        '''
        # start iproxy for SSH
        if self.local_ssh_port == 0:
            self.local_ssh_port = free_port()
        if self.udid is None:
            self.__run_cmd(['iproxy', str(self.local_ssh_port), '22'])
        else:
            self.__run_cmd(['iproxy', '--udid', self.udid, str(self.local_ssh_port), '22'])
        time.sleep(0.1)

        self.log.debug('Connecting to device via SSH')
        # pkey = paramiko.Ed25519Key.from_private_key_file(self.ssh_key_filename)
        self.sshclient = paramiko.SSHClient()
        # client.load_system_host_keys()
        self.sshclient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.sshclient.connect(
                'localhost', port=self.local_ssh_port, username='root', key_filename=self.ssh_key_filename
            )
        except FileNotFoundError:
            self.log.error(f'Could not find ssh keyfile "{self.ssh_key_filename}"')
            return False
        except (EOFError, ConnectionResetError, paramiko.ssh_exception.SSHException):
            self.log.error('Could not connect to establish SSH connection')
            return False

        self.init_ssh_done = True
        return True

    def init_zxtouch(self):
        # start iproxy for zxtouch
        if self.local_zxtouch_port == 0:
            self.local_zxtouch_port = free_port()
        if self.udid is None:
            self.__run_cmd(['iproxy', str(self.local_zxtouch_port), '6000'])
        else:
            self.__run_cmd(['iproxy', '--udid', self.udid, str(self.local_zxtouch_port), '6000'])

        self.log.info(f'Connecting to device at {self.device_address}:{self.local_zxtouch_port}')
        try:
            self.device = zxtouch(self.device_address, port=self.local_zxtouch_port)
        except ConnectionRefusedError:
            self.log.error('Error connecting to zxtouch on device. Make sure iproxy is running')
            self.cleanup()
            return False

        self.init_zxtouch_done = True
        return True

    def init_images(self):
        '''
        Copy template images from local folder to device
        return success
        '''

        # check directory structure
        try:
            _, dirnames_themes, _ = next(os.walk(self.image_base_path_local))
        except StopIteration:
            self.log.error(f'Image directory not found: {self.image_base_path_local}')
            return False
        theme_path = os.path.join(self.image_base_path_local, self.theme)
        lang_path = os.path.join(self.image_base_path_local, self.theme, self.lang)

        if self.theme in dirnames_themes:
            _, dirnames_langs, filenames_theme = next(os.walk(theme_path))
            if self.lang not in dirnames_langs:
                self.log.error(f'Language directory "{self.lang}" not found in {theme_path}')
                return False
        else:
            self.log.error(f'Theme directory "{self.theme}" not found in {self.image_base_path_local}')
            return False

        # check if all images exist locally
        image_names_unlabeled = ['cloud.png']
        image_names_labeled = ['dissallow.png', 'get.png', 'install.png']

        _, _, filenames_lang = next(os.walk(lang_path))
        for image_name_labeled in image_names_labeled:
            if image_name_labeled not in filenames_lang:
                self.log.error(f'Image {image_name_labeled} not found in {lang_path}')
                return False

        for image_name_unlabeled in image_names_unlabeled:
            if image_name_unlabeled not in filenames_theme:
                self.log.error(f'Image {image_name_unlabeled} not found in {theme_path}')
                return False

        # transfer images over SSH
        try:
            with SCPClient(self.sshclient.get_transport(), socket_timeout=self.timeout) as scp:
                for labeled_img in image_names_labeled:
                    scp.put(os.path.join(lang_path, labeled_img), self.image_base_path_device)
                for unlabeled_img in image_names_unlabeled:
                    unlabeled_img_path = os.path.join(theme_path, unlabeled_img)
                    scp.put(unlabeled_img_path, self.image_base_path_device)
        except OSError:
            self.log.error('Could not copy template images to device')
            return False

        self.init_images_done = True
        return True

    def ssh_cmd(self, cmd):
        '''
        execute command via ssh and iproxy
        return exitcode, stdout, stderr
        '''
        if not self.init_ssh_done:
            if not self.init_ssh():
                return 1, '', ''

        self.log.debug(f'Run ssh cmd: {cmd}')
        stdin, stdout, stderr = self.sshclient.exec_command(cmd)

        exitcode = stdout.channel.recv_exit_status()

        out = ''
        err = ''
        for line in stdout:
            out += line
        for line in stderr:
            err += line

        if exitcode != 0 or out != '' or err != '':
            self.log.debug(f'Exitcode: {exitcode}\nSTDOUT:\n{out}STDERR:\n{err}DONE')
        return exitcode, out, err

    def __log_cmd(self, pipe, err):
        with pipe:
            for line in iter(pipe.readline, b''):  # b'\n'-separated lines
                if err is True:
                    self.log.warning(f"got err line from subprocess: {line.decode('utf-8').rstrip()}")
                else:
                    self.log.info(f"got out line from subprocess: {line.decode('utf-8').rstrip()}")

        if err is True:
            self.log.debug('Terminating stderr output thread')
        else:
            self.log.debug('Terminating stdout output thread')

    def __run_cmd(self, cmd):
        '''
        Start external program and log stdout + stderr
        '''
        cmd_str = ' '.join(cmd)
        self.log.info(f'Starting: {cmd_str}')

        p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        # start logging threads: one for stderr and one for stdout
        t_out = threading.Thread(target=self.__log_cmd, args=(p.stdout, False))
        t_err = threading.Thread(target=self.__log_cmd, args=(p.stderr, True))

        self.processes.append(p)

        # t_out.daemon = True
        # t_err.daemon = True

        t_out.name = ' '.join(cmd[:3])  # + '-out'
        t_err.name = ' '.join(cmd[:3])  # + '-err'

        t_out.start()
        t_err.start()

    def __is_installed(self, bundleId):
        '''
        return version code if app is installed else return False
        '''
        try:
            out = self.installed_cached[0]
        except KeyError:
            if self.udid is None:
                out = subprocess.check_output(['ideviceinstaller', '-l'], encoding='utf-8')
            else:
                out = subprocess.check_output(['ideviceinstaller', '--udid', self.udid, '-l'], encoding='utf-8')
            # cache output
            self.installed_cached[0] = out

        for line in out.splitlines()[1:]:
            CFBundleIdentifier, CFBundleVersion, CFBundleDisplayName = line.split(', ')
            if CFBundleIdentifier == bundleId:
                version = CFBundleVersion.strip('"')
                displayName = CFBundleDisplayName.strip('"')
                self.log.debug(f'Found installed app {bundleId}: {version} ({displayName})')
                return version
        return False

    def __match_image(self, image_name, acceptable_value=0.9, max_try_times=1, scaleRation=1):
        '''
        get image from image_dir_device + image_name

        if matching return x,y coordinates from the middle
        else return False
        '''
        path = f'{self.image_base_path_device}/{image_name}'
        result_tuple = self.device.image_match(path, acceptable_value, max_try_times, scaleRation)

        if result_tuple[0] is not True:
            raise Exception(f'Error while matching {image_name}: {result_tuple[1]}')
        else:
            result_dict = result_tuple[1]
            width = int(float(result_dict['width']))
            height = int(float(result_dict['height']))
            x = int(float(result_dict['x']))
            y = int(float(result_dict['y']))
            if width != 0 and height != 0:
                middleX = x + (width // 2)
                middleY = y + (height // 2)
                self.log.debug(
                    f'Matched {image_name}: x,y: {x},{y}\t size: {width},{height}\t middle: {middleX},{middleY}'
                )
                return middleX, middleY
            else:
                self.log.debug(f'Match failed. Cannot find {image_name} on screen.')
                return False

    def __tap(self, xy, message=''):
        '''
        Simulate touch input (single tap) and show toast message on device
        '''
        x, y = xy
        self.log.debug(f'Tapping {xy} {message}')
        self.device.show_toast(toasttypes.TOAST_WARNING, f'{message} ({x},{y})', 1.5)
        self.device.touch(touchtypes.TOUCH_DOWN, 1, x, y)
        time.sleep(0.1)
        self.device.touch(touchtypes.TOUCH_UP, 1, x, y)

    def __wake_up_device(self):
        '''
        Normally not needed.
        Install (uiopen) wakes up device too
        '''
        self.log.info('Unlocking device if not awake..')
        self.ssh_cmd('activator send libactivator.system.homebutton')
        time.sleep(0.5)
        self.ssh_cmd('activator send libactivator.system.homebutton')
        time.sleep(0.5)

    def dump_fouldecrypt(self, target, output, timeout=120, disable_progress=False, copy=True):
        '''
        Dump IPA by using FoulDecrypt
        When copy is False, the app directory on the device is overwritten which is faster than copying everything
        Return success
        '''
        if not self.init_ssh_done:
            if not self.init_ssh():
                return False

        self.log.debug(f'{target}: Start dumping with FoulDecrypt.')

        # get path of app
        apps_dir = '/private/var/containers/Bundle/Application/'
        cmd = f'grep --only-matching {target} {apps_dir}*/iTunesMetadata.plist'
        ret, stdout, stderr = self.ssh_cmd(cmd)
        if ret != 0:
            self.log.error(f'grep returned {ret} {stderr}')
            return False

        target_dir = stdout.split('/iTunesMetadata.plist ')[0].split(' ')[-1]

        # get app directory name
        cmd = f'ls -d {target_dir}/*/'
        ret, stdout, stderr = self.ssh_cmd(cmd)
        if ret != 0:
            self.log.error(f'ls -d returned {ret} {stderr}')
            return False

        app_dir = stdout.strip().rstrip('/').split('/')[-1]
        if not app_dir.endswith('.app'):
            self.log.error(f'App directory does not end with .app: {app_dir}')
            return False

        app_bin = app_dir[:-4]

        if copy is True:
            orig_target_dir = target_dir
            target_dir = target_dir + '_tmp'
            cmd = f'cp -r {orig_target_dir} {target_dir}'
            ret, stdout, stderr = self.ssh_cmd(cmd)
            if ret != 0:
                self.log.error(f'cp -r returned {ret} {stderr}')
                return False

        bin_path = target_dir + '/' + app_dir + '/' + app_bin

        # decrypt binary and replace
        self.log.debug(f'{target}: Decrypting binary with fouldecrypt')
        cmd = f'/usr/local/bin/fouldecrypt -v {bin_path} {bin_path}'
        ret, stdout, stderr = self.ssh_cmd(cmd)
        if ret != 0:
            self.log.error(f'fouldecrypt returned {ret} {stderr}')
            return False

        # prepare for zipping, create Payload folder
        cmd = f'mkdir {target_dir}/Payload'
        ret, stdout, stderr = self.ssh_cmd(cmd)
        if ret != 0:
            self.log.error(f'mkdir returned {ret} {stderr}')
            return False

        cmd = f'mv {target_dir}/{app_dir} {target_dir}/Payload'
        ret, stdout, stderr = self.ssh_cmd(cmd)
        if ret != 0:
            self.log.error(f'mv returned {ret} {stderr}')
            return False

        self.log.debug(f'{target}: Set access and modified date to 0 for reproducible zip files')
        cmd = f'find {target_dir} -exec touch -m -d "1/1/1980" {{}} +'
        ret, stdout, stderr = self.ssh_cmd(cmd)
        if ret != 0:
            self.log.error(f'find+touch returned {ret} {stderr}')
            return False

        # zip
        self.log.debug(f'{target}: Creating zip')
        cmd = f'cd {target_dir} && zip -qrX out.zip . -i "Payload/*"'
        ret, stdout, stderr = self.ssh_cmd(cmd)
        if ret != 0:
            self.log.error(f'zip returned {ret} {stderr}')
            return False

        # transfer out.zip
        bar_fmt = '{desc:20.20} {percentage:3.0f}%|{bar:20}{r_bar}'
        self.log.debug(f'{target}: Start transfer. {output}')

        with tqdm(unit="B", unit_scale=True, miniters=1, bar_format=bar_fmt, disable=disable_progress) as t:
            pr = progress_helper(t)
            with SCPClient(self.sshclient.get_transport(), socket_timeout=self.timeout, progress=pr) as scp:
                scp.get(target_dir + '/out.zip', output)

        if copy is True:
            self.log.debug('Clean up temp directory on device')
            cmd = f'rm -rf {target_dir}'
            ret, stdout, stderr = self.ssh_cmd(cmd)
            if ret != 0:
                self.log.error(f'rm returned {ret} {stderr}')
                return False

        return True

    def dump_frida(
        self,
        target,
        output,
        timeout=120,
        disable_progress=False,
        dumpjs_path=os.path.join(os.path.dirname(ipadumper.__file__), 'dump.js'),
    ):

        '''
        target: Bundle identifier of the target app
        output: Specify name of the decrypted IPA
        dumpjs_path:  path to dump.js
        timeout: timeout in for dump to finish
        disable_progress: disable progress bars
        return success


        partly copied from
        https://github.com/AloneMonkey/frida-ios-dump/blob/9e75f6bca34f649aa6fcbafe464eca5d624784d6/dump.py

        MIT License

        Copyright (c) 2017 Alone_Monkey

        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.
        '''
        if not self.init_ssh_done:
            if not self.init_ssh():
                return False
        if not self.init_frida_done:
            if not self.init_frida():
                return False

        bar_fmt = '{desc:20.20} {percentage:3.0f}%|{bar:20}{r_bar}'
        temp_dir = tempfile.mkdtemp()
        self.log.debug(f'{target}: Start dumping with Frida. Temp dir: {temp_dir}')
        payload_dir = os.path.join(temp_dir, 'Payload')
        os.mkdir(payload_dir)

        self.finished = threading.Event()
        file_dict = {}

        def generate_ipa():
            self.log.debug(f'{target}: Generate ipa')
            for key, value in file_dict.items():
                from_dir = os.path.join(payload_dir, key)
                to_dir = os.path.join(payload_dir, file_dict['app'], value)
                if key != 'app':
                    # try:
                    #     cmp = filecmp.cmp(from_dir, to_dir)
                    # except FileNotFoundError:
                    #     print(f'new: {from_dir}')
                    # print(f'cmp is {cmp}, move {key} from {from_dir}  to  {to_dir}')
                    shutil.move(from_dir, to_dir)

            self.log.debug(f'{target}: Set access and modified date to 0 for reproducible zip files')
            for f in pathlib.Path(temp_dir).glob('**/*'):
                os.utime(f, (0, 0))

            zip_args = ('zip', '-qrX', os.path.join(os.getcwd(), output), 'Payload')
            self.log.debug(f'{target}: Run zip: {zip_args}')
            try:
                subprocess.check_call(zip_args, cwd=temp_dir)
            except subprocess.CalledProcessError as err:
                self.log.error(f'{target}: {zip_args} {str(err)}')

        def on_message(message, data):
            '''
            callback function for dump messages
            receives paths and copies them with scp
            '''
            t = threading.currentThread()
            t.name = f'msg-{target}'
            try:
                payload = message['payload']
            except KeyError:
                self.log.warning(f'{target}: No payload in message')
                self.log.debug(f'Message: {message}')
                return

            if 'info' in payload:
                self.log.debug(f"{target}: {payload['info']}")

            if 'warn' in payload:
                self.log.warning(f"{target}: {payload['warn']}")

            if 'dump' in payload:
                index = payload['path'].find('.app/') + 5
                file_dict[os.path.basename(payload['dump'])] = payload['path'][index:]

                with tqdm(unit="B", unit_scale=True, miniters=1, bar_format=bar_fmt, disable=disable_progress) as t:
                    pr = progress_helper(t)
                    with SCPClient(self.sshclient.get_transport(), socket_timeout=self.timeout, progress=pr) as scp:
                        scp.get(payload['dump'], payload_dir + '/')

                chmod_dir = os.path.join(payload_dir, os.path.basename(payload['dump']))
                chmod_args = ('chmod', '655', chmod_dir)
                try:
                    subprocess.check_call(chmod_args)
                except subprocess.CalledProcessError as err:
                    self.log.error(f'{target}: {chmod_args} {str(err)}')

            if 'app' in payload:
                with tqdm(unit="B", unit_scale=True, miniters=1, bar_format=bar_fmt, disable=disable_progress) as t:
                    pr = progress_helper(t)
                    with SCPClient(self.sshclient.get_transport(), socket_timeout=self.timeout, progress=pr) as scp:
                        scp.get(payload['app'], payload_dir + '/', recursive=True)

                chmod_dir = os.path.join(payload_dir, os.path.basename(payload['app']))
                chmod_args = ('chmod', '755', chmod_dir)
                try:
                    subprocess.check_call(chmod_args)
                except subprocess.CalledProcessError as err:
                    self.log.error(f'{target}: {chmod_args} {str(err)}')

                file_dict['app'] = os.path.basename(payload['app'])

            if 'done' in payload:
                self.finished.set()

        self.log.debug(f'{target}: Opening app')
        self.ssh_cmd(f'open {target}')
        time.sleep(0.1)

        # create frida session
        apps = self.frida_device.enumerate_applications()
        session = None
        for app in apps:
            if app.identifier == target:
                if app.pid == 0:
                    self.log.error(f'{target}: Could not start app')
                    return
                session = self.frida_device.attach(app.pid)

        # run script
        with open(dumpjs_path) as f:
            jsfile = f.read()
        script = session.create_script(jsfile)
        script.on('message', on_message)
        self.log.debug(f'{target}: Loading script')
        script.load()
        script.post('dump')

        success = False
        if self.finished.wait(timeout=timeout):
            if self.running:
                generate_ipa()
                self.log.debug(f'{target}: Dumping finished. Clean up temp dir {temp_dir}')

                success = True
            else:
                self.log.debug(f'{target}: Cancelling dump. Clean up temp dir {temp_dir}')
        else:
            self.log.error(f'{target}: Timeout of {timeout}s exceeded. Clean up temp dir {temp_dir}')

        shutil.rmtree(temp_dir)

        if session:
            session.detach()
        return success

    def bulk_decrypt(self, itunes_ids, timeout_per_MiB=0.5, parallel=3, output_directory='ipa_output', country='us'):
        '''
        Installs apps, decrypts and uninstalls them
        In parallel!
        itunes_ids: list of int with the iTunes IDs
        '''
        if type(itunes_ids[0]) != int:
            self.log.error('bulk_decrypt: list of int needed')
            return False
        total = len(itunes_ids)
        wait_for_install = []  # apps that are currently downloading and installing
        done = []  # apps that are uninstalled
        waited_time = 0
        while len(itunes_ids) > 0 or len(wait_for_install) > 0:
            self.log.debug(f'Done {len(done)}/{total}, installing: {len(wait_for_install)}')
            if len(itunes_ids) > 0 and len(wait_for_install) < parallel:
                # install app
                self.log.info(f'Installing, len: {len(wait_for_install)}')

                itunes_id = itunes_ids.pop()
                trackName, version, bundleId, fileSizeMiB, price, currency = itunes_info(
                    itunes_id, log_level=self.log_level, country=country
                )
                app = {'bundleId': bundleId, 'fileSizeMiB': fileSizeMiB, 'itunes_id': itunes_id, 'version': version}

                if price != 0:
                    self.log.warning(f'{bundleId}: Skipping, app is not for free ({price} {currency})')
                    continue

                if self.__is_installed(bundleId) is not False:
                    self.log.info(f'{bundleId}: Skipping, app already installed')
                    total -= 1
                    # subprocess.check_output(['ideviceinstaller', '--uninstall', bundleId])
                    continue

                wait_for_install.append(app)
                self.install(itunes_id)
                self.log.info(f'{bundleId}: Waiting for download and installation to finish ({fileSizeMiB} MiB)')
            else:
                # check if an app installation has finished
                # if yes then dump app else wait for an install to finish
                # also check if a dump has finished. If yes then uninstall app

                install_finished = False
                to_download_size = 0
                for app in wait_for_install:
                    if self.__is_installed(app['bundleId']) is not False:
                        # dump app

                        self.log.info(
                            f"{app['bundleId']}: Download and installation finished. Opening app and starting dump"
                        )
                        install_finished = True
                        waited_time = 0
                        # waited_time -= app['fileSizeMiB'] * timeout_per_MiB
                        # if waited_time < 0:
                        #     waited_time = 0
                        wait_for_install.remove(app)

                        try:
                            os.mkdir(output_directory)
                        except FileExistsError:
                            pass

                        name = f"{app['itunes_id']}_{app['bundleId']}_{app['version']}.ipa"
                        output = os.path.join(output_directory, name)
                        timeout = self.timeout + app['fileSizeMiB'] // 2
                        disable_progress = False if self.log_level == 'debug' else True

                        self.dump_frida(app['bundleId'], output, timeout=timeout, disable_progress=disable_progress)
                        # uninstall app after dump
                        self.log.info(f"{app['bundleId']}: Uninstalling")
                        if self.udid is None:
                            subprocess.check_output(['ideviceinstaller', '--uninstall', app['bundleId']])
                        else:
                            subprocess.check_output(
                                ['ideviceinstaller', '--udid', self.udid, '--uninstall', app['bundleId']]
                            )
                        done.append(app)
                    else:
                        # recalculate remaining download size
                        to_download_size += app['fileSizeMiB']

                # wait for an app to finish installation
                if install_finished is False:
                    self.log.debug(f'Need to download {to_download_size} MiB')
                    if waited_time > self.timeout + timeout_per_MiB * to_download_size:
                        self.log.error(
                            f'Timeout exceeded. Waited time: {waited_time}. Need to download: {to_download_size} MiB'
                        )
                        self.log.debug(f'Wait for install queue: {wait_for_install}')
                        return False
                    else:
                        waited_time += 1
                        time.sleep(1)

    def install(self, itunes_id):
        '''
        Opens app in appstore on device and simulates touch input to download and installs the app.
        If there is a cloud button then press that and done
        Else if there is a load button, press that and confirm with install button.
        return success
        '''
        if not self.init_images_done:
            if not self.init_images():
                return False
        if not self.init_zxtouch_done:
            if not self.init_zxtouch():
                return False
        # get rid of permission request popups
        while True:
            dissallow_xy = self.__match_image('dissallow.png')
            if dissallow_xy is not False:
                self.log.debug('Dissallow permission request')
                self.__tap(dissallow_xy, message='dissallow')
                time.sleep(0.1)
            else:
                break

        self.ssh_cmd(f'uiopen https://apps.apple.com/de/app/id{str(itunes_id)}')

        self.log.debug(f'ID {itunes_id}: Waiting for get or cloud button to appear')
        dl_btn_wait_time = 0
        while dl_btn_wait_time <= self.timeout:
            dl_btn_wait_time += 1
            time.sleep(1)
            dl_btn_xy = self.__match_image('get.png')
            if dl_btn_xy is False:
                dl_btn_xy = self.__match_image('cloud.png')
                if dl_btn_xy is False:
                    continue
                else:
                    # tap and done
                    self.__tap(dl_btn_xy, 'cloud')
                    return True
            else:
                self.__tap(dl_btn_xy, 'get')
                break

        if dl_btn_wait_time > self.timeout:
            self.log.warning(f'ID {itunes_id}: No download button found after {self.timeout}s')
            return False

        # tap and need to wait and confirm with install button
        self.__tap(dl_btn_xy, 'load')
        self.log.debug(f'ID {itunes_id}: Waiting for install button to appear')
        install_btn_wait_time = 0
        while install_btn_wait_time <= self.timeout:
            install_btn_wait_time += 1
            time.sleep(1)
            install_btn_xy = self.__match_image('install.png')
            if install_btn_xy is not False:
                self.__tap(install_btn_xy, 'install')
                return True

        self.log.warning(f'ID {itunes_id}: No install button found after {self.timeout}s')
        return False
