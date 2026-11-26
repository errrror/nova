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

"""Unit tests for the nova welcome API endpoint."""

import mock
from oslo_config import cfg
from oslo_serialization import jsonutils
import requests
import six
import webob

from nova.api.openstack.compute import welcome as welcome_v21
from nova import test

CONF = cfg.CONF


class WelcomeControllerTestV21(test.NoDBTestCase):

    def setUp(self):
        super(WelcomeControllerTestV21, self).setUp()
        self.controller = welcome_v21.WelcomeController()
        self.url = CONF.welcome.peer_welcome_url
        self.timeout = CONF.welcome.request_timeout

    def _request(self, headers=None, query=None):
        req = webob.Request.blank('/welcome', headers=headers or {},
                                  query_string=query or '')
        req.environ['nova.context'] = None
        return req

    @mock.patch.object(welcome_v21.LOG, 'info')
    @mock.patch.object(requests, 'get')
    def test_index_calls_peer_and_logs(self, mock_get, mock_info):
        res = self.controller.index(self._request())

        self.assertEqual('welcome', res['welcome'])
        self.assertEqual('nova', res['service'])
        mock_info.assert_called_once_with('welcome from nova')
        mock_get.assert_called_once_with(
            self.url,
            headers={welcome_v21.FORWARD_HEADER: '1'},
            timeout=self.timeout)

    @mock.patch.object(welcome_v21.LOG, 'info')
    @mock.patch.object(requests, 'get')
    def test_index_with_forward_header_does_not_recurse(self, mock_get,
                                                       mock_info):
        req = self._request(headers={welcome_v21.FORWARD_HEADER: '1'})
        res = self.controller.index(req)

        self.assertEqual('welcome', res['welcome'])
        mock_info.assert_called_once_with('welcome from nova')
        mock_get.assert_not_called()

    @mock.patch.object(welcome_v21.LOG, 'warning')
    @mock.patch.object(welcome_v21.LOG, 'info')
    @mock.patch.object(requests, 'get',
                       side_effect=requests.RequestException('peer down'))
    def test_index_peer_failure_degrades(self, mock_get, mock_info,
                                         mock_warning):
        res = self.controller.index(self._request())

        self.assertEqual('welcome', res['welcome'])
        mock_warning.assert_called_once()
        mock_get.assert_called_once()

    @mock.patch.object(requests, 'get')
    def test_index_unicode_query_is_serializable(self, mock_get):
        req = self._request(query='msg=' +
                            six.moves.urllib.parse.quote('欢迎'.encode('utf-8')))
        res = self.controller.index(req)

        payload = jsonutils.dumps(res)
        self.assertIn('welcome', payload)
        mock_get.assert_called_once()
