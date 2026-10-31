# DELTA OS — Institutional Multi-Stage Production Container
# Option C: Headless 24/7 Edge / Cloud Execution Node

# ==========================================
# Stage 1: Rust Native C-ABI & TUI Builder
# ==========================================
FROM rust:1.85-bookworm AS rust-builder

WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY rust/ ./rust/
COPY tui/ ./tui/

# Compile delta_native (cdylib) and delta-tui in release mode
RUN cargo build --release --workspace

# ==========================================
# Stage 2: Production Quantitative Runtime
# ==========================================
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    DELTA_HOME=/home/deltauser/.delta

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root unprivileged service user
RUN useradd -m -u 1000 -s /bin/bash deltauser

WORKDIR /app

# Install Python production dependencies
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy native shared libraries from rust builder to canonical target directory
RUN mkdir -p /app/target/release
COPY --from=rust-builder /build/target/release/libdelta_native.so /app/target/release/libdelta_native.so
COPY --from=rust-builder /build/target/release/delta-tui /usr/local/bin/delta-tui

# Copy application source code (all institutional packages)
COPY core/ /app/core/
COPY data/ /app/data/
COPY delta_os/ /app/delta_os/
COPY execution/ /app/execution/
COPY finance_model/ /app/finance_model/
COPY governance/ /app/governance/
COPY native/ /app/native/
COPY research/ /app/research/
COPY risk/ /app/risk/
COPY apps/ /app/apps/
COPY config/ /app/config/
COPY quant/ /app/quant/
COPY agents/ /app/agents/
COPY ai/ /app/ai/
COPY trader/ /app/trader/
COPY storage/ /app/storage/
COPY observability/ /app/observability/
COPY provenance/ /app/provenance/
COPY security/ /app/security/
COPY simulation/ /app/simulation/
COPY learning/ /app/learning/
COPY market_data/ /app/market_data/
COPY config.yaml /app/config.yaml

# Install package in environment
RUN pip install --no-cache-dir -e .

# Secure container defaults: require auth for RPC bridge over non-loopback network
ENV DELTA_REQUIRE_RPC_AUTH=1

# Set ownership and permissions
RUN chown -R deltauser:deltauser /app /home/deltauser
USER deltauser

# Initialize user directory
RUN mkdir -p /home/deltauser/.delta

# Expose JSON-RPC 2.0 Protocol Bridge (8765) and Prometheus Telemetry (9108)
EXPOSE 8765 9108

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD curl -f http://127.0.0.1:8765/healthz || exit 1

ENTRYPOINT ["python", "-m", "apps.cli.main"]
CMD ["serve", "--port", "8765"]
