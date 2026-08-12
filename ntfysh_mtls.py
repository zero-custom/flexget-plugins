from http import HTTPStatus
from urllib.parse import urljoin

from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession

plugin_name = 'ntfysh_mtls'

requests = RequestSession(max_retries=3)


class NtfyshMtlsNotifier:
    """Send a Ntfy.sh notification with mutual TLS support.

    Example::

        notify:
          entries:
            via:
              - ntfysh_mtls:
                  url: https://ntfy.example.com/
                  topic: <NTFY_TOPIC>
                  client_cert: /certs/client.pem
                  client_key: /certs/client-key.pem
                  ca_cert: /certs/ca.pem

    Configuration parameters are also supported from entries (eg. through set).
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'format': 'url', 'default': 'https://ntfy.sh/'},
            'topic': {'type': 'string'},
            'priority': {'type': 'integer', 'default': 3},
            'delay': {'type': 'string'},
            'tags': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'client_cert': {'type': 'string'},
            'client_key': {'type': 'string'},
            'ca_cert': {'type': 'string'},
            'verify': {'type': 'boolean', 'default': True},
        },
        'required': ['topic', 'url'],
        'dependentRequired': {
            'client_key': ['client_cert'],
            'client_cert': ['client_key'],
        },
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """Send a Ntfy.sh notification."""
        base_url = config['url']
        topic = config['topic']
        url = urljoin(base_url, topic)

        req = {
            'url': url,
            'data': message,
            'params': {'title': title, 'priority': config['priority']},
        }

        if 'username' in config or 'password' in config:
            req['auth'] = HTTPBasicAuth(config.get('username', ''), config.get('password', ''))

        if 'delay' in config:
            req['params']['delay'] = config['delay']
        if 'tags' in config:
            req['params']['tags'] = config['tags']

        # mTLS: client cert/key pair and CA override
        request_kwargs = {}
        if config.get('client_cert') and config.get('client_key'):
            request_kwargs['cert'] = (config['client_cert'], config['client_key'])
        if config.get('ca_cert'):
            request_kwargs['verify'] = config['ca_cert']
        elif 'verify' in config:
            request_kwargs['verify'] = config['verify']

        try:
            requests.post(**req, **request_kwargs)
        except RequestException as e:
            if e.response is not None:
                if e.response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    message = 'Invalid username and password'
                else:
                    message = e.response.text
            else:
                message = str(e)
            raise PluginWarning(message)


@event('plugin.register')
def register_plugin():
    plugin.register(NtfyshMtlsNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])