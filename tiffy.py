#!/usr/bin/env python3

"""
# #####################################################################################
#                                                                                     #
#                                                                                     #
#                    .___________. __   _______  ___________    ____                  #
#                    |           ||  | |   ____||   ____\   \  /   /                  #
#                    `---|  |----`|  | |  |__   |  |__   \   \/   /                   #
#                        |  |     |  | |   __|  |   __|   \_    _/                    #
#                        |  |     |  | |  |     |  |        |  |                      #
#                        |__|     |__| |__|     |__|        |__|                      #
#                                                                                     #
#                                                                                     #
#                                                                                     #
# #####################################################################################

DCSO tiffy

Copyright (c) 2019, DCSO GmbH
Project   - https://github.com/DCSO/

"""
import json
import logging
import os
import re
import signal as signal_module
import sys
from datetime import datetime
from json import JSONDecodeError
from urllib.parse import urlparse

import click
import pytest
from click.testing import CliRunner

from TIELoader import TIELoader
from model import Config


# CTRL+C Handler --------------------------------------------------------------
def signal_handler(signal_name, frame):
    try:
        logging.info("------------------------------------------\n")
        logging.info('tiffy has been interrupted. Shutting down flux capacitor.')
    except Exception as e:
        print('tiffy has been interrupted. Shutting down flux capacitor.')
    sys.exit(0)


# INIT tiffy --------------------------------------------------------------
@click.command()
@click.option('--category', help='list of categories separated by comma to filter for')
@click.option('--actor', help='list of actors separated by comma to filter for')
@click.option('--family', help='list of actors separated by comma to filter for')
@click.option('--source', help='list of source pseudonyms separated by comma to filter for')
@click.option('--first-seen')
@click.option('--last-seen')
@click.option('--event-tags', help='event base tags as MISP conform JSON object String',
              default='{"name": "tlp:amber"}')
@click.option('--output-format', type=click.Choice(['MISP']), default='MISP',
              help='sets the output format for the feed.')
@click.option('--no-filter', is_flag=True,
              help='If set, no filter will be used for the request to TIE. Otherwise, the default filter will be used.')
@click.option('--loglvl', default=20, help='Sets the log level. Default is 20.\n Params are: 0 - NOTSET / 10 - DEBUG / '
                                           '20 - INFO / 30 - WARNING / 40 - ERROR / 50 - CRITICAL')
@click.option('--disable_console_log', is_flag=True, help='If used, the convert will not generate output in the '
                                                          'console')
@click.option('--disable_file_log', is_flag=True, help='If used, the converter will not generate a file output')
@click.option('--min-severity', type=int, help='Events with a severity value lower than the given value will not be '
                                               'fetched. If used, the generator will ignore the severity value defined '
                                               'in the config file. The severity value can be equal or between 0 and 5.')
@click.option('--min-confidence', type=int,
              help='Events with a confidence value lower than the given value will not be '
                   'fetched. If used, the generator will ignore the severity value defined '
                   'in the config file. The confidence value can be equal or between 0 and '
                   '100')
@click.option('--max-severity', type=int, help='Events with a severity value higher than the given value will not be '
                                               'fetched. If used, the generator will ignore the severity value defined '
                                               'in the config file. The severity value can be equal or between 0 and 5.')
@click.option('--max-confidence', type=int,
              help='Events with a confidence value higher than the given value will not be '
                   'fetched. If used, the generator will ignore the severity value defined '
                   'in the config file. The confidence value can be equal or between 0 and '
                   '100')
@click.option('--proxy_http', type=str, help='Sets the address for a http based proxy e.g. http://10.8.0.1:8000')
@click.option('--proxy_https', type=str, help='Sets the address for a https based proxy e.g. https://10.8.0.1:8000')
@click.option('--disable_cert_verify', is_flag=True,
              help='If set, ssl-certs will not be validated.')
