package connector

import (
	"context"

	"github.com/economic-trading/gateway/internal/domain"
)

// ExchangeConnector defines the interface for all exchange integrations
type ExchangeConnector interface {
	Connect(ctx context.Context) error
	Disconnect(ctx context.Context) error

	GetOrderBook(symbol string) (*domain.OrderBook, error)
	PlaceOrder(order *domain.Order) (*domain.OrderResult, error)
	CancelOrder(orderID string) error
}

// ExchangeManager manages the lifecycle of multiple exchange connections
type ExchangeManager struct {
	connectors map[string]ExchangeConnector
}

func NewExchangeManager() *ExchangeManager {
	return &ExchangeManager{
		connectors: make(map[string]ExchangeConnector),
	}
}

func (m *ExchangeManager) Register(name string, connector ExchangeConnector) {
	m.connectors[name] = connector
}
