#!/usr/bin/env python
# -*- coding: utf-8 -*-

# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Published May 2018
# Author : Melec PETIT-PIERRE
# Public domain source code

import json
import os

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

"""
    This API provides access to Qivivo thermostat, modules and gateways
    To use the Qivivo API, you will need to access your Qivivo developer account. This account is accessible with the same
    credentials you use to connect to your thermostat on http://www.qivivo.com/login. This developer account is accessible
    from the link https://account.qivivo.com/.
    To generate your CLIENT_ID and SECRET_ID, you need to provide the following information:
      - Name of the application : The name you want the users identify you to. (e.g. Qivivo)
      - The Redirect URI : This is the URI we will return the access token to. (e.g. https://qivivo.com/authorize)
    After that, you will be able to generate an access_token from your credentials.
"""

if os.path.isfile('credidentials.json'):
    with open('credidentials.json') as f:
        cred = json.load(f)
    _CLIENT_ID = cred['CLIENT_ID']  # Client ID from Qivivo app
    _CLIENT_SECRET = cred['CLIENT_SECRET']  # Client app secret
else:
    _CLIENT_ID = 'XXXXXX'
    _CLIENT_SECRET = 'XXXXXX'

_TOKEN_LIFE_TIME = 3600
_BASE_URL = 'https://data.qivivo.com/api/v2/'
_AUTH_URL = 'https://account.qivivo.com/oauth/token'


def check_serial(fun):
    def wrapper(*args, **kwargs):
        d_id = args[1]
        devices = args[0].devices
        if d_id in devices.keys():
            d_id = devices[d_id]['id']
            args = list(args)
            args[1] = d_id
        output = fun(*args, **kwargs)
        return output

    return wrapper


def process_response(fun):
    def wrapper(*args, **kwargs):
        res = fun(*args, **kwargs)
        res.raise_for_status()
        return res.json()

    return wrapper


class QivivoAuth(OAuth2Session):
    def __init__(self, client_id=_CLIENT_ID, client_secret=_CLIENT_SECRET, scope='user_basic_information'):
        client = BackendApplicationClient(client_id=client_id, scope=scope)
        super(QivivoAuth, self).__init__(client=client)
        self.headers.update({'Content-Type': "application/json"})
        self.fetch_token(token_url=_AUTH_URL, client_id=client_id, client_secret=client_secret, timeout=_TOKEN_LIFE_TIME)

        self.get = process_response(self.get)
        self.post = process_response(self.post)
        self.put = process_response(self.put)
        self.delete = process_response(self.delete)


