# Overview

This subordinate charm provides the Octavia Diskimage Retrofit tool

# Usage

There is a [section in the Octavia][amphora-octavia-cdg] appendix in the
[OpenStack Charms Deployment Guide][cdg] that describes how to deploy and use
the charm.

A [bundle overlay][octavia-bundle-overlay] for use in conjunction with the
[OpenStack Base bundle][openstack-base-bundle] is also available.

> **Note**: The charm relies on Glance image properties as provided by the
  [Glance Simplestreams Sync Charm][charm-gss] for automatic discovery of the
  most recent image, and as such is designed to be deployed as a subordinate to
  it.

> **Note**: When establishing connections to cloud services such as Glance and
  Keystone in clouds that have TLS enabled, the system certificate store will
  be used to verify the peer. It is the responsibility of the principle charm
  to populate the system certificate store.

# Bugs

Please report bugs on [Launchpad][lp-octavia-diskimage-retrofit].

For general questions please refer to the OpenStack [Charm Guide][cg].

<!-- LINKS -->

[cg]: https://docs.openstack.org/charm-guide/latest/
[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/
[amphora-octavia-cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/app-octavia.html#amphora-image
[octavia-bundle-overlay]: https://github.com/openstack-charmers/openstack-bundles/blob/master/stable/overlays/loadbalancer-octavia.yaml
[openstack-base-bundle]: https://jujucharms.com/openstack-base/
[charm-gss]: https://jaas.ai/glance-simplestreams-sync/
[lp-octavia-diskimage-retrofit]: https://bugs.launchpad.net/charm-octavia-diskimage-retrofit/+filebug
