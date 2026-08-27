from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_host: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_timeout: int = 10
    mail_from: str = "ai-router@example.com"

    log_level: str = "INFO"


settings = Settings()