class QivivoData(object):
    """
        List all devices linked to the developer account.
        Enable access to devices information (reading and setting)
    """

    def __init__(self, auth):
        self.auth = auth
        self.devices = self.get_devices()
        self.update_devices()

    def get_devices(self):
        url = _BASE_URL + 'devices'
        response = self.auth.get(url=url)
        raw_devices = response['devices']
        devices = {}
        for d in raw_devices:
            d_type, d_id = d['type'], d['uuid']
            if d_type == 'thermostat':
                d_info = self.get_thermostat_info(d_id)
                devices[d_info['serial']] = {'id': d_id, 'type': d_type}
            elif d_type == 'wireless-module':
                d_info = self.get_module_info(d_id)
                devices[d_info['serial']] = {'id': d_id, 'type': d_type}
            else:
                d_info = self.get_gateway_info(d_id)
                devices[d_info['serial']] = {'id': d_id, 'type': d_type}

        return devices

    def update_devices(self, devices=None):

        if devices is None:
            devices = self.devices.keys()

        for sn in devices:
            id = self.devices[sn]['id']
            type = self.devices[sn]['type']

            if type == 'thermostat':
                t, t_s = self.get_thermostat_temperatures(id)
                h = self.get_thermostat_humidity(id)
                a_p = self.get_thermostat_active_program(id)
                p = self.get_thermostat_programs(id)

                data = {'temperature': t,
                        'set_point': t_s,
                        'humidity': h,
                        'active_program': a_p,
                        'programs': p}
                self.devices[sn].update(data)

            elif type == 'wireless-module':
                t = self.get_module_temperature(id)
                h = self.get_module_humidity(id)
                pw = self.get_module_order(id)

                data = {'temperature': t,
                        'humidity': h,
                        'pilote-wire order': pw}
                self.devices[sn].update(data)

    # GATEWAY FUNCTIONS
    def get_gateway_info(self, g_id):
        url = _BASE_URL + 'devices/gateways/{}/info'.format(g_id)
        response = self.auth.get(url=url)
        return response

    # THERMOSTAT FUNCTIONS
    def get_thermostat_info(self, th_id):
        url = _BASE_URL + 'devices/thermostats/{}/info'.format(th_id)
        response = self.auth.get(url=url)
        return response

    @check_serial
    def get_thermostat_temperatures(self, th_id):
        url = _BASE_URL + 'devices/thermostats/{}/temperature'.format(th_id)
        response = self.auth.get(url=url)
        return response['temperature'], response['current_temperature_order']

    @check_serial
    def set_thermostat_temperature(self, th_id, temp, dur):
        url = _BASE_URL + 'devices/thermostats/{}/temperature/temporary-instruction'.format(th_id)
        payload = json.dumps({'temperature': temp, 'duration': dur})
        response = self.auth.post(url=url, data=payload)
        return response['message']

    @check_serial
    def del_thermostat_temperature(self, th_id):
        url = _BASE_URL + 'devices/thermostats/{}/temperature/temporary-instruction'.format(th_id)
        response = self.auth.delete(url=url)
        return response['message']

    @check_serial
    def get_thermostat_humidity(self, th_id):
        url = _BASE_URL + 'devices/thermostats/{}/humidity'.format(th_id)
        response = self.auth.get(url=url)
        return response['humidity']

    @check_serial
    def get_thermostat_programs(self, th_id):
        url = _BASE_URL + 'devices/thermostats/{}/programs'.format(th_id)
        response = self.auth.get(url=url)
        return {p['id']: p['name'] for p in response['user_programs']}

    @check_serial
    def get_thermostat_active_program(self, th_id):
        url = _BASE_URL + 'devices/thermostats/{}/programs'.format(th_id)
        response = self.auth.get(url=url)
        return response['user_active_program_id']

    @check_serial
    def set_thermostat_active_program(self, th_id, prog_id):
        url = _BASE_URL + 'devices/thermostats/{}/programs/{}/active'.format(th_id, prog_id)
        response = self.auth.put(url)
        return response['message']

    # MODULES FUNCTIONS
    def get_module_info(self, m_id):
        url = _BASE_URL + 'devices/wireless-modules/{}/info'.format(m_id)
        response = self.auth.get(url=url)
        return response

    @check_serial
    def get_module_temperature(self, m_id):
        url = _BASE_URL + 'devices/wireless-modules/{}/temperature'.format(m_id)
        response = self.auth.get(url=url)
        return response['temperature']

    @check_serial
    def get_module_humidity(self, m_id):
        url = _BASE_URL + 'devices/wireless-modules/{}/humidity'.format(m_id)
        response = self.auth.get(url=url)
        return response['humidity']

    @check_serial
    def get_module_order(self, m_id):
        url = _BASE_URL + 'devices/wireless-modules/{}/pilot-wire-order'.format(m_id)
        response = self.auth.get(url=url)
        return response['current_pilot_wire_order']

    @check_serial
    def get_module_programs(self, m_id):  # TODO test with Multizone
        url = _BASE_URL + 'devices/wireless-modules/{}/programs'.format(m_id)
        response = self.auth.get(url=url)
        return {p['id']: p['name'] for p in response['user_programs']}

    @check_serial
    def set_module_programs(self, m_id, prog_id):  # TODO test with Multizone
        url = _BASE_URL + 'devices/wireless-modules/{}/programs/{}/active'.format(m_id, prog_id)
        response = self.auth.get(url=url)
        return {p['id']: p['name'] for p in response['user_multizone_programs']}


if __name__ == "__main__":
    scope = 'user_basic_information read_devices read_thermostats read_wireless_modules read_programmation ' \
            'update_programmation read_house_data update_house_settings'
    authorization = QivivoAuth(client_id=_CLIENT_ID, client_secret=_CLIENT_SECRET, scope=scope)
    th = QivivoData(authorization)
    print(th.devices)
