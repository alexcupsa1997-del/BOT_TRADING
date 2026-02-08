package mt5

import (
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"time"

	"github.com/economic-trading/gateway/internal/pipeline"
)

const (
	MaxFrameSize = 1024 * 64 // 64KB max packet
	Port         = ":5555"
)

type Server struct {
	listener net.Listener
	recorder *pipeline.Recorder
}

func NewServer(recorder *pipeline.Recorder) *Server {
	return &Server{
		recorder: recorder,
	}
}

func (s *Server) Start() error {
	addr, err := net.ResolveTCPAddr("tcp", Port)
	if err != nil {
		return err
	}

	l, err := net.ListenTCP("tcp", addr)
	if err != nil {
		return err
	}
	s.listener = l

	fmt.Printf("MT5 Bridge listening on %s\n", Port)

	go s.acceptLoop()
	return nil
}

func (s *Server) acceptLoop() {
	for {
		conn, err := s.listener.Accept()
		if err != nil {
			fmt.Println("Accept error:", err)
			continue
		}

		// Handle each connection in a goroutine
		go s.handleConnection(conn)
	}
}

func (s *Server) handleConnection(conn net.Conn) {
	defer conn.Close()
	fmt.Println("New MT5 Connection:", conn.RemoteAddr())

	// Stale Check / Heartbeat state
	// Stale Check / Heartbeat state
	// Using ReadDeadline directly for timeout

	// Using a buffer for framing
	headerBuf := make([]byte, 4) // 4 bytes length prefix

	for {
		// 1. Read Frame Length (4 bytes Big Endian as per Spec)
		if _, err := io.ReadFull(conn, headerBuf); err != nil {
			if err != io.EOF {
				fmt.Println("Read length error:", err)
			}
			return
		}

		length := binary.BigEndian.Uint32(headerBuf)
		if length > MaxFrameSize {
			fmt.Printf("DoS Protection: Frame too large (%d). Closing.\n", length)
			return
		}

		// 2. Read Body
		bodyBuf := make([]byte, length)
		if _, err := io.ReadFull(conn, bodyBuf); err != nil {
			fmt.Println("Read body error:", err)
			return
		}

		// 4. Update Heartbeat & Set ReadDeadline
		// Set a read deadline for the next frame (e.g., 5 seconds)
		// If no data is received within this window, ReadFull will timeout
		if err := conn.SetReadDeadline(time.Now().Add(5 * time.Second)); err != nil {
			fmt.Printf("SetReadDeadline Error: %v\n", err)
			return
		}

		// 5. Decode SBE
		header, err := DecodeHeader(bodyBuf)
		if err != nil {
			fmt.Printf("Header Decode Error: %v\n", err)
			continue
		}

		// Dispatch by Template ID
		switch header.TemplateID {
		case 2: // OrderResult
			order, err := DecodeOrderResult(header, bodyBuf)
			if err != nil {
				fmt.Printf("Order Decode Error: %v\n", err)
				continue
			}
			fmt.Printf("[EXECUTION] Order #%d %s %f @ %f\n",
				order.OrderID, string(order.Side), order.Quantity, order.Price)

		case 3: // MarketData
			tick, err := DecodeMarketData(header, bodyBuf)
			if err != nil {
				fmt.Printf("Tick Decode Error: %v\n", err)
				continue
			}

			// Push to Pipeline
			if s.recorder != nil {
				s.recorder.Record(pipeline.MarketTick{
					SymbolID:  tick.SymbolID,
					Timestamp: tick.Timestamp,
					Bid:       tick.Bid,
					Ask:       tick.Ask,
					Volume:    tick.Volume,
					Flags:     int32(tick.Flags),
				})
			}

			// Optional: Debug print for now
			// fmt.Printf("[TICK] %d Bid=%f Ask=%f\n", tick.SymbolID, tick.Bid, tick.Ask)

		default:
			fmt.Printf("Unknown Template ID: %d\n", header.TemplateID)
		}
	}
}
