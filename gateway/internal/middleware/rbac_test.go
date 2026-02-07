package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestRBAC(t *testing.T) {
	tests := []struct {
		name         string
		userRole     Role
		requiredRole Role
		wantStatus   int
	}{
		{
			name:         "Admin accessing Admin route",
			userRole:     RoleAdmin,
			requiredRole: RoleAdmin,
			wantStatus:   http.StatusOK,
		},
		{
			name:         "Trader trying to access Admin route",
			userRole:     RoleTrader,
			requiredRole: RoleAdmin,
			wantStatus:   http.StatusForbidden,
		},
		{
			name:         "Trader accessing Trader route",
			userRole:     RoleTrader,
			requiredRole: RoleTrader,
			wantStatus:   http.StatusOK,
		},
		{
			name:         "Auditor accessing Viewer route",
			userRole:     RoleAuditor,
			requiredRole: RoleViewer,
			wantStatus:   http.StatusOK,
		},
		{
			name:         "Trader accessing Auditor route (SoD check)",
			userRole:     RoleTrader,
			requiredRole: RoleAuditor,
			wantStatus:   http.StatusForbidden,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Build the chain: MockAuth -> RBAC -> FinalHandler
			finalHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusOK)
			})

			rbac := RBAC(tt.requiredRole)
			auth := MockAuthMiddleware(tt.userRole)

			handler := auth(rbac(finalHandler))

			req := httptest.NewRequest("GET", "/", nil)
			w := httptest.NewRecorder()

			handler.ServeHTTP(w, req)

			if w.Code != tt.wantStatus {
				t.Errorf("RBAC() status = %v, want %v", w.Code, tt.wantStatus)
			}
		})
	}
}

func TestRBAC_NoRole(t *testing.T) {
	// Test case where no role is in context
	finalHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	rbac := RBAC(RoleAdmin)
	// No Auth middleware

	req := httptest.NewRequest("GET", "/", nil)
	w := httptest.NewRecorder()

	rbac(finalHandler).ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("RBAC() status = %v, want %v (Unauthorized)", w.Code, http.StatusUnauthorized)
	}
}
