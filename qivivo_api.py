#!/usr/bin/env python
# -*- coding: utf-8 -*-

# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Published May 2018
# Author : Melec PETIT-PIERRE
# Public domain source code

import datetime
import json
import logging
import os

import pytz
import requests_oauthlib
from oauthlib.oauth2 import BackendApplicationClient

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

# type names
_TYPE_NAMES = {'TH': u'thermostat',
               'HM': u'wireless-module',
               'GW': u'gateway'}

# variables names
_VAR_NAMES = {'temperature': u'temperature',
              'humidity': u'humidity',
              'set_point': u'current_temperature_order',
              'presence': u'presence_detected',
              'pilot_wire_order': u'current_pilot_wire_order',
              'programs': u'user_programs',
              'active_program': u'user_active_program_id',
              }

_DEFAULT_TEMPORARY_SET_POINT = 20

_SERVER_TIMEZONE = pytz.timezone('Europe/Paris')


def utc_time():
    return pytz.timezone('UTC').localize(datetime.datetime.utcnow())


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def process_response(fun):
    def wrapper(*args, **kwargs):
        res = fun(*args, **kwargs)
        try:
            res.raise_for_status()
            return res.json()
        except requests_oauthlib.requests.HTTPError as e:
            logger.error(e)
            pass

    return wrapper


class QivivoAuth(requests_oauthlib.OAuth2Session):
    def __init__(self, client_id=_CLIENT_ID, client_secret=_CLIENT_SECRET, scope='user_basic_information'):
        client = BackendApplicationClient(client_id=client_id, scope=scope)
        super(QivivoAuth, self).__init__(client=client)
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
        self._auth = auth
        self.devices = self.get_devices()
        self.update_devices()
        self.update_settings()

    def get_devices(self):
        url = _BASE_URL + 'devices'
        response = self._auth.get(url=url)
        raw_devices = response.get('devices', [])
        devices = {}
        for d in raw_devices:
            d_type, d_id = d['type'], d['uuid']
            if d_type == _TYPE_NAMES['TH']:
                th = QivivoThermostat(self._auth, d_id)
                devices[th.serial] = th
            elif d_type == _TYPE_NAMES['HM']:
                hm = QivivoModule(self._auth, d_id)
                devices[hm.serial] = hm
            elif d_type == _TYPE_NAMES['GW']:
                gw = QivivoGateway(self._auth, d_id)
                devices[gw.serial] = gw

        return devices

    def update_devices(self, devices_sn=None):

        if devices_sn is None:
            devices_sn = self.devices.keys()

        for sn in devices_sn:
            device = self.devices[sn]
            device.update()

    @property
    def settings(self):
        return self._settings

    def update_settings(self):
        url = _BASE_URL + 'habitation/data/settings'
        response = self._auth.get(url=url)
        if response is not None:
            for k, v in response.iteritems():
                setattr(self, '_{}'.format(k), v)


class QivivoDevice(object):
    def __init__(self, auth, id):
        self._auth = auth
        self._id = id
        self.update_info()

    # Id
    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, *args):
        logger.error('can\t set attribute id')

    # Serial
    @property
    def serial(self):
        return self._serial

    @serial.setter
    def serial(self, *args):
        logger.error('can\t set attribute serial')

    # Type
    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, *args):
        logger.error('can\t set attribute type')

    def update_info(self):
        url = _BASE_URL + 'devices/{type}s/{id}/info'.format(id=self._id, type=self._type)
        response = self._auth.get(url=url)
        for k, v in response.iteritems():
            setattr(self, '_{}'.format(k), v)
        last_com = _SERVER_TIMEZONE.localize(datetime.datetime.strptime(self._lastCommunicationDate, '%Y-%m-%d %H:%M'))
        com_delta = datetime.timedelta(minutes=self._currentTimeBetweenCommunication)
        setattr(self, '_nextCommunicationDate', last_com + com_delta)

    def update(self):
        update_methods = [m for m in dir(self) if m.startswith('update_')]
        for m in update_methods:
            method = getattr(self, m)
            method()


class QivivoGateway(QivivoDevice):
    def __init__(self, auth, id):
        self._type = 'gateway'
        QivivoDevice.__init__(self, auth, id)


