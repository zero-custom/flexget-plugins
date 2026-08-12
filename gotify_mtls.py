from http import HTTPStatus
from urllib.parse import urljoin

from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession

plugin_name = 'gotify_mtls'

requests = RequestSession(max_retries=3)


class GotifyMtlsNotifier:
    """Send a Gotify notification with mutual TLS support.

    Example::

        notify:
          entries:
            via:
              - gotify_mtls:
                  url: https://gotify.example.com
                  token: <GOTIFY_TOKEN>
                  client_cert: /certs/client.pem
                  client_key: /certs/client-key.pem
                  ca_cert: /certs/ca.pem

    Configuration parameters are also supported from entries (eg. through set).
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'format': 'url'},
            'token': {'type': 'string'},
            'priority': {'type': 'integer', 'default': 4},
            'content_type': {
                'type': 'string',
                'enum': ['text/plain', 'text/markdown'],
                'default': 'text/plain',
            },
            'client_cert': {'type': 'string'},
            'client_key': {'type': 'string'},
            'ca_cert': {'type': 'string'},
            'verify': {'type': 'boolean', 'default': True},
        },
        'required': ['token', 'url'],
        'dependentRequired': {
            'client_key': ['client_cert'],
            'client_cert': ['client_key'],
        },
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """Send a Gotify notification."""
        base_url = config['url']
        api_endpoint = '/message'
        url = urljoin(base_url, api_endpoint)
        params = {'token': config['token']}

        priority = config['priority']
        content_type = config['content_type']

        notification = {
            'title': title,
            'message': message,
            'priority': priority,
            'extras': {'client::display': {'contentType': content_type}},
        }

        request_kwargs = {}
        if config.get('client_cert') and config.get('client_key'):
            request_kwargs['cert'] = (config['client_cert'], config['client_key'])
        if config.get('ca_cert'):
            request_kwargs['verify'] = config['ca_cert']
        elif 'verify' in config:
            request_kwargs['verify'] = config['verify']

        try:
            requests.post(url, params=params, json=notification, **request_kwargs)
        except RequestException as e:
            if e.response is not None:
                if e.response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    message = 'Invalid Gotify access token'
                else:
                    message = e.response.json()['error']['message']
            else:
                message = str(e)
            raise PluginWarning(message)


@event('plugin.register')
def register_plugin():
    plugin.register(GotifyMtlsNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
