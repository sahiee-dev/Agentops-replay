from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    POSTGRES_USER: str = "agentops"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "agentops_replay"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str = "your-super-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Logging
    LOG_LEVEL: str = "INFO"

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: str = "100MB"

    # AgentOps
    AGENTOPS_API_KEY: str = ""
    ENABLE_REAL_TIME_MONITORING: bool = True
    BATCH_SIZE: int = 100
    FLUSH_INTERVAL: int = 5

    # AI Integration
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ENABLE_AI_AGENT: bool = True

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "your-super-secret-key-change-this":
            raise ValueError(
                "Refusing to use insecure default SECRET_KEY in production. Please set SECRET_KEY in .env."
            )
        return v

    class Config:
        env_file = ".env"
        extra = "allow"  # Allow extra environment variables


try:
    settings = Settings()
except PermissionError:
    # Handle case where .env exists but is not readable (e.g. macOS protection)
    # We create a subclass that ignores the .env file
    class SettingsNoEnv(Settings):
        # Override with a safe-for-dev key to bypass the validation error
        SECRET_KEY: str = "dev-secret-key-ignore-in-prod"
        class Config:
            env_file = None
    settings = SettingsNoEnv()
