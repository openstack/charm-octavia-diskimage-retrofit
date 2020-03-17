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

import charms.reactive as reactive

import charms_openstack.bus
import charms_openstack.charm as charm

charms_openstack.bus.discover()

charm.use_defaults(
    'charm.installed',
    'config.changed',
    'update-status',
    'upgrade-charm',
)


@reactive.when_not('charm.installed')
def check_snap_installed():
    # Installation is handled by the ``snap`` layer, just update our status.
    with charm.provide_charm_instance() as instance:
        instance.assess_status()
    reactive.set_flag('charm.installed')


@reactive.when('identity-credentials.connected')
@reactive.when_not('identity-credentials.available')
def request_credentials():
    keystone_endpoint = reactive.endpoint_from_flag(
        'identity-credentials.connected')
    with charm.provide_charm_instance() as instance:
        instance.request_credentials(keystone_endpoint)
        instance.assess_status()


@reactive.when('identity-credentials.available')
def credentials_available():
    with charm.provide_charm_instance() as instance:
        instance.assess_status()
