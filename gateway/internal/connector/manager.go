package connector

import (
	"context"
	"fmt"
	"time"

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

// StartAll starts all registered connectors with automatic retry logic
func (m *ExchangeManager) StartAll(ctx context.Context) {
	for name, connector := range m.connectors {
		go m.maintainConnection(ctx, name, connector)
	}
}

func (m *ExchangeManager) maintainConnection(ctx context.Context, name string, connector ExchangeConnector) {
	backoff := time.Second
	maxBackoff := 30 * time.Second

	for {
		select {
		case <-ctx.Done():
			return
		default:
			fmt.Printf("[%s] Connecting...\n", name)
			if err := connector.Connect(ctx); err != nil {
				fmt.Printf("[%s] Connection failed: %v. Retrying in %v\n", name, err, backoff)
				time.Sleep(backoff)

				// Exponential backoff
				backoff *= 2
				if backoff > maxBackoff {
					backoff = maxBackoff
				}
				continue
			}

			// Connected successfully - reset backoff
			backoff = time.Second
			fmt.Printf("[%s] Connected.\n", name)

			// Wait for disconnection (blocking call or monitor)
			// Assuming Connect is blocking or we verify health here.
			// If Connect is non-blocking, we'd need a health check loop.
			// For this implementation, let's assume we need to wait/block until disconnect.
			// Ideally Connect() should block until error or context cancel.
			// If it returns immediately, we need a mechanism to wait.

			// Placeholder: Wait for context done or error channel from connector?
			// Since interface is simple, let's assume Connect blocks or we poll.
			// If Connect returns nil immediately, we sleep to avoid tight loop
			time.Sleep(5 * time.Second)
		}
	}
}
