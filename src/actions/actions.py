#!/usr/bin/env python3
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

import os
import sys

# Load basic layer module from $CHARM_DIR/lib
sys.path.append('lib')
from charms.layer import basic

# setup module loading from charm venv
basic.bootstrap_charm_deps()

import charms.reactive as reactive
import charmhelpers.core as ch_core
import charms_openstack.bus
import charms_openstack.charm as charm

# load reactive interfaces
reactive.bus.discover()
# load Endpoint based interface data
ch_core.hookenv._run_atstart()

# load charm class
charms_openstack.bus.discover()


def retrofit_image(*args):
    """Trigger image retrofitting process."""
    keystone_endpoint = reactive.endpoint_from_flag(
        'identity-credentials.available')
    with charm.provide_charm_instance() as instance:
        instance.retrofit(
            keystone_endpoint,
            ch_core.hookenv.action_get('force'),
            ch_core.hookenv.action_get('source-image'))


ACTIONS = {
    'retrofit-image': retrofit_image,
}


def main(args):
    action_name = os.path.basename(args[0])
    try:
        action = ACTIONS[action_name]
    except KeyError:
        return 'Action {} is undefined'.format(action_name)

    try:
        action(args)
    except Exception as e:
        ch_core.hookenv.action_fail(str(e))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
