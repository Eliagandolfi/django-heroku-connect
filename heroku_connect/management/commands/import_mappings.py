import time

import requests
from django.core.management import BaseCommand, CommandError

from heroku_connect import utils
from heroku_connect.conf import settings


class Command(BaseCommand):
    """Import Heroku Connect mappings to connection."""

    help = __doc__.strip()

    def add_arguments(self, parser):
        parser.add_argument('--app', '-a', dest='HEROKU_APP', type=str,
                            help="Heroku app name that the schema will be pulled from.")
        parser.add_argument('--connection', '-c', dest='CONNECTION_ID', type=str,
                            help="Heroku Connect connection ID. "
                                 "If not provided, the ID of the first connection associated "
                                 "with the app will be used.")
        parser.add_argument('--wait', '-w', dest='wait', action='store_true', default=False,
                            help="Wait until mapping import to be completed.")

    def handle(self, *args, **options):
        connection_id = options.get('CONNECTION_ID', None)
        app_name = options.get('HEROKU_APP', settings.HEROKU_CONNECT_APP_NAME)
        wait = options.get('wait', False)
        if not (connection_id or app_name):
            raise CommandError("You need ether specify the application name or "
                               "the connection ID.")
        if connection_id is None:
            connections = self.get_connections(app_name)
            if len(connections) == 0:
                msg = self.style.NOTICE(
                    "No associated connections found for the current user with the app %r."
                    " Linking the current user with Heroku Connect." % app_name
                )
                self.stdout.write(msg)
                try:
                    utils.link_connection_to_account(app_name)
                except requests.HTTPError as e:
                    raise CommandError("Authentication failed") from e
                else:
                    time.sleep(3)  # deep breath
                    self.get_connections(app_name)

            if len(connections) == 0:
                raise CommandError(
                    "No associated connections found"
                    " for the current user with the app %r." % app_name)
            elif len(connections) > 1:
                raise CommandError("More than one associated connections found"
                                   " for the current user with the app %r."
                                   " Please specify the connection ID." % app_name)
            connection_id = connections[0]['id']

        mapping = utils.get_mapping(app_name=app_name)

        try:
            utils.import_mapping(connection_id, mapping)
        except requests.HTTPError as e:
            raise CommandError("Failed to upload the mapping") from e

        if wait:
            self.wait_for_import(connection_id)

    @staticmethod
    def wait_for_import(connection_id):
        """
        Wait until connection state is no longer ``IMPORT_CONFIGURATION``.

        Args:
            connection_id: Heroku Connect connection to monitor.

        Raises:
            CommandError: If fetch connection information fails.

        """
        state = utils.ConnectionStates.IMPORT_CONFIGURATION
        while state == utils.ConnectionStates.IMPORT_CONFIGURATION:
            # before you get the first state, the API can be a bit behind
            time.sleep(1)  # breeze
            try:
                connection = utils.get_connection(connection_id)
            except requests.HTTPError as e:
                raise CommandError("Failed to fetch connection information.") from e
            else:
                state = connection['state']

    @staticmethod
    def get_connections(app_name):
        try:
            return utils.get_connections(app_name)
        except requests.HTTPError as e:
            raise CommandError("Failed to load connections") from e
