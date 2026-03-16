# Stage 1: Build
FROM golang:1.23-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -o /chat-server ./cmd/server/main.go

FROM alpine:latest

WORKDIR /

COPY --from=builder /chat-server /chat-server


EXPOSE 8006

CMD ["/chat-server"]