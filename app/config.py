from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    google_client_id: str = ""
    google_client_secret: str = ""
    app_base_url: str = "http://localhost:8000"
    session_secret_key: str = "dev-secret-change-in-production"
    allowed_emails: str = ""

    @property
    def allowed_email_set(self) -> set[str]:
        if not self.allowed_emails:
            return set()
        return {e.strip() for e in self.allowed_emails.split(",")}

    @property
    def oauth_redirect_uri(self) -> str:
        return f"{self.app_base_url}/auth/callback"


settings = Settings()
