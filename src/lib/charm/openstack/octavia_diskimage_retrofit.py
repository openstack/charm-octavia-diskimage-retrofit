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
import subprocess
import tempfile

import charms_openstack.adapters
import charms_openstack.charm
import charms_openstack.charm.core

import charmhelpers.core as ch_core

import charm.openstack.glance_retrofitter as glance_retrofitter

TMPDIR = '/var/snap/octavia-diskimage-retrofit/common/tmp'


class SourceImageNotFound(Exception):
    pass


class DestinationImageExists(Exception):
    pass


class OctaviaDiskimageRetrofitCharm(charms_openstack.charm.OpenStackCharm):
    release = 'rocky'
    name = 'octavia-diskimage-retrofit'
    python_version = 3
    adapters_class = charms_openstack.adapters.OpenStackRelationAdapters
    required_relations = ['juju-info', 'identity-credentials']

    @property
    def application_version(self):
        return charms_openstack.charm.core.get_snap_version(self.name)

    def request_credentials(self, keystone_endpoint):
        keystone_endpoint.request_credentials(
            self.name,
            project='services',
            domain='service_domain')

    def retrofit(self, keystone_endpoint, force=False, image_id=''):
        """Use ``octavia-diskimage-retrofit`` tool to retrofit an image.

        :param keystone_endpoint: Keystone Credentials endpoint
        :type keystone_endpoint: keystone-credentials RelationBase
        :param force: Force retrofitting of image despite presence of
                      apparently up to date target image
        :type force: bool
        :param image_id: Use specific source image for retrofitting
        :type image_id: str
        :raises:SourceImageNotFound,DestinationImageExists,
                subprocess.CalledProcessError
        """
        session = glance_retrofitter.session_from_identity_credentials(
            keystone_endpoint)
        glance = glance_retrofitter.get_glance_client(session)

        if image_id:
            source_image = next(glance.images.list(filters={'id': image_id}))
        else:
            source_image = glance_retrofitter.find_source_image(glance)
        if not source_image:
            raise SourceImageNotFound('unable to find suitable source image')

        if not image_id:
            for image in glance_retrofitter.find_destination_image(
                    glance,
                    source_image.product_name,
                    source_image.version_name):
                if not force:
                    raise DestinationImageExists(
                        'image with product_name "{}" and '
                        'version_name "{}" already exists: "{}"'
                        .format(source_image.product_name,
                                source_image.version_name, image.id))

        input_file = tempfile.NamedTemporaryFile(delete=False, dir=TMPDIR)
        ch_core.hookenv.atexit(os.unlink, input_file.name)
        ch_core.hookenv.status_set('maintenance',
                                   'Downloading {}'
                                   .format(source_image.name))
        glance_retrofitter.download_image(glance, source_image, input_file)

        output_file = tempfile.NamedTemporaryFile(delete=False, dir=TMPDIR)
        ch_core.hookenv.atexit(os.unlink, output_file.name)
        output_file.close()
        ch_core.hookenv.status_set('maintenance',
                                   'Retrofitting {}'
                                   .format(source_image.name))
        cmd = ['octavia-diskimage-retrofit',
               '-u', ch_core.hookenv.config('retrofit-uca-pocket')]
        if ch_core.hookenv.config('debug'):
            cmd.append('-d')
        cmd.extend([input_file.name, output_file.name])
        try:
            # We want to pass the [juju-]{http,https,ftp,no}-proxy model
            # configs as envvars (http_proxy, HTTP_PROXY, https_proxy, etc.) to
            # octavia-diskimage-retrofit.
            #
            # env_proxy_settings() returns a dict with these envvars. See
            # https://github.com/juju/charm-helpers/pull/248
            #
            # It is then up to octavia-diskimage-retrofit to make use of them
            # or not. This fixes
            # https://bugs.launchpad.net/charm-octavia-diskimage-retrofit/+bug/1843510
            proxy_envvars = ch_core.hookenv.env_proxy_settings()
            ch_core.hookenv.log('proxy_envvars: {}'.format(proxy_envvars),
                                level=ch_core.hookenv.DEBUG)

            envvars = os.environ.copy()
            if proxy_envvars is not None:
                envvars.update(proxy_envvars)
            output = subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, universal_newlines=True,
                env=envvars)
            ch_core.hookenv.log('Output from "{}": "{}"'.format(cmd, output),
                                level=ch_core.hookenv.DEBUG)
        except subprocess.CalledProcessError as e:
            ch_core.hookenv.log('Call to "{}" failed, output: "{}"'
                                .format(cmd, e.output),
                                level=ch_core.hookenv.ERROR)
            raise

        # NOTE(fnordahl) the manifest is stored within the image itself in
        # ``/etc/dib-manifests``.  A copy of the manifest is saved on the host
        # by the ``octavia-diskimage-retrofit`` tool.  With the lack of a place
        # to store the copy, remove it.  (it does not fit in a Glance image
        # property)
        manifest_file = output_file.name + '.manifest'
        ch_core.hookenv.atexit(os.unlink, manifest_file)

        dest_name = 'amphora-haproxy'
        for image_property in (source_image.architecture,
                               source_image.os_distro,
                               source_image.os_version,
                               source_image.version_name):
                # build a informative image name
            dest_name += '-' + str(image_property)
        dest_image = glance.images.create(container_format='bare',
                                          disk_format='qcow2',
                                          name=dest_name)
        ch_core.hookenv.status_set('maintenance',
                                   'Uploading {}'
                                   .format(dest_image.name))
        with open(output_file.name, 'rb') as fin:
            glance.images.upload(dest_image.id, fin)

        tags = [self.name]
        custom_tag = ch_core.hookenv.config('amp-image-tag')
        if custom_tag:
            tags.append(custom_tag)
        glance.images.update(
            dest_image.id,
            source_product_name=source_image.product_name or 'custom',
            source_version_name=source_image.version_name or 'custom',
            tags=tags)
        ch_core.hookenv.log('Successfully created image "{}" with id "{}"'
                            .format(dest_image.name, dest_image.id),
                            level=ch_core.hookenv.INFO)
