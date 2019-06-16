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

import reactive.octavia_diskimage_retrofit_handlers as handlers

import charms_openstack.test_utils as test_utils


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        defaults = [
            'config.changed',
            'update-status']
        hook_set = {
            'when': {
                'request_credentials': (
                    'identity-credentials.connected',),
            },
            'when_not': {
                'check_snap_installed': (
                    'charm.installed',),
                'request_credentials': (
                    'identity-credentials.available',),
            },
        }
        # test that the hooks were registered via the
        # reactive.barbican_handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)


class TestOctaviaDiskimageRetrofitHandlers(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.charm_instance = mock.MagicMock()
        self.patch_object(handlers.charm, 'provide_charm_instance',
                          new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = \
            self.charm_instance
        self.provide_charm_instance().__exit__.return_value = None

    def test_check_snap_installed(self):
        self.patch_object(handlers.reactive, 'set_flag')
        handlers.check_snap_installed()
        self.charm_instance.assess_status.assert_called_once_with()
        self.set_flag.assert_called_once_with('charm.installed')

    def test_request_credentials(self):
        self.patch_object(handlers.reactive, 'endpoint_from_flag')
        self.endpoint_from_flag.return_value = 'endpoint'
        handlers.request_credentials()
        self.endpoint_from_flag.assert_called_once_with(
            'identity-credentials.connected')
        self.charm_instance.request_credentials.assert_called_once_with(
            'endpoint')
