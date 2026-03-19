#CODE SAMPLE to demonstrate fernet encryption

class AllegroCredentials(models.Model):
     encrypted_client_secret = models.CharField(max_length=512)

    def set_client_secret(self, secret: str) -> None:
        """Encrypt and store the client secret."""
        self.encrypted_client_secret = settings.PRIMARY_FERNET.encrypt(secret.encode()).decode()

    def get_client_secret(self) -> str:
        """Decrypt and return the client secret."""
        return settings.FERNET.decrypt(self.encrypted_client_secret.encode()).decode()