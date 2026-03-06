from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    debug: bool = False

    llm_provider: str = "gemini"

    database_url: str = ""
    google_cloud_project: str = ""
    google_cloud_location: str = ""
    groq_api_key: str = ""


settings = Settings()
