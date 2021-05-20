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
from ipadumper import utils


class AppleDL:
    def __init__(
        self,
        device_address='localhost',
        local_ssh_port=22222,
        ssh_key_filename='iphone',
        image_base_path_device='/private/var/mobile/Library/ZXTouch/scripts/appstoredownload.bdl',
        image_base_path_local=os.path.join('appstore_images', 'dark_de'),
        timeout=15,
        log_level='info',
    ):
        self.device_address = device_address
        self.local_ssh_port = local_ssh_port
        self.ssh_key_filename = ssh_key_filename
        self.image_base_path_device = image_base_path_device
        self.image_base_path_local = image_base_path_local
        self.timeout = timeout
        self.log_level = log_level
        self.log = utils.get_logger(log_level, name=__name__)

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.running = True
        self.processes = []
        self.dump_threads = []
        # self.file_dict = {}
        self.installed_cached = TTLCache(maxsize=1, ttl=2)

        self.log.debug('Logging is set to debug')
        self.run_cmd(['iproxy', str(self.local_ssh_port), '22'])
        self.run_cmd(['iproxy', '6000', '6000'])

        self.log.info(f'Connecting to device at {device_address}:6000')
        try:
            self.device = zxtouch(device_address)
        except ConnectionRefusedError:
            self.log.error('Error connecting to device. Make sure iproxy is running')
            self.cleanup()
            return

        if not self.init_ssh() or not self.init_frida() or not self.init_images():
            self.cleanup()

    def __del__(self):
        if self.running:
            self.cleanup()

    def signal_handler(self, signum, frame):
        self.log.info('Received exit signal')
        self.cleanup()

    def cleanup(self):
        self.log.debug('Clean up...')
        self.log.info('Disconnecting from device')
        try:
            self.device.disconnect()
        except AttributeError:
            pass

        self.sshclient.close()

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
        self.running = False

    def init_ssh(self):
        """
        Initializing SSH connection to device
        return success
        """
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
        return True

    def init_frida(self):
        """
        set frida device
        return success
        """
        device_manager = frida.get_device_manager()
        devices = device_manager.enumerate_devices()
        for device in devices:
            if device.type == 'usb' and device.name == 'iOS Device':
                self.frida_device = device
                return True
        self.log.error('No Frida USB device found')
        return False

    def init_images(self):
        """
        Copy template images from local folder to device
        return success
        """
        _, _, filenames = next(os.walk(self.image_base_path_local))
        image_names = ['dissallow.png', 'get.png', 'install.png', 'cloud.png', 'open.png']
        if filenames != image_names:
            self.log.error(f'Image files not found in {self.image_base_path_local}')
            self.log.info(f'Make sure no other files except these images are in the directory: {image_names}')
            self.cleanup()
            return False

        # folder_name = os.path.basename(self.image_base_path_local)
        # self.image_dir_device = f'{self.image_base_path_device}/{folder_name}'

        # self.log.debug('Copy images to device')
        # self.ssh_cmd(f'mkdir -p {self.image_dir_device}')
        # sftp_session = self.sshclient.open_sftp()

        # for image_name in image_names:
        #     image_path_local = os.path.join(self.image_base_path_local, image_name)
        #     # self.log.debug(f'Copy image {image_name}')
        #     sftp_session.put(image_path_local, f'{self.image_dir_device}/{image_name}')

        ####
        ####

        # def progress(filename, size, sent):
        #     print("%s\'s progress: %.2f%%   \r" % (filename, float(sent) / float(size) * 100))

        # def progress3(filename, size, sent):
        #     fn = filename.decode('utf-8')
        #     print(f'{fn} {sent} {size}')

        # t = tqdm(unit='B', unit_scale=True, unit_divisor=1024, miniters=1)
        # # t = tqdm(ascii=True, unit='b', unit_scale=True)

        # last_sent = [0]

        # def progress2(filename, size, sent):
        #     fn = filename.decode('utf-8')
        #     t.desc = os.path.basename(fn)
        #     t.total = size
        #     # t.update(int(sent))
        #     t.update(sent - last_sent[0])
        #     last_sent[0] = 0 if size == sent else sent

        with SCPClient(self.sshclient.get_transport(), socket_timeout=self.timeout) as scp:
            scp.put(self.image_base_path_local, self.image_base_path_device, recursive=True)
        return True

    def ssh_cmd(self, cmd):
        """
        execute command via ssh and iproxy
        return exitcode, stdout, stderr
        """
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

    def log_cmd(self, pipe, err):
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

    def run_cmd(self, cmd):
        """
        Start external program and log stdout + stderr
        """
        cmd_str = ' '.join(cmd)
        self.log.info(f'Starting: {cmd_str}')

        p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        # start logging threads: one for stderr and one for stdout
        t_out = threading.Thread(target=self.log_cmd, args=(p.stdout, False))
        t_err = threading.Thread(target=self.log_cmd, args=(p.stderr, True))

        self.processes.append(p)

        # t_out.daemon = True
        # t_err.daemon = True

        t_out.name = ' '.join(cmd[:3])  # + '-out'
        t_err.name = ' '.join(cmd[:3])  # + '-err'

        t_out.start()
        t_err.start()

    def is_installed(self, bundleId):
        """
        return version code if app is installed else return False
        """
        try:
            out = self.installed_cached[0]
        except KeyError:
            out = subprocess.check_output(['ideviceinstaller', '-l'], encoding='utf-8')
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

    def match_image(self, image_name, acceptable_value=0.9, max_try_times=1, scaleRation=1):
        '''
        get image from image_dir_device + image_name

        if matching return x,y coordinates from the middle
        else return False
        '''
        path = f'{self.image_base_path_device}/{os.path.basename(self.image_base_path_local)}/{image_name}'
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

    def tap(self, xy, message=''):
        """
        Simulate touch input (single tap) and show toast message on device
        """
        x, y = xy
        self.log.debug(f'Tapping {xy} {message}')
        self.device.show_toast(toasttypes.TOAST_WARNING, f'{message} ({x},{y})', 1.5)
        self.device.touch(touchtypes.TOUCH_DOWN, 1, x, y)
        time.sleep(0.1)
        self.device.touch(touchtypes.TOUCH_UP, 1, x, y)

    def wake_up_device(self):
        """
        Normally not needed.
        Install (uiopen) wakes up device too
        """
        self.log.info('Unlocking device if not awake..')
        self.ssh_cmd('activator send libactivator.system.homebutton')
        time.sleep(0.5)
        self.ssh_cmd('activator send libactivator.system.homebutton')
        time.sleep(0.5)

    def dump(self, target, output, dumpjs_path='dump.js', timeout=120, disable_progress=False):
        """
        target: Bundle identifier of the target app
        output: Specify name of the decrypted IPA
        dumpjs_path:  path to dump.js
        timeout: timeout in for dump to finish
        disable_progress: disable progress bars


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
        """

        bar_fmt = '{desc:20.20} {percentage:3.0f}%|{bar:20}{r_bar}'
        temp_dir = tempfile.mkdtemp()
        self.log.debug(f'{target}: Start dumping. Temp dir: {temp_dir}')
        payload_dir = os.path.join(temp_dir, 'Payload')
        os.mkdir(payload_dir)

        finished = threading.Event()
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

        def progress_helper(t):
            """
            returns progress function
            """
            last_sent = [0]

            def progress(filename, size, sent):
                if isinstance(filename, bytes):
                    filename = filename.decode('utf-8')
                t.desc = os.path.basename(filename)
                t.total = size
                displayed = t.update(sent - last_sent[0])
                last_sent[0] = 0 if size == sent else sent
                return displayed

            return progress

        def on_message(message, data):
            """
            callback function for dump messages
            receives paths and copies them with scp
            """
            t = threading.currentThread()
            t.name = f'msg-{target}'
            try:
                payload = message['payload']
            except KeyError:
                self.log.warning(f'{target}: No payload in message')
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
                        # print(f'scp.get: {scp_from} -- {scp_to}')
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
                finished.set()

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
        if finished.wait(timeout=timeout):
            generate_ipa()
            self.log.debug(f'{target}: Dumping finished. Clean up temp dir {temp_dir}')

            success = True
        else:
            self.log.error(f'{target}: Timeout of {timeout}s exceeded. Clean up temp dir {temp_dir}')

        shutil.rmtree(temp_dir)

        if session:
            session.detach()
        return success

    def bulk_decrypt(self, itunes_ids, timeout_per_MiB=0.5, parallel=3, output_directory='ipa_output'):
        """
        Installs apps, decrypts and uninstalls them
        In parallel!
        """
        total = len(itunes_ids)
        wait_for_install = []  # apps that are currently downloading and installing
        wait_for_dump = []  # apps that currently get dumped
        done = []  # apps that are uninstalled
        waited_time = 0
        while len(itunes_ids) > 0 or len(wait_for_install) > 0:
            self.log.debug(
                f'Done {len(done)}/{total}, installing: {len(wait_for_install)}, dumping {len(wait_for_dump)}'
            )
            if len(itunes_ids) > 0 and len(wait_for_install) < parallel:
                # install app
                self.log.info(f'Installing, len: {len(wait_for_install)}')

                itunes_id = itunes_ids.pop()
                trackName, version, bundleId, fileSizeMiB, price, currency = utils.itunes_info(
                    itunes_id, log_level=self.log_level
                )
                app = {'bundleId': bundleId, 'fileSizeMiB': fileSizeMiB, 'itunes_id': itunes_id, 'version': version}

                if price != 0:
                    self.log.warning(f'{bundleId}: Skipping, app is not for free ({price} {currency})')
                    continue

                if self.is_installed(bundleId) is not False:
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
                    if self.is_installed(app['bundleId']) is not False:
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

                        self.log.debug(f"{app['bundleId']}: Opening app")
                        self.ssh_cmd(f"open {app['bundleId']}")
                        time.sleep(0.1)

                        # get rid of permission request popups
                        while True:
                            dissallow_xy = self.match_image('dissallow.png')
                            if dissallow_xy is not False:
                                self.log.debug(f"{app['bundleId']}: Dissallow permission request")
                                self.tap(dissallow_xy, message='dissallow')
                                time.sleep(0.1)
                            else:
                                break

                        try:
                            os.mkdir(output_directory)
                        except FileExistsError:
                            pass

                        name = f"{app['itunes_id']}_{app['bundleId']}_{app['version']}.ipa"
                        output = os.path.join(output_directory, name)
                        timeout = self.timeout + app['fileSizeMiB'] // 2

                        disable_progress = False if self.log_level == 'debug' else True

                        self.log.info(f'self.log_level: {self.log_level}, disable_progress {disable_progress}')

                        # Starts dump() thread with args and kwargs

                        args = (app['bundleId'], output)
                        kwargs = {'timeout': timeout, 'disable_progress': disable_progress, 'open_app': False}
                        t = threading.Thread(target=self.dump, args=args, kwargs=kwargs)
                        t.daemon = True
                        t.name = f'dump-{len(self.dump_threads)}-{args[0]}'
                        self.dump_threads.append(t)
                        wait_for_dump.append((app, t))
                        t.start()
                        self.log.debug('wait for dump')
                        t.join()

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

                # uninstall apps that finished dumping
                for app, t in wait_for_dump:
                    if t.is_alive() is False:
                        self.log.info(f"{app['bundleId']}: Uninstalling")
                        subprocess.check_output(['ideviceinstaller', '--uninstall', app['bundleId']])
                        wait_for_dump.remove((app, t))
                        done.append(app)

        for t in self.dump_threads:
            self.log.debug(f'Found thread {t.name} waiting to finish')
            t.join()

        # timeout = self.timeout + fileSizeMiB * timeout_per_MiB
        # wait_time = 0
        # success = False
        # while wait_time < timeout:
        #     if self.is_installed(bundleId) is not False:
        #         self.log.info(f'Install Successful: {bundleId} {self.is_installed(bundleId)}')
        #         success = True
        #         break
        #     else:
        #         wait_time += 1
        #         time.sleep(1)

        # if success is False:
        #     self.log.warning(f'Exceeded timeout of {timeout}s')

    def install(self, itunes_id):
        """
        Opens app in appstore on device and simulates touch input to download and install the app.
        If there is a cloud button then press that and done
        Else if there is a load button, press that and confirm with install button.
        return True if successful or False at timeout
        """
        self.ssh_cmd(f'uiopen https://apps.apple.com/de/app/id{str(itunes_id)}')

        self.log.debug(f'ID {itunes_id}: Waiting for get or cloud button to appear')
        dl_btn_wait_time = 0
        while dl_btn_wait_time <= self.timeout:
            dl_btn_wait_time += 1
            time.sleep(1)
            dl_btn_xy = self.match_image('get.png')
            if dl_btn_xy is False:
                dl_btn_xy = self.match_image('cloud.png')
                if dl_btn_xy is False:
                    continue
                else:
                    # tap and done
                    self.tap(dl_btn_xy, 'cloud')
                    return True
            else:
                self.tap(dl_btn_xy, 'get')
                break

        if dl_btn_wait_time > self.timeout:
            self.log.warning(f'ID {itunes_id}: No download button found after {self.timeout}s')
            return False

        # tap and need to wait and confirm with install button
        self.tap(dl_btn_xy, 'load')
        self.log.debug(f'ID {itunes_id}: Waiting for install button to appear')
        install_btn_wait_time = 0
        while install_btn_wait_time <= self.timeout:
            install_btn_wait_time += 1
            time.sleep(1)
            install_btn_xy = self.match_image('install.png')
            if install_btn_xy is not False:
                self.tap(install_btn_xy, 'install')
                return True

        self.log.warning(f'ID {itunes_id}: No install button found after {self.timeout}s')
        return False

        # # check for get.png and if not found for cloud.png
        # dl_btn_xy = self.match_image('get.png')

        # if dl_btn_xy is False:
        #     # no match:
        #     dl_btn_xy = self.match_image('cloud.png')

        #     if dl_btn_xy is False:
        #         # raise Exception('I am stuck')
        #         self.log.warning(f'ID {itunes_id}: No download button found after {self.timeout}s')
        #         return False

        #     else:
        #         # tap and done
        #         self.tap(dl_btn_xy, 'cloud')
