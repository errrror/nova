# Copyright 2026
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Welcome API endpoint for nova.

Responds to GET /welcome by logging a welcome message in the nova service
and calling the peer (cinder) welcome endpoint once. A forwarded marker in
the incoming request stops the peer call, preventing infinite recursion
between the two services.
"""

from oslo_config import cfg
from oslo_log import log as logging
import requests

from nova.api.openstack import wsgi

LOG = logging.getLogger(__name__)

welcome_group = cfg.OptGroup(
    'welcome',
    title='Welcome options',
    help='Options for the welcome API endpoint.')

welcome_opts = [
    cfg.StrOpt('peer_welcome_url',
               default='http://127.0.0.1:8776/v3/welcome',
               help='URL of the peer (cinder) welcome endpoint.'),
    cfg.IntOpt('request_timeout',
               default=2,
               min=1,
               help='Timeout in seconds when calling the peer welcome '
                    'endpoint.'),
]

CONF = cfg.CONF
CONF.register_group(welcome_group)
CONF.register_opts(welcome_opts, welcome_group)

FORWARD_HEADER = 'X-Welcome-Forwarded'


class WelcomeController(wsgi.Controller):

    def index(self, req):
        """Log welcome and call the peer once unless already forwarded."""
        LOG.info('welcome from nova')
        if req.headers.get(FORWARD_HEADER):
            return {'welcome': 'welcome', 'service': 'nova'}

        url = CONF.welcome.peer_welcome_url
        try:
            requests.get(url,
                         headers={FORWARD_HEADER: '1'},
                         timeout=CONF.welcome.request_timeout)
        except requests.RequestException:
            LOG.warning('Failed to call peer welcome endpoint at %s', url)
        return {'welcome': 'welcome', 'service': 'nova'}


def create_resource():
    return wsgi.Resource(WelcomeController())
