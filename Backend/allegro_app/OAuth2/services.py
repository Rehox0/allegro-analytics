#CODE SAMPLE to demonstrate fernet encryption

    @staticmethod
    def require_client_secret(creds: AllegroCredentials) -> str:
        secret = creds.get_client_secret().strip()
        if not secret:
            raise ValueError("Allegro client_secret is missing")
        return secret