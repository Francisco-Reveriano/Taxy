import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # API Keys
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    mistral_api_key: str = Field(default="", validation_alias="MISTRAL_API_KEY")

    # LLM Models
    ocr_model: str = Field(default="mistral-ocr-2512", validation_alias="OCR_MODEL")
    # Handle .env typo: ANTHROPIDC_ADVANCE_LLM_MODEL
    anthropic_advance_llm_model: str = Field(
        default="claude-opus-4-6",
        validation_alias="ANTHROPIDC_ADVANCE_LLM_MODEL"
    )
    anthropic_medium_llm_model: str = Field(
        default="claude-sonnet-4-6",
        validation_alias="ANTHROPIC_MEDIUM_LLM_MODEL"
    )
    anthropic_low_llm_model: str = Field(
        default="claude-haiku-4-5",
        validation_alias="ANTHROPIC_LOW_LLM_MODEL"
    )
    openai_very_advance_llm_model: str = Field(
        default="gpt-4o",
        validation_alias="OPENAI_VERY_ADVANCE_LLM_MODEL"
    )
    openai_advance_llm_model: str = Field(
        default="gpt-4o",
        validation_alias="OPENAI_ADVANCE_LLM_MODEL"
    )
    openai_medium_llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="OPENAI_MEDIUM_LLM_MODEL"
    )

    # Vector Store
    tax_vector_store: str = Field(
        default="",
        validation_alias="TAX_VECTOR_STORE"
    )

    # Telemetry
    otel_exporter_endpoint: str = Field(
        default="",
        validation_alias="OTEL_EXPORTER_ENDPOINT"
    )
    otel_console_export: bool = Field(default=False, validation_alias="OTEL_CONSOLE_EXPORT")

    # Agent settings
    todo_max_iterations: int = Field(default=25, validation_alias="TODO_MAX_ITERATIONS")
    context_window_threshold: float = Field(
        default=0.75,
        validation_alias="CONTEXT_WINDOW_THRESHOLD"
    )

    # SSL verification (set to false if behind a corporate proxy with self-signed certs)
    mistral_verify_ssl: bool = Field(default=True, validation_alias="MISTRAL_VERIFY_SSL")

    # Upload limits
    max_upload_size_mb: int = Field(default=20, validation_alias="MAX_UPLOAD_SIZE_MB")

    # Form 1040 template
    form_1040_template_path: str = Field(
        default="/Users/Francisco_Reveriano/Downloads/f1040.pdf",
        validation_alias="FORM_1040_TEMPLATE_PATH",
    )

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
