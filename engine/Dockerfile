# Build Stage
FROM rust:alpine AS builder

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
FROM alpine:latest

WORKDIR /app

# Copy Binaries
COPY --from=builder /app/target/release/backtester .
# COPY --from=builder /app/target/release/sbe_consumer . 

# Data Volume
VOLUME ["/app/data"]

CMD ["./backtester"]
