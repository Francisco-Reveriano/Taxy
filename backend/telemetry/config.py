import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

from backend.telemetry.file_exporter import JSONFileSpanExporter

logger = logging.getLogger(__name__)


def configure_telemetry(settings) -> TracerProvider:
    """Initialize OpenTelemetry tracing. Returns the TracerProvider."""
    resource = Resource.create({
        "service.name": "tax-ai-backend",
        "service.version": "1.0.0",
    })

    provider = TracerProvider(resource=resource)

    # Always-on: local JSON file exporter (no external services needed)
    file_exporter = JSONFileSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(file_exporter))
    logger.info("Local file span exporter configured (backend/traces/)")

    # Optional: OTLP exporter (only if a collector/Jaeger is running)
    if settings.otel_exporter_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.otel_exporter_endpoint,
                insecure=True,
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP exporter configured: {settings.otel_exporter_endpoint}")
        except Exception as e:
            logger.warning(f"OTLP exporter not available: {e}")

    # Optional console exporter
    if settings.otel_console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider
