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

"""The hello world compute API."""

from nova.api.openstack import wsgi


class HelloController(wsgi.Controller):
    """Minimal controller that returns a fixed hello world payload."""

    def index(self, req):
        """Return hello world without any policy or auth check."""
        return {'message': 'Hello, World!'}
