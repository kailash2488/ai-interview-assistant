FROM golang:1.24-alpine AS build
WORKDIR /src
COPY go.mod main.go main_test.go ./
RUN go test ./...
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /runner ./main.go

FROM docker:28-cli
RUN addgroup -S runner && adduser -S -G runner runner
COPY --from=build /runner /usr/local/bin/aia-runner
EXPOSE 8081
ENTRYPOINT ["/usr/local/bin/aia-runner"]
