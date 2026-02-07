# Build Stage
FROM golang:latest AS builder

WORKDIR /app

# Dependencies
COPY go.mod go.sum ./
RUN go mod download

# Source
COPY . .

# Build
RUN CGO_ENABLED=0 go build -o gateway ./cmd/gateway/main.go

# Runtime Stage
FROM alpine:latest

WORKDIR /app

RUN apk add --no-cache ca-certificates

# Copy Binary
COPY --from=builder /app/gateway .

# Expose HTTP and MT5 TCP
EXPOSE 8080
EXPOSE 5555

# Data Volume
VOLUME ["/app/data"]

CMD ["./gateway"]
