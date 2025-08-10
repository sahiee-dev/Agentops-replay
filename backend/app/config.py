from pydantic_settings import BaseSettings
from typing import List, Optional
import os


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
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
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
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ENABLE_AI_AGENT: bool = True

    class Config:
        env_file = ".env"
        extra = "allow"  # Allow extra environment variables


settings = Settings()
