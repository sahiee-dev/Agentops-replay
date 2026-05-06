from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://agentops_app:password@localhost:5432/agentops"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Logging
    log_level: str = "WARNING"

    # Security (v1.1+)
    api_key_required: bool = False

    class Config:
        env_prefix = "AGENTOPS_"
        env_file = ".env"


settings = Settings()
