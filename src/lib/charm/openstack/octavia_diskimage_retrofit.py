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

import charms_openstack.adapters
import charms_openstack.charm
import charms_openstack.charm.core


class OctaviaDiskimageRetrofitCharm(charms_openstack.charm.OpenStackCharm):
    release = 'rocky'
    name = 'octavia-diskimage-retrofit'
    python_version = 3
    adapters_class = charms_openstack.adapters.OpenStackRelationAdapters
    required_relations = ['identity-credentials']

    @property
    def application_version(self):
        return charms_openstack.charm.core.get_snap_version(self.name)

    def request_credentials(self, keystone_endpoint):
        keystone_endpoint.request_credentials(
            self.name,
            project='services',
            domain='service_domain')
