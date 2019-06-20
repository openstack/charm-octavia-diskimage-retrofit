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

import charm.openstack.glance_retrofitter as glance_retrofitter


class TestGlanceRetrofitter(test_utils.PatchHelper):

    def test_session_from_identity_credentials(self):
        self.patch_object(
            glance_retrofitter.keystoneauth1.loading, 'get_plugin_loader')
        self.patch_object(
            glance_retrofitter.keystoneauth1.session, 'Session')
        loader = mock.MagicMock()
        self.get_plugin_loader.return_value = loader
        endpoint = mock.MagicMock()
        result = glance_retrofitter.session_from_identity_credentials(endpoint)
        self.get_plugin_loader.assert_called_once_with('password')
        loader.load_from_options.assert_called_once_with(
            auth_url='{}://{}:{}/'
                     .format(endpoint.auth_protocol(),
                             endpoint.auth_host(),
                             endpoint.auth_port()),
            user_domain_name=endpoint.credentials_user_domain_name(),
            project_domain_name=endpoint.credentials_project_domain_name(),
            project_name=endpoint.credentials_project(),
            username=endpoint.credentials_username(),
            password=endpoint.credentials_password())
        self.Session.assert_called_once_with(
            auth=loader.load_from_options(),
            verify=glance_retrofitter.SYSTEM_CA_BUNDLE)
        self.assertEquals(result, self.Session())

    def test_get_glance_client(self):
        self.patch_object(glance_retrofitter.glanceclient, 'Client')
        result = glance_retrofitter.get_glance_client('aSession')
        self.Client.assert_called_once_with('2', session='aSession')
        self.assertEquals(result, self.Client())

    def test_get_product_name(self):
        self.patch_object(glance_retrofitter.subprocess, 'check_output')
        self.check_output.return_value = 'aArchitecture'
        self.assertEquals(glance_retrofitter.get_product_name(),
                          'com.ubuntu.cloud.daily:server:18.04:aArchitecture')
        self.check_output.assert_called_once_with(
            ['dpkg', '--print-architecture'],
            universal_newlines=True)

    def test_find_image(self):
        glance = mock.MagicMock()

        class FakeImage1(object):
            version_name = '20194242'
        fake_image1 = FakeImage1()

        class FakeImage2(object):
            version_name = '20195151'
        fake_image2 = FakeImage2()

        glance.images.list.return_value = [fake_image1, fake_image2]
        self.assertEquals(
            glance_retrofitter.find_image(glance, {'fake_property': 'real'}),
            fake_image2)
        glance.images.list.assert_called_once_with(
            filters={'fake_property': 'real'},
            sort_key='created_at',
            sort_dir='desc')

    def test_find_destination_image(self):
        glance = mock.MagicMock()
        result = glance_retrofitter.find_destination_image(
            glance, 'aProduct', 'aVersion')
        glance.images.list.assert_called_once_with(
            filters={'source_product_name': 'aProduct',
                     'source_version_name': 'aVersion'})
        self.assertEquals(result, glance.images.list())

    def test_find_source_image(self):
        self.patch_object(glance_retrofitter, 'get_product_name')
        self.patch_object(glance_retrofitter, 'find_image')
        self.get_product_name.return_value = 'aProduct'
        self.find_image.side_effect = [None, None, None, 'aImage']
        self.assertEquals(
            glance_retrofitter.find_source_image('aGlance'),
            'aImage')
        self.get_product_name.assert_has_calls([
            mock.call(stream='daily', variant='server'),
            mock.call(stream='daily', variant='minimal'),
            mock.call(stream='released', variant='server'),
            mock.call(stream='released', variant='minimal'),
        ])
        self.find_image.assert_called_with(
            'aGlance', filters={'product_name': 'aProduct'})

    def test_download_image(self):
        glance = mock.MagicMock()
        glance.images.data.return_value = ['two', 'Chunks']
        image = mock.MagicMock()
        file_object = mock.MagicMock()
        file_handle = mock.MagicMock()
        file_object.__enter__.return_value = file_handle
        glance_retrofitter.download_image(glance, image, file_object)
        glance.images.data.assert_called_once_with(image.id)
        file_handle.write.assert_has_calls([
            mock.call('two'),
            mock.call('Chunks'),
        ])
