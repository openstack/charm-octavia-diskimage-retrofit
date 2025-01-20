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
import time

import charms_openstack.adapters
import charms_openstack.charm
import charms_openstack.charm.core

import charmhelpers.core as ch_core
import charmhelpers.core.unitdata as unitdata

import charm.openstack.glance_retrofitter as glance_retrofitter

TMPDIR = '/var/snap/octavia-diskimage-retrofit/common/tmp'
SCRIPT_WRAPPER_NAME = "auto-retrofit.sh"
SCRIPT_WRAPPER_TEMPLATE_NAME = "auto-retrofit.tmpl"
CRON_JOB_LINKNAME = 'auto-retrofit'
ERR_FILE_EXISTS, ERR_FILE_NOT_EXISTS = 17, 2
KEY_LAST_RUN_IMAGE_ID, KEY_LAST_RUN_TIME = 'last-image-id', 'last-timestamp'


class SourceImageNotFound(Exception):
    pass


class DestinationImageExists(Exception):
    pass


class OctaviaDiskimageRetrofitCharm(charms_openstack.charm.OpenStackCharm):
    release = 'rocky'
    name = 'octavia-diskimage-retrofit'
    python_version = 3
    packages = ['distro-info']
    adapters_class = charms_openstack.adapters.OpenStackRelationAdapters
    required_relations = ['juju-info', 'identity-credentials']
    db = unitdata.kv()

    @property
    def application_version(self):
        return charms_openstack.charm.core.get_snap_version(self.name)

    def get_ubuntu_release(self, series=None):
        """Determine Ubuntu release.

        Use the ``distro-info`` script to determine the release number for
        the most recent LTS release or the series provided as argument.

        :param series: Ubuntu codename to look up
        :type series: Optional[str]
        :returns: Ubuntu release number eg. 18.04
        :rtype: str
        """
        cmd = ['distro-info', '-r']
        if series:
            cmd.extend(['--series', series])
        else:
            cmd.append('--lts')

        output = subprocess.check_output(cmd, universal_newlines=True)
        return output.split()[0]

    def request_credentials(self, keystone_endpoint):
        keystone_endpoint.request_credentials(
            self.name,
            project='services',
            domain='service_domain')

    def endpoint_type(self):
        """Determine which endpoint type to use for OpenStack clients.

        :returns: Endpoint type to use
        :rtype: str
        """
        if self.options.use_internal_endpoints:
            return 'internalURL'
        return 'publicURL'

    def handle_auto_retrofit(self):
        """Setup or clear cron job for auto-retrofitting

        Depending on the current values of ``auto-retrofit`` and ``frequency``
        config options, the cron job with the specified frequency will be
        added or removed.

        :raises:OSError
        """
        target_script = os.path.join("files", SCRIPT_WRAPPER_NAME)

        # By default remove links for current and previous frequency values
        # on all units.
        # The second one is current
        previous_linkname = self.config.previous('frequency')
        currnet_linkname = self.config['frequency']
        for freq in [previous_linkname, currnet_linkname]:
            if freq:
                linkname = '/etc/cron.{}/{}'.format(
                    freq,
                    CRON_JOB_LINKNAME)
                self.remove_cron_job(linkname)

        # Setup cron job only on the leader
        if self.config['auto-retrofit'] and ch_core.hookenv.is_leader():
            try:
                self.render_shell_wrapper()
                ch_core.hookenv.log('Creating symlink: "{}" -> "{}"'
                                    .format(target_script, linkname))
                os.symlink(os.path.abspath(target_script), linkname)
            except OSError as ex:
                if ex.errno == ERR_FILE_EXISTS:
                    ch_core.hookenv.log('symlink "{}" already exists'
                                        .format(linkname),
                                        level=ch_core.hookenv.INFO)
                else:
                    raise ex

    def remove_cron_job(self, linkname):
        """Remove existing cron job for auto retrofitting

        :param linkname: cron job symbolic link to be removed
        :type linkname: str
        :raises:OSError
        """
        try:
            ch_core.hookenv.log('Removing symlink: "{}"'
                                .format(linkname))
            os.unlink(linkname)
        except OSError as ex:
            if ex.errno == ERR_FILE_NOT_EXISTS:
                ch_core.hookenv.log('symlink "{}" does not exist'
                                    .format(linkname),
                                    level=ch_core.hookenv.INFO)
            else:
                raise ex

    def render_shell_wrapper(self):
        """Render shell script that will be run by cron
        """
        target_script = os.path.join("files", SCRIPT_WRAPPER_NAME)
        if not os.path.exists(target_script):
            unit_name = ch_core.hookenv.local_unit()
            ch_core.templating.render(
                source=SCRIPT_WRAPPER_TEMPLATE_NAME,
                target=target_script,
                perms=0o755,
                context={
                    'unit_name': unit_name,
                },
                templates_dir='files'
            )

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
        region = self.config["region"] or None
        glance = glance_retrofitter.get_glance_client(
            session, endpoint_type=self.endpoint_type(),
            region=region)

        ubuntu_release = self.get_ubuntu_release(
            series=self.config['retrofit-series'])

        if image_id:
            source_image = next(glance.images.list(filters={'id': image_id}))
        else:
            source_image = None
            if not self.config['retrofit-series']:
                # When no specifc series is configured we fall back to looking
                # for an image with series matching the series of the unit the
                # charm runs on if most recent LTS image is not available
                candidate_releases = (
                    ubuntu_release,
                    self.get_ubuntu_release(
                        series=ch_core.host.get_distrib_codename()))
            else:
                candidate_releases = (ubuntu_release,)
            for release in candidate_releases:
                source_image = glance_retrofitter.find_source_image(
                    glance,
                    release=release)
                if source_image:
                    ubuntu_release = release
                    break
            else:
                raise SourceImageNotFound(
                    'unable to find suitable source image')

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
        cmd = ['octavia-diskimage-retrofit']
        if self.config['retrofit-uca-pocket']:
            cmd.extend(['-u', self.config['retrofit-uca-pocket']])
        elif ubuntu_release == '18.04':
            # Conditional default depending on ubuntu release used for amphora
            cmd.extend(['-u', 'ussuri'])

        if self.config['debug']:
            cmd.append('-d')
        if self.config['ubuntu-mirror']:
            cmd.append('-m')
            cmd.append(self.config['ubuntu-mirror'])
        if self.config['image-format']:
            cmd.append('-O')
            cmd.append(self.config['image-format'])
        if self.config['uca-mirror']:
            uca_mirror = self.config['uca-mirror']
            if '|' in uca_mirror:
                uca_mirror = uca_mirror.split('|')[0].strip()
            cmd.append('-c')
            cmd.append(uca_mirror)
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
            # or not. This fixes LP: #1843510.
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
        dest_arch = source_image.architecture
        img_format = self.config['image-format'] or "qcow2"
        dest_image = glance.images.create(container_format='bare',
                                          disk_format=img_format,
                                          name=dest_name,
                                          architecture=dest_arch)
        ch_core.hookenv.status_set('maintenance',
                                   'Uploading {}'
                                   .format(dest_image.name))
        with open(output_file.name, 'rb') as fin:
            glance.images.upload(dest_image.id, fin)

        tags = [self.name]
        custom_tag = self.config['amp-image-tag']
        if custom_tag:
            tags.append(custom_tag)
        glance.images.update(
            dest_image.id,
            source_product_name=source_image.product_name or 'custom',
            source_version_name=source_image.version_name or 'custom',
            tags=tags)
        ts = time.strftime("%x %X")
        self.db.set(KEY_LAST_RUN_IMAGE_ID, dest_image.id)
        self.db.set(KEY_LAST_RUN_TIME, ts)
        self.db.flush()
        ch_core.hookenv.log('Successfully created image "{}" with id "{}"'
                            .format(dest_image.name, dest_image.id),
                            level=ch_core.hookenv.INFO)

    def custom_assess_status_last_check(self):
        image_id = self.db.get(KEY_LAST_RUN_IMAGE_ID)
        last_run_time = self.db.get(KEY_LAST_RUN_TIME)
        if image_id and last_run_time:
            return 'active', 'Unit is ready (Image {} retrofitting ' \
                   'completed at {})'.format(image_id, last_run_time)
        else:
            return None, None
