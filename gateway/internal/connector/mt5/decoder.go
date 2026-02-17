package mt5

import (
	"encoding/binary"
	"errors"
)

// SBE Header layout (Little Endian)
const HeaderSize = 8

type SbeHeader struct {
	BlockLength uint16
	TemplateID  uint16
	SchemaID    uint16
	Version     uint16
}

// OrderResult represents the Execution Report from MT5 (ID 2)
type OrderResult struct {
	Header   SbeHeader
	OrderID  int64
	SymbolID int64
	Side     byte
	Price    float64 // Converted from decimal9
	Quantity float64 // Converted from decimal9
}

// MarketData represents a Tick from MT5 (ID 3)
type MarketData struct {
	Header    SbeHeader
	SymbolID  int64
	Timestamp int64
	Bid       float64
	Ask       float64
	Volume    float64
	Flags     uint8
}

// Decoder handles binary parsing
type Decoder struct{}

func DecodeHeader(data []byte) (SbeHeader, error) {
	if len(data) < HeaderSize {
		return SbeHeader{}, errors.New("buffer too short for header")
	}
	return SbeHeader{
		BlockLength: binary.LittleEndian.Uint16(data[0:2]),
		TemplateID:  binary.LittleEndian.Uint16(data[2:4]),
		SchemaID:    binary.LittleEndian.Uint16(data[4:6]),
		Version:     binary.LittleEndian.Uint16(data[6:8]),
	}, nil
}

// DecodeOrderResult parses ID 2
func DecodeOrderResult(header SbeHeader, data []byte) (*OrderResult, error) {
	// Body validation
	if len(data) < int(HeaderSize+header.BlockLength) {
		return nil, errors.New("buffer too short for order body")
	}

	body := data[HeaderSize : HeaderSize+header.BlockLength]

	// Layout ID 2:
	// 0-8: OrderID (i64)
	// 8-16: SymbolID (i64)
	// 16-17: Side (char/byte)
	// 17-25: Price (decimal9 -> i64 mantissa)
	// 25-33: Quantity (decimal9 -> i64 mantissa)

	orderID := int64(binary.LittleEndian.Uint64(body[0:8]))
	symbolID := int64(binary.LittleEndian.Uint64(body[8:16]))
	side := body[16]

	priceMantissa := int64(binary.LittleEndian.Uint64(body[17:25]))
	qtyMantissa := int64(binary.LittleEndian.Uint64(body[25:33]))

	price := float64(priceMantissa) / 1e9
	qty := float64(qtyMantissa) / 1e9

	return &OrderResult{
		Header:   header,
		OrderID:  orderID,
		SymbolID: symbolID,
		Side:     side,
		Price:    price,
		Quantity: qty,
	}, nil
}

// DecodeMarketData parses ID 3
func DecodeMarketData(header SbeHeader, data []byte) (*MarketData, error) {
	// Body validation
	// ID 3 BlockLength should be 8+8+8+8+8+1 = 41 bytes?
	// Field offsets:
	// Symbol(8) + Time(8) + Bid(8) + Ask(8) + Vol(8) + Flags(1) = 41 bytes.

	if len(data) < int(HeaderSize+header.BlockLength) {
		return nil, errors.New("buffer too short for market data body")
	}

	body := data[HeaderSize : HeaderSize+header.BlockLength]

	// Layout ID 3:
	// 0-8: Symbol
	// 8-16: Timestamp
	// 16-24: Bid
	// 24-32: Ask
	// 32-40: Volume
	// 40: Flags

	symbolID := int64(binary.LittleEndian.Uint64(body[0:8]))
	ts := int64(binary.LittleEndian.Uint64(body[8:16]))

	bidM := int64(binary.LittleEndian.Uint64(body[16:24]))
	askM := int64(binary.LittleEndian.Uint64(body[24:32]))
	volM := int64(binary.LittleEndian.Uint64(body[32:40]))
	flags := body[40]

	return &MarketData{
		Header:    header,
		SymbolID:  symbolID,
		Timestamp: ts,
		Bid:       float64(bidM) / 1e9,
		Ask:       float64(askM) / 1e9,
		Volume:    float64(volM) / 1e9,
		Flags:     flags,
	}, nil
}
