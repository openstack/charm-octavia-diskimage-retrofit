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

import subprocess

import glanceclient
import keystoneauth1.loading
import keystoneauth1.session

SYSTEM_CA_BUNDLE = '/etc/ssl/certs/ca-certificates.crt'


def session_from_identity_credentials(identity_credentials):
    """Get Keystone Session from ``identity-credentials`` relation.

    :param identity_credentials: reactive Endpoint
    :type identity_credentials: RelationBase
    :returns: Keystone session
    :rtype: keystoneauth1.session.Session
    """
    loader = keystoneauth1.loading.get_plugin_loader('password')
    auth = loader.load_from_options(
        auth_url='{}://{}:{}/'
                 .format(identity_credentials.auth_protocol(),
                         identity_credentials.auth_host(),
                         identity_credentials.auth_port()),
        user_domain_name=identity_credentials.credentials_user_domain_name(),
        project_domain_name=(
            identity_credentials.credentials_project_domain_name()),
        project_name=identity_credentials.credentials_project(),
        username=identity_credentials.credentials_username(),
        password=identity_credentials.credentials_password())
    session = keystoneauth1.session.Session(
        auth=auth,
        verify=SYSTEM_CA_BUNDLE)
    return session


def get_glance_client(session):
    """Get Glance Client from Keystone Session.

    :param session: Keystone Session object
    :type session: keystoneauth1.session.Session
    :returns: Glance Client
    :rtype: glanceclient.Client
    """
    return glanceclient.Client('2', session=session)


def get_product_name(stream='daily', variant='server', release='18.04',
                     arch=''):
    """Build Simple Streams ``product_name`` string.

    :param stream: Stream type. ('daily'|'released')
    :type stream: str
    :param variant: Image variant. ('server'|'minimal')
    :type variant: str
    :param release: Release verssion. (e.g. '18.04')
    :type release: str
    :param arch: Architecture string as Debian would expect it
                 (Optional: default behaviour is to query dpkg)
    :type arch: str
    :returns: Simple Streams ``product_name``
    :rtype: str
    """
    if not arch:
        arch = subprocess.check_output(
            ['dpkg', '--print-architecture'],
            universal_newlines=True).rstrip()
    if stream and stream != 'released':
        return ('com.ubuntu.cloud.{}:{}:{}:{}'
                .format(stream, variant, release, arch))
    else:
        return ('com.ubuntu.cloud:{}:{}:{}'
                .format(variant, release, arch))


def find_image(glance, filters):
    """Find most recent image based on filters and ``version_name``.

    :param filters: Dictionary with Glance image properties to filter on
    :type filters: dict
    :returns: Glance image object
    """
    candidate = None
    for image in glance.images.list(filters=filters,
                                    sort_key='created_at',
                                    sort_dir='desc'):
            # glance does not offer ``version_name`` as a sort key.
            # iterate over result to make sure we get the most recent image.
        if not candidate or candidate.version_name < image.version_name:
            candidate = image
    return candidate


def find_destination_image(glance, product_name, version_name):
    """Find previously retrofitted image.

    :param product_name: SimpleStreams ``product_name``
    :type product_name: str
    :param version_name: SimpleStreams ``version_name``
    :type version_name: str
    :returns: Glance image object
    :rtype: generator
    """
    return glance.images.list(filters={'source_product_name': product_name,
                                       'source_version_name': version_name})


def find_source_image(glance):
    """Find source image in Glance.

    Attempts to find a image from the ``daily`` stream first and reverts to
    the ``released`` stream if none is found there.

    Image variant ``server`` is selected over ``minimal`` as source at the
    moment.  This is due to it taking a shorter amount of time to retrofit
    the standard image and its presence being more commonplace in deployed
    clouds.

    :returns: Glance image object or None
    :rtype: Option[..., None]
    """
    for stream in 'daily', 'released':
        for variant in 'server', 'minimal':
            product = get_product_name(stream=stream, variant=variant)
            image = find_image(glance, filters={'product_name': product})
            if image:
                break
        else:
            continue
        break
    return image


def download_image(glance, image, file_object):
    """Download image from glance.

    :param glance: Glance client
    :type glance: glanceclient.Client
    :param image: Glance image object
    :type image: Glance image object
    :param file_object: Open file object to write data to
    :type file_object: Python file object
    """
    with file_object as out:
        for chunk in glance.images.data(image.id):
            out.write(chunk)
