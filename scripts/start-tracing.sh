#!/usr/bin/env bash
#
# NOTE: Tracing is built-in — spans are always saved to backend/traces/
# and viewable at http://localhost:8000/api/traces.
#
# This script is OPTIONAL. Run it only if you want to also send traces
# to Jaeger for its richer UI. Then set in .env:
#   OTEL_EXPORTER_ENDPOINT="http://localhost:4317"
#
set -e

if command -v jaeger-all-in-one &>/dev/null; then
  echo "Starting Jaeger (native binary)..."
  echo "Jaeger UI:  http://localhost:16686"
  echo "OTLP gRPC:  localhost:4317"
  echo ""
  jaeger-all-in-one \
    --collector.otlp.grpc.host-port=:4317 \
    --collector.otlp.http.host-port=:4318 \
    --query.http-server.host-port=:16686
elif command -v docker &>/dev/null; then
  echo "Starting Jaeger (Docker)..."
  docker run -d --name jaeger-tax-ai \
    -p 4317:4317 \
    -p 4318:4318 \
    -p 16686:16686 \
    jaegertracing/all-in-one:latest
  echo "Jaeger UI:  http://localhost:16686"
  echo "OTLP gRPC:  localhost:4317"
else
  echo "ERROR: Neither jaeger-all-in-one nor Docker found."
  echo ""
  echo "Jaeger is optional — traces are already saved to backend/traces/"
  echo "and viewable at http://localhost:8000/api/traces"
  echo ""
  echo "To install Jaeger: brew install jaegertracing/tap/jaeger-all-in-one"
  exit 1
fi
