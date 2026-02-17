# Build Stage
FROM rust:1.84-alpine AS builder

WORKDIR /app

RUN apk add --no-cache musl-dev

# Dependency Caching Trick
COPY Cargo.toml Cargo.lock ./
# Create dummy src to compile deps
RUN mkdir src && echo "fn main() {}" > src/main.rs
# RUN cargo build --release --bin backtester # Fail if bin doesn't exist yet in config
# Just copy source for simplicity in this iteration
COPY src ./src

# Build
# Building all binaries
RUN cargo build --release --bins

# Runtime Stage
FROM alpine:3.21

WORKDIR /app

# Copy Binaries
COPY --from=builder /app/target/release/backtester .
# COPY --from=builder /app/target/release/sbe_consumer .

# Data Volume
VOLUME ["/app/data"]

# Run as non-root
RUN adduser -D appuser
USER appuser

CMD ["./backtester"]