class QivivoSensor(QivivoDevice):
    # Temperature
    @property
    def temperature(self):
        var = _VAR_NAMES['temperature']
        if getattr(self, '_{}_validity'.format(var)) <= utc_time():
            self.update_temperature()
        return getattr(self, '_{}'.format(var))

    @temperature.setter
    def temperature(self, *args):
        logger.error('can\t set attribute temperature')

    def update_temperature(self):
        self.update_info()
        url = _BASE_URL + 'devices/{}s/{}/temperature'.format(self._type, self._id)
        response = self._auth.get(url=url)
        if response is not None:
            for k, v in response.iteritems():
                setattr(self, '_{}'.format(k), v)
                setattr(self, '_{}_validity'.format(k), self._nextCommunicationDate)

    # Humidity
    @property
    def humidity(self):
        var = _VAR_NAMES['humidity']
        if getattr(self, '_{}_validity'.format(var)) <= utc_time():
            self.update_humidity()
        return getattr(self, '_{}'.format(var))

    @humidity.setter
    def humidity(self, *args):
        logger.error('can\t set attribute humidity')

    def update_humidity(self):
        self.update_info()
        url = _BASE_URL + 'devices/{}s/{}/humidity'.format(self.type, self._id)
        response = self._auth.get(url=url)
        if response is not None:
            for k, v in response.iteritems():
                setattr(self, '_{}'.format(k), v)
                setattr(self, '_{}_validity'.format(k), self._nextCommunicationDate)


class QivivoModule(QivivoSensor):
    def __init__(self, auth, id):
        self._type = 'wireless-module'
        self._multizone = False
        QivivoDevice.__init__(self, auth, id)
        if self._multizone:
            self.update_programs()

    # Pilote-wire order
    @property
    def pw_order(self):
        var = _VAR_NAMES['pilot_wire_order']
        if getattr(self, '_{}_validity'.format(var)) <= utc_time():
            self.update_pw_order()
        return getattr(self, '_{}'.format(var))

    @pw_order.setter
    def pw_order(self, *args):
        logger.error('can\t set attribute pw_order')

    def update_pw_order(self):
        self.update_info()
        url = _BASE_URL + 'devices/{}s/{}/pilot-wire-order'.format(self._type, self._id)
        response = self._auth.get(url=url)
        if response is not None:
            if response.get(_VAR_NAMES['pilot_wire_order'], []) != u'monozone':  # TODO get Multizone info from get_info
                setattr(self, '_multizone', True)
            for k, v in response.iteritems():
                setattr(self, '_{}'.format(k), v)
                setattr(self, '_{}_validity'.format(k), self._nextCommunicationDate)

    # Programs
    @property
    def programs(self):
        if self._multizone:
            var = _VAR_NAMES['programs']
            if getattr(self, '_{}_validity'.format(var)) <= utc_time():
                self.update_programs()
            return getattr(self, '_{}'.format(var))
        else:
            return 'Thermostat program'

    @programs.setter
    def programs(self, *args):
        logger.error('can\t set attribute programs')

    # Active program
    @property
    def active_program(self):
        if self._multizone:
            var = _VAR_NAMES['active_program']
            if getattr(self, '_{}_validity'.format(var)) <= utc_time():
                self.update_programs()
            return getattr(self, '_{}'.format(var))
        else:
            return 'Thermostat program'

    @active_program.setter
    def active_program(self, prog):
        self.set_active_program(prog)

    def set_active_program(self, prog):
        if self._multizone:
            if prog in [p['id'] for p in self.programs]:
                url = _BASE_URL + 'devices/{}s/{}/programs/{}/active'.format(self._type, self._id, prog)
                response = self._auth.put(url)
                if response is not None:
                    logger.info(response.get('message', []))
            else:
                logger.warning('Program {} is not defined for {}.'.format(prog, self._id))
        else:
            logger.warning('Module {} is on thermostat program. Cannot set program.'.format(self._id))

    def update_programs(self):
        if self._multizone:
            self.update_info()
            url = _BASE_URL + 'devices/{}s/{}/programs'.format(self._type, self._id)
            response = self._auth.get(url=url)
            if response is not None:
                for k, v in response.iteritems():
                    setattr(self, '_{}'.format(k), v)
                    setattr(self, '_{}_validity'.format(k), self._nextCommunicationDate)


