================================
Python API for Qivivo Thermostat
================================

Installation
------------

To install qivivo_api simply run:

.. code-block:: bash

    [sudo] pip install qivivo-python-api


Qivivo Developer Account
------------------------

To use the Qivivo API, you will need to access your Qivivo developer account. This account is accessible with the same credentials you use to connect to your thermostat on http://www.qivivo.com/login. This developer account is accessible from the link https://account.qivivo.com/.

To generate your CLIENT_ID and SECRET_ID, you need to register a new application with:

- *Name of the application* : The name you want the users identify you to. (e.g. Qivivo)

- *The Redirect URI* : Set the redirect URI to https://qivivo.com/authorize

After that, you will be able to generate an access_token from your credentials.

Usage
-----

The qivivo API module can be imported as ``qivivo_api``.

.. code-block:: python

    import qivivo_api

    _CLIENT_ID = 'XXXXXX'
    _CLIENT_SECRET = 'XXXXXX'

    scope = 'user_basic_information read_devices read_thermostats read_wireless_modules '\
            'read_programmation update_programmation read_house_data update_house_settings'

    authorization = QivivoAuth(client_id=_CLIENT_ID, client_secret=_CLIENT_SECRET, scope=scope)
    data = QivivoData(authorization)

Once called all the devices linked to the Qivivo account will be listed in ``data.devices``.
Every variables will then be accessible from their respective device object and will be updated when needed according to the device expected communication time.

.. code-block:: python

    th = data.devices[serial_number]
    th.temperature, th.set_point, th.humidity

Temporary temperature set-point and away_mode can be set or canceled.

.. code-block:: python

    th.temporary_set_point(25, 20)  # temperature set-point (°C), duration (minutes)
    th.remove_temporary_set_point()

    import datetime
    dt_from = datetime.datetime(2018,1,1)
    dt_to = datetime.datetime(2018,1,10)
    th.set_absence(dt_from, dt_to)
    th.remove_absence()

Thermostat program can be switched to other registered programs.

.. code-block:: python

    th.active_program = 1  # progam id needs to exist in th.programs