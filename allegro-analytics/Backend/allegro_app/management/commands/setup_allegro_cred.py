# Django management command for syncing Allegro API credentials
# from environment (AWS Secrets Manager) into the database.
#
# Responsibilities:
# - Reads credentials from secrets_json
# - Ensures a single credentials record exists
# - Updates DB at startup
#
# Used during container startup (entrypoint.sh)



from django.core.management.base import BaseCommand
from allegro_app.oauth2.models import AllegroCredentials
from django.db import transaction
import logging
import os
import json

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Auto cred for Allegro CLIENT'
    
    @transaction.atomic
    def handle(self, *args, **options):
        secrets_raw = os.environ.get('secrets_json', '{}')
        
        try:
            secrets = json.loads(secrets_raw)
        except json.JSONDecodeError:
            logger.error('Failed to decode secrets_json!')
            return
    
        client_id = secrets.get('ALLEGRO_CLIENT_ID')
        client_secret = secrets.get('ALLEGRO_CLIENT_SECRET')
        redirect_uri = secrets.get('ALLEGRO_REDIRECT_URI')
        is_sandbox_raw = secrets.get('ALLEGRO_IS_SANDBOX', 'False')
        is_sandbox_env = str(is_sandbox_raw).lower() in ['true', '1', 't', 'y', 'yes']

        if not client_id or not client_secret:
            logger.error('No creds in json!')
            return

        obj, created = AllegroCredentials.objects.get_or_create(id=1)

        obj.client_id = client_id
        obj.set_client_secret(client_secret)
        obj.redirect_uri = redirect_uri
        obj.is_sandbox = is_sandbox_env
        obj.save()

        if created:
            logger.info("Created new Allegro credentials")
        else:
            logger.info("Updated Allegro credentials")