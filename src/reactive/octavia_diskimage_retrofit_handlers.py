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

from collections import defaultdict
from charms.layer import snap
from charms.reactive.flags import (
    set_flag,
    clear_flag,
)
from charmhelpers.core.hookenv import (
    config,
    log,
)
from charmhelpers.core.host import (
    get_distrib_codename,
)

charms_openstack.bus.discover()

charm.use_defaults(
    'charm.installed',
    'config.changed',
    'update-status',
    'upgrade-charm',
)

CHANNELS = defaultdict(lambda: 'latest/edge')
CHANNELS.update({
    'jammy': '1.0/stable',
    'noble': '2.0/stable',
})


@reactive.when_not('snap.installed.octavia-diskimage-retrofit')
def snap_install():
    channel = config('channel')
    if not channel:
        series = get_distrib_codename()
        channel = CHANNELS[series]
        log('No snap channel configured, using default '
            'for series {}: {}'.format(series, channel),
            level="INFO")

    if validate_snap_risk(channel):
        clear_flag('snap.channel.invalid')
        snap.install('core')
        snap.install('octavia-diskimage-retrofit',
                     channel=channel,
                     classic=True)
    else:
        log('Invalid snap channel risk level: {}'.format(channel),
            level="ERROR")
        set_flag('snap.channel.invalid')


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


@reactive.when_any('config.changed.auto-retrofit',
                   'config.changed.frequency')
def retrofit_by_cron():
    with charm.provide_charm_instance() as instance:
        instance.handle_auto_retrofit()


def validate_snap_risk(channel):
    """Validate a provided snap channel's risk

    Any prefix is ignored ('0.10' in '0.10/stable' for example).

    :param: channel: string of the snap channel to validate
    :returns: boolean: whether provided channel is valid
    """
    tokens = channel.split('/')
    if len(tokens) == 1:
        risk_level = tokens[0]
    else:
        # Check if track is a risk level (invalid case like 'stable/edge')
        track = tokens[0]
        risk_level = tokens[1]
        if track in ('stable', 'candidate', 'beta', 'edge'):
            return False

    return risk_level in ('stable', 'candidate', 'beta', 'edge')
