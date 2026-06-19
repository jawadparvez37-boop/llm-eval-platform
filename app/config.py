from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
    database_path: str = "eval_platform.db"
    chat_model: str = "gpt-4o-mini"
    judge_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    trace_retention_days: int = 30
    enable_llm_judge: bool = True


settings = Settings()
