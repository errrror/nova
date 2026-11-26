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

"""Unit tests for the hello world API controller.

NOTE: This legacy Nova tree cannot be imported as a package under Python 3.11
(``async`` is used as an identifier in compute/api.py). The test loads the
controller module directly by path so the controller logic stays verifiable.
"""

import importlib.util
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_HELLO_PATH = os.path.join(
    _REPO_ROOT, 'nova', 'api', 'openstack', 'compute', 'hello.py')


def _load_hello():
    if not os.path.isfile(_HELLO_PATH):
        return None
    spec = importlib.util.spec_from_file_location('nova_hello', _HELLO_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HelloControllerTest(unittest.TestCase):
    def setUp(self):
        super(HelloControllerTest, self).setUp()
        self.hello = _load_hello()
        if self.hello is not None:
            self.controller = self.hello.HelloController()

    def test_hello_module_exists(self):
        self.assertIsNotNone(
            self.hello, 'nova/api/openstack/compute/hello.py 应存在')

    def test_index_returns_hello_world(self):
        self.assertIsNotNone(self.hello, 'hello 模块缺失')
        self.assertEqual(
            {'message': 'Hello, World!'}, self.controller.index(None))

    def test_index_returns_only_message_key(self):
        self.assertIsNotNone(self.hello, 'hello 模块缺失')
        result = self.controller.index(None)
        self.assertEqual({'message'}, set(result.keys()))

    def test_index_does_not_require_auth_context(self):
        self.assertIsNotNone(self.hello, 'hello 模块缺失')
        result = self.controller.index(None)
        self.assertEqual('Hello, World!', result['message'])


if __name__ == '__main__':
    unittest.main()
