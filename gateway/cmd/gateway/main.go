package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"regexp"
	"syscall"
	"time"

	"github.com/economic-trading/gateway/internal/connector/mt5"
	"github.com/economic-trading/gateway/internal/middleware"
	"github.com/economic-trading/gateway/internal/pipeline"
)

var validSymbolRe = regexp.MustCompile(`^[A-Za-z0-9]{2,20}$`)

func main() {
	log.Println("Starting Gateway Service...")
	startTime := time.Now()

	// 1. Start Data Recorder (Pipeline)
	// In Docker, /app/data is a volume
	cfg := pipeline.Config{
		BasePath:      "./data",
		RotInterval:   1 * time.Hour,
		BufferSize:    10000,
		MaxFileSizeMB: 100,
		FlushInterval: 5 * time.Second,
	}
	recorder, err := pipeline.NewRecorder(cfg)
	if err != nil {
		log.Fatalf("Failed to init recorder: %v", err)
	}
	recorder.Start()
	defer recorder.Stop()

	// 2. Start MT5 Bridge (TCP Listener)
	// Port 5555
	bridge := mt5.NewServer(recorder)
	if err := bridge.Start(); err != nil {
		log.Fatalf("Failed to start bridge: %v", err)
	}

	// 3. Setup HTTP API (Health + RBAC)
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(fmt.Sprintf(
			`{"status":"ok","service":"gateway","recorder_running":%t,"uptime_s":%.0f}`,
			recorder.IsRunning(),
			time.Since(startTime).Seconds(),
		)))
	})

	// Example Admin Route
	mux.Handle("/admin", middleware.RBAC(middleware.RoleAdmin)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("Admin Access"))
	})))

	// Signal API for GoliathHybrid EA
	// Proxies to Analysis container's signal server
	analysisHost := os.Getenv("ANALYSIS_HOST")
	if analysisHost == "" {
		analysisHost = "analysis:8000"
	}
	signalClient := &http.Client{Timeout: 10 * time.Second}

	mux.HandleFunc("/api/signal/", func(w http.ResponseWriter, r *http.Request) {
		symbol := r.URL.Path[len("/api/signal/"):]
		if symbol == "" {
			http.Error(w, "Symbol required", http.StatusBadRequest)
			return
		}
		if !validSymbolRe.MatchString(symbol) {
			http.Error(w, "Invalid symbol format", http.StatusBadRequest)
			return
		}

		// Proxy to Python Analysis signal server
		timeframe := r.URL.Query().Get("timeframe")
		if timeframe == "" {
			timeframe = "H1"
		}
		validTF := map[string]bool{"M1": true, "M5": true, "M15": true, "M30": true, "H1": true, "H4": true, "D1": true}
		if !validTF[timeframe] {
			http.Error(w, "Invalid timeframe", http.StatusBadRequest)
			return
		}
		url := fmt.Sprintf("http://%s/predict/%s?timeframe=%s", analysisHost, symbol, timeframe)

		resp, err := signalClient.Get(url)
		if err != nil {
			log.Printf("Analysis proxy error: %v", err)
			w.Header().Set("Content-Type", "application/json")
			w.Write([]byte(`{"direction":"HOLD","confidence":0,"reasoning":"Analysis service unavailable"}`))
			return
		}
		defer resp.Body.Close()

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	})

	handler := middleware.PIIScrubber(mux)

	server := &http.Server{
		Addr:         ":8080",
		Handler:      handler,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 5 * time.Second,
	}

	// Graceful shutdown on SIGTERM/SIGINT
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Println("Gateway HTTP listening on :8080")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal(err)
		}
	}()

	<-sigChan
	log.Println("Shutdown signal received, draining connections...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Printf("HTTP server shutdown error: %v", err)
	}
	log.Println("Gateway stopped gracefully.")
}