def init(category, actor, family, source, first_seen, last_seen, event_tags, output_format, no_filter, loglvl,
         disable_console_log, disable_file_log, min_severity, min_confidence, max_severity, max_confidence,
         proxy_http, proxy_https, disable_cert_verify):
    """
    Starting the converter
    """
    error = False
    given_first_seen_date = ''
    given_last_seen_date = ''
    proxy_tie_addr = dict()

    # Signal handler for CTRL+C
    signal_module.signal(signal_module.SIGINT, signal_handler)

    try:
        event_tags = json.loads(event_tags)
    except JSONDecodeError:
        raise_error_critical('event tags are not valid JSON')

    # check loglvl
    if isinstance(loglvl, int):
        if loglvl < 0 or loglvl > 50:
            click.echo(
                'loglvl must be equal or between 0 and 50. Type \'python tiffy.py --help\' for'
                ' more information\'s.\nSet default value: 20')
            loglvl = 20
    else:
        click.echo('loglvl must be an unsigned integer value equal or between 0 and 50. Type \'python tiffy.py '
                   '--help\' for more information\'s.\nSet default value: 20')
        loglvl = 20
    TIELoader.init_logger(sys.path[0], "tiffy.py", loglvl, disable_console_log, disable_file_log)
    try:

        # Check date arguments
        if first_seen is not None:
            try:
                given_first_seen_date = datetime.strptime(first_seen, "%Y-%m-%d")
            except ValueError:
                raise_error_critical(
                    'First Seen Date could not be converted. Please use the following format YYYY-MM-DD')
        else:
            given_first_seen_date = datetime.now()

        # Check date arguments
        if last_seen is not None:
            try:
                given_last_seen_date = datetime.strptime(last_seen, "%Y-%m-%d")
            except ValueError:
                raise_error_critical(
                    'Last Seen Date could not be converted. Please use the following format YYYY-MM-DD')

        # Check confidence

        if max_confidence is not None:
            if isinstance(max_confidence, int):
                if max_confidence < 0 or max_confidence > 100:
                    raise_error_critical(
                        'The max confidence value must be an unsigned integer value equal or between 0 and 100')
            else:
                raise_error_critical('The max confidence value must be an unsigned integer value')
        if min_confidence is not None:
            if isinstance(min_confidence, int):
                if min_confidence < 0 or min_confidence > 100:
                    raise_error_critical(
                        'The confidence value must be an unsigned integer value equal or between 0 and 100')
                elif max_confidence and (min_confidence > max_confidence):
                    raise_error_critical(
                        'The min confidence must be lower than max confidence')
            else:
                raise_error_critical('The confidence value must be an unsigned integer value')

        # Check severity
        if max_severity is not None:
            if isinstance(max_severity, int):
                if max_severity < 0 or max_severity > 5:
                    raise_error_critical(
                        'The max severity value must be an unsigned integer value equal or between 0 and 5')
            else:
                raise_error_critical('The max severity value must be an unsigned integer value')
        if min_severity is not None:
            if isinstance(min_severity, int):
                if min_severity < 0 or min_severity > 5:
                    raise_error_critical(
                        'The severity value must be an unsigned integer value equal or between 0 and 5')
                elif max_severity and (min_severity > max_severity):
                    raise_error_critical(
                        'The min severity must be lower than max severity')
            else:
                raise_error_critical('The severity value must be an unsigned integer value')

        # Check Proxy variables
        ## First check if a Proxy for TIE has been set
        if proxy_http is not None or os.environ.get('HTTP_PROXY') or proxy_https is not None or os.environ.get(
                'HTTPS_PROXY'):
            proxy_tie_addr = checkProxyUrls(proxy_http, proxy_https, True)

        # check family, source, category, actor parameters
        pattern = "^[a-zA-Z0-9 /-]+(?:,[a-zA-Z0-9 /-]+)*$"
        if actor:
            if not re.search(pattern, actor):
                raise_error_critical(
                    'actor must be a single value or a comma delimited list of values')
        if family:
            if not re.search(pattern, family):
                raise_error_critical(
                    'family must be a single value or a comma delimited list of values')
        if category:
            if not re.search(pattern, category):
                raise_error_critical(
                    'category must be a single value or a comma delimited list of values')
        if source:
            if not re.search(pattern, source):
                raise_error_critical(
                    'source must be a single value or a comma delimited list of values')

        #### everything is fine -> start up
        # Loading config file
        try:
            # Load config and tags
            conf = Config.parse("settings/config.yml")

            logging.info("Powering up flux capacitor. Starting up tiffy.")
            logging.info("#### Start new TIE-Query ####")

            TIELoader.start(output_format, conf, event_tags, category, actor, family, source, given_first_seen_date,
                            given_last_seen_date, min_confidence, min_severity, max_confidence, max_severity,
                            proxy_tie_addr, no_filter, disable_cert_verify)

        except FileNotFoundError:
            logging.error("Error: \nconfig.yml and/or tags.yml not found")

    except (RuntimeError, TypeError) as ex:
        click.echo(ex)


