# Copyright 2019 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock

import charms_openstack.test_utils as test_utils

import charm.openstack.octavia_diskimage_retrofit as octavia_diskimage_retrofit


class TestOctaviaDiskimageRetrofitCharm(test_utils.PatchHelper):

    def test_application_version(self):
        self.patch_object(
            octavia_diskimage_retrofit.charms_openstack.charm.core,
            'get_snap_version')
        self.get_snap_version.return_value = 'fake-version'
        c = octavia_diskimage_retrofit.OctaviaDiskimageRetrofitCharm()
        self.assertEqual(c.application_version, 'fake-version')
        self.get_snap_version.assert_called_once_with(
            'octavia-diskimage-retrofit')

    def test_request_credentials(self):
        keystone_endpoint = mock.MagicMock()
        c = octavia_diskimage_retrofit.OctaviaDiskimageRetrofitCharm()
        c.request_credentials(keystone_endpoint)
        keystone_endpoint.request_credentials.assert_called_once_with(
            c.name,
            project='services',
            domain='service_domain')
