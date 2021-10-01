#!/usr/bin/env python3
# Copyright 2021 Canonical
# See LICENSE file for licensing details.

"""Charm the service."""

import os
import logging

from jinja2 import Environment, FileSystemLoader

from ops.charm import CharmBase
from ops.model import ActiveStatus, BlockedStatus
from ops.main import main
from ops.framework import StoredState

from charmhelpers.core import hookenv;


logger = logging.getLogger(__name__)


class JujuDashboardCharm(CharmBase):
    """Juju Dashboard Charm"""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on["dashboard"].relation_changed, self._on_dashboard_relation_changed)
        self.framework.observe(self.on["controller"].relation_changed, self._on_controller_relation_changed)
        self._stored.set_default(controllerData={})
        hookenv.open_port(8080)

    def _on_install(self, _):
        """
        Start the webserver to host the dashboard.
        """
        os.system("apt install -y nginx")
        self._configure()

    def _on_start(self, _):
        """
        Start the webserver to host the dashboard.
        """
        pass

    def _on_upgrade_charm(self, _):
        """
        Restart the webserver to host the dashboard.
        """
        self._configure()

    def _on_config_changed(self, _):
        """
        XXX Not implemented
        Any values defined in the configuration will override the values
        provided by the controller relation.
        """
        self._configure()

    def _on_dashboard_relation_changed(self, event):
        """
        XXX Not implemented
        If the user wants to front the dashboard with a proxy return the
        information about where the dashboard is being hosted so that it can
        connect to the correct endpoint.
        """
        pass

    def _on_controller_relation_changed(self, event):
        """
        Receive the configuration data for the controller so that we can
        generate the config file for the dashboard. We also send the endpoint
        data that the dashboard is being hosted at so that this information can
        be relayed to the user via the controller when the user runs the
        `juju dashboard` command.
        """
        self._stored.controllerData["controller-url"] = event.relation.data[event.app]["controller-url"]
        self._stored.controllerData["identity-provider-url"] = event.relation.data[event.app].get("identity-provider-url", "")
        self._stored.controllerData["is-juju"] = event.relation.data[event.app]["is-juju"]

        self._configure()

    def _configure(self):
        """
        Take the configuration values and render them to the index.html file
        for display on the static page.
        """
        data = self._stored.controllerData

        controller_url = data.get("controller-url")
        identity_provider_url = data.get("identity-provider-url")
        is_juju = data.get("is-juju", True)

        if not controller_url:
            self.unit.status = BlockedStatus("Missing controller URL")
            return

        env = Environment(loader=FileSystemLoader(os.getcwd()))
        env.filters['bool'] = bool

        config_template = env.get_template("src/config.js.template")
        config_template.stream(
            base_app_url="/",
            controller_api_endpoint="/api",
            identity_provider_url=identity_provider_url,
            is_juju=is_juju
        ).dump("src/dist/config.js")

        nginx_template = env.get_template("src/nginx.conf.template")
        nginx_template = nginx_template.stream(
            # nginx proxy_pass expects the protocol to be https
            controller_ws_api=controller_url.replace("wss", "https"),
            dashboard_root=os.getcwd()
        ).dump("/etc/nginx/sites-available/default")

        nginx_status = os.system("sudo systemctl restart nginx")
        # If restarting nginx returns a 0 status it should have been succesfull
        if nginx_status == 0:
            self.unit.status = ActiveStatus()
        else:
            self.unit.status = BlockedStatus("Could not start nginx")

if __name__ == "__main__":
    main(JujuDashboardCharm)