class QivivoThermostat(QivivoSensor):
    def __init__(self, auth, id):
        self._type = 'thermostat'
        QivivoDevice.__init__(self, auth, id)

    # Presence
    @property
    def presence(self):
        var = _VAR_NAMES['presence']
        if getattr(self, '_{}_validity'.format(var)) <= utc_time():
            self.update_presence()
        return getattr(self, '_{}'.format(var))

    @presence.setter
    def presence(self, *args):
        logger.error('can\t set attribute presence')

    def update_presence(self):
        self.update_info()
        url = _BASE_URL + 'devices/{}s/{}/presence'.format(self._type, self._id)
        response = self._auth.get(url=url)
        if response is not None:
            for k, v in response.iteritems():
                setattr(self, '_{}'.format(k), v)
                setattr(self, '_{}_validity'.format(k), self._nextCommunicationDate)

    # Temperature set point
    @property
    def set_point(self):
        var = _VAR_NAMES['set_point']
        if getattr(self, '_{}_validity'.format(var)) <= utc_time():
            self.update_temperature()
        return getattr(self, '_{}'.format(var))

    @set_point.setter
    def set_point(self, *args):
        logger.error('can\t set attribute set_point')

    def temporary_set_point(self, temp, dur=None):
        if dur is None:
            dur = _DEFAULT_TEMPORARY_SET_POINT
        url = _BASE_URL + 'devices/{}s/{}/temperature/temporary-instruction'.format(self._type, self._id)
        data = {'temperature': temp, 'duration': dur}
        response = self._auth.post(url=url, json=data)
        if response is not None:
            logger.info(response.get('message', []))

    def remove_temporary_set_point(self):
        url = _BASE_URL + 'devices/{}s/{}/temperature/temporary-instruction'.format(self._type, self._id)
        response = self._auth.delete(url=url)
        if response is not None:
            logger.info(response.get('message', []))

    # Programs
    @property
    def programs(self):
        var = _VAR_NAMES['programs']
        if getattr(self, '_{}_validity'.format(var)) <= utc_time():
            self.update_programs()
        return getattr(self, '_{}'.format(var))

    @programs.setter
    def programs(self, *args):
        logger.error('can\t set attribute programs')

    # Active program
    @property
    def active_program(self):
        var = _VAR_NAMES['active_program']
        if getattr(self, '_{}_validity'.format(var)) <= utc_time():
            self.update_programs()
        return getattr(self, '_{}'.format(var))

    @active_program.setter
    def active_program(self, prog):
        self.set_active_program(prog)

    def set_active_program(self, prog):
        if prog in [p['id'] for p in self.programs]:
            url = _BASE_URL + 'devices/{}s/{}/programs/{}/active'.format(self._type, self._id, prog)
            response = self._auth.put(url)
            if response is not None:
                logger.info(response.get('message', []))
        else:
            logger.warning('Promgram {} is not defined for {}'.format(self._id))

    def update_programs(self):
        self.update_info()
        url = _BASE_URL + 'devices/{}s/{}/programs'.format(self._type, self._id)
        response = self._auth.get(url=url)
        if response is not None:
            for k, v in response.iteritems():
                setattr(self, '_{}'.format(k), v)
                setattr(self, '_{}_validity'.format(k), self._nextCommunicationDate)

    # Absence
    def set_absence(self, start_date, end_date):  # TODO adapt date with timezone
        url = _BASE_URL + 'devices/{}s/{}/absence'.format(self._type, self._id)
        data = {'start_date': start_date.strftime('%Y-%m-%d %H:%M'), 'end_date': end_date.strftime('%Y-%m-%d %H:%M')}
        response = self._auth.post(url=url, json=data)
        if response is not None:
            logger.info(response.get('message', []))

    def remove_absence(self):
        url = _BASE_URL + 'devices/{}s/{}/absence'.format(self._type, self._id)
        response = self._auth.delete(url=url)
        if response is not None:
            logger.info(response.get('message', []))


if __name__ == "__main__":
    scope = 'user_basic_information read_devices read_thermostats read_wireless_modules read_programmation ' \
            'update_programmation read_house_data update_house_settings'
    authorization = QivivoAuth(client_id=_CLIENT_ID, client_secret=_CLIENT_SECRET, scope=scope)
    data = QivivoData(authorization)

    print('The account is linked to {} devices:'.format(len(data.devices)))
    for sn, d in data.devices.iteritems():
        print('\t- {} ({})'.format(d.serial, d.type))
        if d.type == 'wireless-module':
            print(u'\t\ttemperature: {}\u00b0C'.format(d.temperature))
            print(u'\t\thumidity: {}%'.format(d.humidity))
            print(u'\t\tpw order: {}'.format(d.pw_order))
        if d.type == 'thermostat':
            print(u'\t\ttemperature: {}\u00b0C'.format(d.temperature))
            print(u'\t\thumidity: {}%'.format(d.humidity))
            print(u'\t\ttemp set point: {}\u00b0C'.format(d.set_point))