def checkProxyUrls(proxy_http, proxy_https, system_proxy=True):
    url_http = None
    url_https = None
    proxy_addrs = dict()

    if proxy_http is not None:
        url_http = urlparse(proxy_http)
    elif system_proxy:
        if os.environ.get('HTTP_PROXY'):
            url_http = urlparse(os.environ['HTTP_PROXY'])
    if proxy_https is not None:
        url_https = urlparse(proxy_https)
    elif proxy_http is not None:
        url_https = urlparse(proxy_http)
    elif system_proxy:
        if os.environ.get('HTTPS_PROXY'):
            url_https = urlparse(proxy_https)

    # check if HTTP attributes are valid
    if url_http is not None:
        if url_http.scheme is None or url_http.port is None or url_http.hostname is None:
            raise_error_critical(
                'HTTP Proxy address ist not valid. Type \'python tiffy.py --help\' for more information\'s.')
        if url_http.scheme != 'http':
            raise_error_critical('HTTP Proxy address must have a valid scheme')
        if url_http.port <= 0 or url_http.port > 65535:
            raise_error_critical('HTTP Proxy address must have a valid port')
        if len(url_http.hostname) <= 2:
            raise_error_critical('HTTP Proxy address is to short or not valid ')
        # Address should be valid
        proxy_addrs['http'] = str(url_http.scheme + "://" + url_http.netloc)
        # If not set, Request an PyMISP will not querry HTTPS Urls
        proxy_addrs['https'] = str(url_http.scheme + "://" + url_http.netloc)

    # check if HTTPS attributes are valid
    if url_https is not None:
        if url_https.scheme is None or url_https.port is None or url_https.hostname is None:
            raise_error_critical(
                'HTTPS Proxy address is not valid. Type \'python tiffy.py --help\' for more information\'s.')
        if url_https.scheme != 'https' and url_https.scheme != 'http':
            raise_error_critical('HTTPS Proxy address must have a valid scheme')
        if url_https.port <= 0:
            raise_error_critical('HTTP Proxy address must have a valid port')
        if len(url_https.hostname) <= 2:
            raise_error_critical('HTTP Proxy address is to short or not valid ')
        # Address should be valid
        proxy_addrs['https'] = str(url_https.scheme + "://" + url_https.netloc)

    return proxy_addrs


def raise_error_critical(error_str):
    ERROR_BASE_STR = "Error starting tiffy.py: "
    logging.error(ERROR_BASE_STR + error_str)
    raise RuntimeError(ERROR_BASE_STR + error_str)


def raise_error_warning(error_str):
    ERROR_BASE_STR = "Error starting tiffy.py: "
    logging.warning(ERROR_BASE_STR + error_str)


# MAIN ################################################################
if __name__ == '__main__':
    init()
