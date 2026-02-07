package main

import (
	"log"
	"net/http"
	"time"

	"github.com/economic-trading/gateway/internal/connector/mt5"
	"github.com/economic-trading/gateway/internal/middleware"
	"github.com/economic-trading/gateway/internal/pipeline"
)

func main() {
	log.Println("Starting Gateway Service...")

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
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})

	// Example Admin Route
	mux.Handle("/admin", middleware.RBAC(middleware.RoleAdmin)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("Admin Access"))
	})))

	// Signal API for GoliathHybrid EA
	// Returns AI signal for a symbol
	mux.HandleFunc("/api/signal/", func(w http.ResponseWriter, r *http.Request) {
		symbol := r.URL.Path[len("/api/signal/"):]
		if symbol == "" {
			http.Error(w, "Symbol required", http.StatusBadRequest)
			return
		}

		// TODO: Connect to Python Brain for real signals
		// For now, return neutral signal
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"direction": "HOLD", "confidence": 0, "reason": "Awaiting Python Brain connection"}`))
	})

	handler := middleware.PIIScrubber(mux)

	server := &http.Server{
		Addr:         ":8080",
		Handler:      handler,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 5 * time.Second,
	}

	log.Println("Gateway HTTP listening on :8080")
	if err := server.ListenAndServe(); err != nil {
		log.Fatal(err)
	}
}
