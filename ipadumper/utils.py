# stdlib
from datetime import datetime
import logging
import os
import requests
import socket

# external
import coloredlogs  # colored logs


def itunes_info(itunes_id, log_level='info', country='us'):
    '''
    return: trackName, trackId, version, bundleId, fileSizeMiB, price, currency
    '''
    log = get_logger(log_level, name=__name__)
    log.debug('Get app info from itunes.apple.com')
    url = f'https://itunes.apple.com/{country}/search?limit=200&term={str(itunes_id)}&media=software'
    j = requests.get(url).json()
    if j['resultCount'] == 0:
        log.error('no result with that itunes id found')
        return

    if j['resultCount'] > 1:
        log.warning('multiple results with that itunes id found')
    result = j['results'][0]
    trackName = result['trackName']
    trackId = result['trackId']
    version = result['version']
    bundleId = result['bundleId']
    fileSizeMiB = int(result['fileSizeBytes']) // (2 ** 20)
    price = result['price']
    currency = result['currency']

    log.debug(
        f'Name: {trackName}, trackId: {trackId}, version: {version}, bundleId: {bundleId}, size: {fileSizeMiB}MiB'
    )
    if trackId != itunes_id:
        log.warning(f'trackId ({trackId}) != itunes_id ({itunes_id})')

    return trackName, version, bundleId, fileSizeMiB, price, currency


def get_logger(log_level, name=__name__):
    '''
    Colored logging

    :param log_level:  'warning', 'info', 'debug'
    :param name: logger name (use __name__ variable)
    :return: Logger
    '''

    fmt = '%(asctime)s %(threadName)-16s %(levelname)-8s %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    fs = {
        'asctime': {'color': 'green'},
        'hostname': {'color': 'magenta'},
        'levelname': {'color': 'red', 'bold': True},
        'name': {'color': 'magenta'},
        'programname': {'color': 'cyan'},
        'username': {'color': 'yellow'},
    }

    ls = {
        'critical': {'color': 'red', 'bold': True},
        'debug': {'color': 'green'},
        'error': {'color': 'red'},
        'info': {},
        'notice': {'color': 'magenta'},
        'spam': {'color': 'green', 'faint': True},
        'success': {'color': 'green', 'bold': True},
        'verbose': {'color': 'blue'},
        'warning': {'color': 'yellow'},
    }

    logger = logging.getLogger(name)

    # log to file
    now_str = datetime.now().strftime('%F_%T')
    handler = logging.FileHandler(f'{now_str}.log')
    formatter = logging.Formatter(fmt, datefmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # logger.propagate = False  # no logging of libs
    coloredlogs.install(level=log_level, logger=logger, fmt=fmt, datefmt=datefmt, level_styles=ls, field_styles=fs)
    return logger


def progress_helper(t):
    '''
    returns progress function
    '''
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


def free_port():
    '''
    Determines a free port using sockets.
    '''
    free_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    free_socket.bind(('0.0.0.0', 0))
    free_socket.listen(5)
    port = free_socket.getsockname()[1]
    free_socket.close()
    return port
