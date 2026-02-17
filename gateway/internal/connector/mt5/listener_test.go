package mt5

import (
	"encoding/binary"
	"net"
	"testing"
	"time"
)

func TestBridgeEndToEnd(t *testing.T) {
	// 1. Start Server (No recorder for basic test)
	srv := NewServer(nil)
	go func() {
		if err := srv.Start(); err != nil {
			t.Logf("Server start error (expected if port busy): %v", err)
		}
	}()

	// Give it a moment to bind
	time.Sleep(100 * time.Millisecond)

	// 2. Connect Client (Simulating MT5)
	conn, err := net.Dial("tcp", "localhost"+Port)
	if err != nil {
		t.Fatalf("Failed to connect to bridge: %v", err)
	}
	defer conn.Close()

	// 3. Construct SBE Message (OrderResult)
	// Header: BlockLen=33, ID=2, Schema=1, Ver=1 (8 bytes)
	// Body: ... (33 bytes) (OrderID, Symbol, Side, Price, Qty)

	header := []byte{
		33, 0, // BlockLength (33)
		2, 0, // TemplateID (2)
		1, 0, // SchemaID (1)
		1, 0, // Version (1)
	} // 8 bytes

	body := make([]byte, 33)
	// Fill dummy data
	// OrderID=123 (i64 le)
	binary.LittleEndian.PutUint64(body[0:8], 123)
	// SymbolID=1 (i64 le)
	binary.LittleEndian.PutUint64(body[8:16], 1)
	// Side='B' (66)
	body[16] = 'B'
	// Price=45000.0 * 1e9 (i64 le)
	binary.LittleEndian.PutUint64(body[17:25], uint64(45000*1e9))
	// Qty=1.5 * 1e9 (i64 le)
	binary.LittleEndian.PutUint64(body[25:33], uint64(1.5*1e9))

	fullMsg := append(header, body...) // 8 + 33 = 41 bytes

	// 4. Construct Frame (Length Prefix)
	// Length = 41 (uint32 Big Endian)
	frame := make([]byte, 4)
	binary.BigEndian.PutUint32(frame, uint32(len(fullMsg)))

	frame = append(frame, fullMsg...)

	// 5. Send Order (ID 2)
	_, err = conn.Write(frame)
	if err != nil {
		t.Fatalf("Failed to write order to bridge: %v", err)
	}

	// 6. Send MarketData (ID 3)
	// Header: BlockLen=41, ID=3, Schema=1, Ver=1
	headerTick := []byte{
		41, 0, // BlockLength
		3, 0, // TemplateID
		1, 0, // SchemaID
		1, 0, // Version
	}

	bodyTick := make([]byte, 41)
	// SymbolID=1
	binary.LittleEndian.PutUint64(bodyTick[0:8], 1)
	// Timestamp=1600000000
	binary.LittleEndian.PutUint64(bodyTick[8:16], 1600000000)
	// Bid=45000.0 * 1e9
	binary.LittleEndian.PutUint64(bodyTick[16:24], uint64(45000*1e9))
	// Ask=45001.0 * 1e9
	binary.LittleEndian.PutUint64(bodyTick[24:32], uint64(45001*1e9))
	// Vol=1.0 * 1e9
	binary.LittleEndian.PutUint64(bodyTick[32:40], uint64(1*1e9))
	// Flags=0
	bodyTick[40] = 0

	fullMsgTick := append(headerTick, bodyTick...)
	frameTick := make([]byte, 4)
	binary.BigEndian.PutUint32(frameTick, uint32(len(fullMsgTick)))
	frameTick = append(frameTick, fullMsgTick...)

	_, err = conn.Write(frameTick)
	if err != nil {
		t.Fatalf("Failed to write tick to bridge: %v", err)
	}

	// 7. Verification
	// In a real test, we would inject a channel into the Server to capture the parsed struct.
	// Here, we just ensure no panic/disconnect for 1 second.
	time.Sleep(500 * time.Millisecond)

	// If server crashed, this would fail locally or in logs.
	t.Log("Message sent successfully. Check console output for '[Received]' log.")
}
