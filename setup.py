from setuptools import setup

setup(
    name='Qivivo_python_API',
    version='0.1.0',
    packages=['qivivo'],
    install_requires=['requests', 'oauthlib', 'pytz'],
    url='https://github.com/melecptp/Qivivo_python_API',
    project_urls={
        'Qivivo API': 'https://documenter.getpostman.com/view/1147709/qivivo-api/2MsDNL'
    },
    license='Open Source',
    author='Melec PETIT-PIERRE',
    author_email='petitpierre.melec@gmail.com',
    description='Package to access Qivivo thermostat, modules and gateways',
    keywords=['Qivivo', 'thermostat']
)
