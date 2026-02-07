package domain

// OrderBook represents a snapshot of the market
type OrderBook struct {
	Symbol    string
	Bids      []PriceLevel
	Asks      []PriceLevel
	Timestamp int64
}

type PriceLevel struct {
	Price    string // Using string to preserve decimal precision in JSON
	Quantity string
}

// Order represents a trading order
type Order struct {
	ID        string
	Symbol    string
	Side      string // "buy" or "sell"
	Type      string // "limit" or "market"
	Price     string
	Quantity  string
	Timestamp int64
}

// OrderResult represents the outcome of an order placement
type OrderResult struct {
	OrderID   string
	Status    string
	FilledQty string
	AvgPrice  string
}
