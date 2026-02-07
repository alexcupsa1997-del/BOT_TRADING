package pipeline

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/parquet-go/parquet-go"
)

// Config defines the recorder behavior
type Config struct {
	BasePath      string
	RotInterval   time.Duration
	BufferSize    int
	MaxFileSizeMB int64
	FlushInterval time.Duration
}

// MarketTick represents the schema for Parquet
type MarketTick struct {
	SymbolID  int64   `parquet:"symbol_id"`
	Timestamp int64   `parquet:"timestamp"` // Unix Millis
	Bid       float64 `parquet:"bid"`
	Ask       float64 `parquet:"ask"`
	Volume    float64 `parquet:"volume"`
	Flags     int32   `parquet:"flags"` // Parquet doesn't like uint8, use int32
}

// Recorder manages the lifecycle of data ingestion
type Recorder struct {
	cfg  Config
	ch   chan MarketTick
	wg   sync.WaitGroup
	quit chan struct{}

	currentFile *os.File
	writer      *parquet.GenericWriter[MarketTick]
	lastRot     time.Time

	// Metrics
	ticksProcessed uint64
	ticksDropped   uint64
}

// NewRecorder creates a ready-to-start recorder
func NewRecorder(cfg Config) (*Recorder, error) {
	if err := os.MkdirAll(cfg.BasePath, 0755); err != nil {
		return nil, err
	}

	return &Recorder{
		cfg:  cfg,
		ch:   make(chan MarketTick, cfg.BufferSize),
		quit: make(chan struct{}),
	}, nil
}

// Start begins the async worker
func (r *Recorder) Start() {
	r.wg.Add(1)
	go r.worker()
}

// Stop initiates graceful shutdown
func (r *Recorder) Stop() {
	close(r.quit)
	r.wg.Wait()
}

// Record pushes a tick to the buffer. Non-blocking (drops if full).
// Enterprise principle: Better to lose history than to block the Trading Engine path.
func (r *Recorder) Record(tick MarketTick) {
	select {
	case r.ch <- tick:
		// success
	default:
		// Buffer full - Drop!
		// In a real system, we might increment a metric counter here.
		// atomic.AddUint64(&r.ticksDropped, 1)
	}
}

func (r *Recorder) worker() {
	defer r.wg.Done()

	// Open initial rotation
	if err := r.rotate(); err != nil {
		fmt.Printf("Initial rotation failed: %v\n", err)
		return
	}
	defer r.closeCurrent()

	ticker := time.NewTicker(r.cfg.FlushInterval)
	defer ticker.Stop()

	for {
		select {
		case tick := <-r.ch:
			// Write to parquet buffer (in memory)
			if _, err := r.writer.Write([]MarketTick{tick}); err != nil {
				fmt.Printf("Write error: %v\n", err)
			}

			// Check rotation constraints (Time or Size)
			// Size check is expensive on every tick, so we might rely mostly on Time or check periodically
			if time.Since(r.lastRot) > r.cfg.RotInterval {
				if err := r.rotate(); err != nil {
					fmt.Printf("Rotation failure: %v\n", err)
				}
			}

		case <-ticker.C:
			// Periodic Flush to disk
			if r.writer != nil {
				r.writer.Flush()
			}

		case <-r.quit:
			// Drain remaining buffer before exit
			r.drain()
			return
		}
	}
}

func (r *Recorder) drain() {
	for {
		select {
		case tick := <-r.ch:
			r.writer.Write([]MarketTick{tick})
		default:
			return
		}
	}
}

func (r *Recorder) rotate() error {
	r.closeCurrent()

	now := time.Now()
	filename := fmt.Sprintf("ticks_%s.parquet", now.Format("20060102_150405"))
	path := filepath.Join(r.cfg.BasePath, filename)

	f, err := os.Create(path)
	if err != nil {
		return err
	}

	r.currentFile = f
	r.writer = parquet.NewGenericWriter[MarketTick](f)
	r.lastRot = now

	fmt.Printf("[Recorder] Rotated to %s\n", filename)
	return nil
}

func (r *Recorder) closeCurrent() {
	if r.writer != nil {
		r.writer.Close()
		r.writer = nil
	}
	if r.currentFile != nil {
		r.currentFile.Close()
		r.currentFile = nil
	}
}
