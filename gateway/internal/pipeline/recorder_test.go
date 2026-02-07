package pipeline

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/parquet-go/parquet-go"
)

func TestRecorderLifecycle(t *testing.T) {
	// Setup temp dir
	tmpDir := t.TempDir()

	cfg := Config{
		BasePath:      tmpDir,
		RotInterval:   2 * time.Second, // Fast rotation for test
		BufferSize:    100,
		FlushInterval: 100 * time.Millisecond,
	}

	out, err := NewRecorder(cfg)
	if err != nil {
		t.Fatalf("Failed to create recorder: %v", err)
	}

	out.Start()

	// 1. Ingest Data
	ticks := []MarketTick{
		{SymbolID: 1, Timestamp: 1000, Bid: 100.0, Ask: 101.0, Volume: 1.0},
		{SymbolID: 1, Timestamp: 1001, Bid: 100.1, Ask: 101.1, Volume: 2.0},
		{SymbolID: 1, Timestamp: 1002, Bid: 100.2, Ask: 101.2, Volume: 3.0},
	}

	for _, tick := range ticks {
		out.Record(tick)
	}

	// Wait for rotation logic (optional, mainly testing shutdown flush here)
	time.Sleep(500 * time.Millisecond)

	// 2. Stop (Should flush everything)
	out.Stop()

	// 3. Verify Files
	files, err := os.ReadDir(tmpDir)
	if err != nil {
		t.Fatalf("Failed to read dir: %v", err)
	}

	if len(files) == 0 {
		t.Fatal("No files created")
	}

	// 4. Read Parquet back to verify integrity
	parquetFile, err := os.Open(filepath.Join(tmpDir, files[0].Name()))
	if err != nil {
		t.Fatalf("Failed to open parquet file: %v", err)
	}
	defer parquetFile.Close()

	reader := parquet.NewGenericReader[MarketTick](parquetFile)
	readRows := make([]MarketTick, len(ticks))
	n, err := reader.Read(readRows)

	if err != nil && err.Error() != "EOF" {
		t.Fatalf("Read error: %v", err) // EOF is expected if read exact amount
	}

	if n != len(ticks) {
		t.Errorf("Expected %d rows, got %d", len(ticks), n)
	}

	if readRows[0].Bid != 100.0 {
		t.Errorf("Data corruption: Expected 100.0, got %f", readRows[0].Bid)
	}
}
