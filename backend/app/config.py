from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    openai_api_key: str
    moltbook_api_url: str = "https://moltbook.com/api"
    moltbook_api_key: str = ""
    moltbook_public_key_url: str = "https://moltbook.com/.well-known/jwks.json"
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env"}


settings = Settings()
