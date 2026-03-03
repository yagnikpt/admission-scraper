from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    debug: bool = False

    llm_provider: str = "groq"

    database_url: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""


settings = Settings()
