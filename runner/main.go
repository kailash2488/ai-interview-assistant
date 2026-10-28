package main

import (
	"bytes"
	"context"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
)

const (
	maxBodyBytes   = 30_000
	maxCodeChars   = 20_000
	maxStdinChars  = 4_000
	maxOutputBytes = 20_000
)

type server struct {
	token, runtime, image string
	limit                 chan struct{}
	sequence              atomic.Uint64
}

type runRequest struct {
	Language       string  `json:"language"`
	Code           string  `json:"code"`
	Stdin          string  `json:"stdin"`
	TimeoutSeconds float64 `json:"timeout_seconds"`
	Network        bool    `json:"network"`
	ReadOnly       bool    `json:"read_only"`
	MemoryMB       int     `json:"memory_mb"`
	CPUSeconds     int     `json:"cpu_seconds"`
	Pids           int     `json:"pids"`
}

type runResponse struct {
	ExitCode *int   `json:"exit_code"`
	Stdout   string `json:"stdout"`
	Stderr   string `json:"stderr"`
	TimedOut bool   `json:"timed_out"`
}

type cappedBuffer struct {
	bytes.Buffer
	limit int
}

func (b *cappedBuffer) Write(p []byte) (int, error) {
	n := len(p)
	remaining := b.limit - b.Len()
	if remaining > 0 {
		if remaining > len(p) {
			remaining = len(p)
		}
		_, _ = b.Buffer.Write(p[:remaining])
	}
	return n, nil
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func main() {
	token := os.Getenv("RUNNER_TOKEN")
	if len(token) < 32 {
		log.Fatal("RUNNER_TOKEN must contain at least 32 characters")
	}
	concurrency, err := strconv.Atoi(env("RUNNER_CONCURRENCY", "2"))
	if err != nil || concurrency < 1 || concurrency > 8 {
		log.Fatal("RUNNER_CONCURRENCY must be between 1 and 8")
	}
	s := &server{token: token, runtime: env("RUNNER_RUNTIME", "runsc"), image: env("RUNNER_IMAGE", "aia-python-sandbox:3.12"), limit: make(chan struct{}, concurrency)}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", s.health)
	mux.HandleFunc("POST /run", s.run)
	h := &http.Server{Addr: ":8081", Handler: http.MaxBytesHandler(mux, maxBodyBytes), ReadHeaderTimeout: 2 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 30 * time.Second}
	log.Print("isolated runner listening on :8081")
	log.Fatal(h.ListenAndServe())
}

func (s *server) authorized(r *http.Request) bool {
	provided := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	return len(provided) == len(s.token) && subtle.ConstantTimeCompare([]byte(provided), []byte(s.token)) == 1
}

func jsonReply(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func (s *server) health(w http.ResponseWriter, r *http.Request) {
	if !s.authorized(r) {
		jsonReply(w, http.StatusUnauthorized, map[string]any{"ready": false})
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	runtimes, err1 := exec.CommandContext(ctx, "docker", "info", "--format", "{{json .Runtimes}}").Output()
	_, err2 := exec.CommandContext(ctx, "docker", "image", "inspect", s.image).Output()
	ready := err1 == nil && err2 == nil && strings.Contains(string(runtimes), `"`+s.runtime+`"`)
	detail := "Runner ready: fresh gVisor sandbox, no network, non-root, read-only filesystem and strict resource limits."
	if !ready {
		detail = "Runner is not ready. Verify Docker access, register the gVisor runtime, and build the sandbox image."
	}
	jsonReply(w, http.StatusOK, map[string]any{"ready": ready, "detail": detail})
}

func validate(req runRequest) error {
	if req.Language != "python" {
		return errors.New("only python is supported")
	}
	if len(req.Code) == 0 || len(req.Code) > maxCodeChars || len(req.Stdin) > maxStdinChars || strings.ContainsRune(req.Code, 0) || strings.ContainsRune(req.Stdin, 0) {
		return errors.New("invalid code or stdin size")
	}
	if req.Network || !req.ReadOnly || req.MemoryMB != 128 || req.CPUSeconds != 2 || req.Pids != 32 || req.TimeoutSeconds < 1 || req.TimeoutSeconds > 8 {
		return errors.New("required isolation policy is missing")
	}
	return nil
}

func (s *server) dockerArgs(name string) []string {
	return []string{"run", "--rm", "--name", name, "--runtime", s.runtime, "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m", "--memory", "128m", "--memory-swap", "128m", "--cpus", "0.25", "--pids-limit", "32", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65534:65534", "--ulimit", "nofile=64:64", "--ulimit", "fsize=1048576:1048576", "--stop-timeout", "1", s.image}
}

func (s *server) run(w http.ResponseWriter, r *http.Request) {
	if !s.authorized(r) {
		jsonReply(w, http.StatusUnauthorized, map[string]string{"detail": "unauthorized"})
		return
	}
	var req runRequest
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil || validate(req) != nil {
		jsonReply(w, http.StatusUnprocessableEntity, map[string]string{"detail": "invalid execution request"})
		return
	}
	select {
	case s.limit <- struct{}{}:
		defer func() { <-s.limit }()
	default:
		jsonReply(w, http.StatusTooManyRequests, map[string]string{"detail": "runner is busy"})
		return
	}
	name := fmt.Sprintf("aia-run-%d-%d", time.Now().UnixNano(), s.sequence.Add(1))
	timeout := time.Duration(req.TimeoutSeconds * float64(time.Second))
	ctx, cancel := context.WithTimeout(r.Context(), timeout)
	defer cancel()
	payload, _ := json.Marshal(map[string]string{"code": req.Code, "stdin": req.Stdin})
	cmd := exec.CommandContext(ctx, "docker", s.dockerArgs(name)...)
	cmd.Stdin = bytes.NewReader(payload)
	stdout, stderr := &cappedBuffer{limit: maxOutputBytes}, &cappedBuffer{limit: maxOutputBytes}
	cmd.Stdout, cmd.Stderr = stdout, stderr
	err := cmd.Run()
	// CommandContext should terminate the CLI; force cleanup in case the daemon kept the sandbox.
	cleanup, cleanupCancel := context.WithTimeout(context.Background(), 2*time.Second)
	_ = exec.CommandContext(cleanup, "docker", "rm", "-f", name).Run()
	cleanupCancel()
	timedOut := errors.Is(ctx.Err(), context.DeadlineExceeded)
	var exitCode *int
	if !timedOut {
		code := 0
		if err != nil {
			var ee *exec.ExitError
			if errors.As(err, &ee) {
				code = ee.ExitCode()
			} else {
				code = 125
			}
		}
		exitCode = &code
		if code == 125 {
			stderr.Buffer.Reset()
			_, _ = stderr.Write([]byte("The isolated runner could not start the sandbox."))
		}
	}
	jsonReply(w, http.StatusOK, runResponse{ExitCode: exitCode, Stdout: stdout.String(), Stderr: stderr.String(), TimedOut: timedOut})
}

var _ io.Writer = (*cappedBuffer)(nil)
