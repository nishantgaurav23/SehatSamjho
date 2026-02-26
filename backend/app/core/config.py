from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "development"
    debug: bool = True

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 2000
    openai_timeout_seconds: int = 45

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str
    validate_twilio_signature: bool = False

    # Bhashini TTS
    bhashini_api_key: str = ""
    bhashini_user_id: str = ""
    bhashini_pipeline_url: str = (
        "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
    )

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # AWS / S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    aws_s3_bucket: str = "sehatsamjho-audio-dev"
    aws_s3_audio_url_expiry: int = 3600

    # Drug DB
    indian_medicine_api_key: str = ""
    indian_medicine_api_url: str = "https://api.indianmedicinedatabase.com/v1"

    # Analytics
    posthog_api_key: str = ""
    posthog_host: str = "https://app.posthog.com"

    # Session
    session_ttl_seconds: int = 1800  # 30 minutes

    # Feature flags
    enable_audio: bool = True
    enable_drug_lookup: bool = True
    enable_indictrans2: bool = False
    enable_analytics: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
