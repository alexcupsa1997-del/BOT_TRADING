package middleware

import (
	"context"
	"net/http"
)

// Role definitions
type Role string

const (
	RoleAdmin   Role = "admin"
	RoleTrader  Role = "trader"
	RoleAuditor Role = "auditor"
	RoleViewer  Role = "viewer"
)

// Context keys
type contextKey string

const (
	ContextKeyUserRole contextKey = "user_role"
	ContextKeyUserID   contextKey = "user_id"
)

// RBACConfig holds configuration for the middleware
type RBACConfig struct {
	Enforce bool
}

// RBAC middleware enforces role-based access
func RBAC(requiredRole Role) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// 1. Extract Role from Context (populated by JWT Auth Middleware previously)
			// In a real flow, the Auth middleware runs BEFORE this and injects the role.
			// For this implementation, we assume the role is already in the context.
			userRole, ok := r.Context().Value(ContextKeyUserRole).(Role)

			if !ok {
				// No role found -> Unauthenticated or internal error in chain
				http.Error(w, "Unauthorized: No role found in context", http.StatusUnauthorized)
				return
			}

			// 2. Evaluate Permissions (Principle of Least Privilege)
			if !hasPermission(userRole, requiredRole) {
				http.Error(w, "Forbidden: Insufficient privileges", http.StatusForbidden)
				return
			}

			// 3. Pass to next handler
			next.ServeHTTP(w, r)
		})
	}
}

// hasPermission determines if userRole satisfies the requiredRole
// Hierarchy: Admin > Trader > Auditor > Viewer
func hasPermission(userRole, requiredRole Role) bool {
	if userRole == RoleAdmin {
		return true // Admin has access to everything
	}

	if userRole == requiredRole {
		return true
	}

	// Hierarchy implementation
	switch userRole {
	case RoleTrader:
		// Trader can do Viewer things, but not Auditor (SoD?)
		// Let's stick to strict matching or simple hierarchy.
		// User requirement: Segregation of Duties.
		// Admin = Config. Trader = Trade. Auditor = Audit.
		// Mixing them violates SoD if we aren't careful.

		// For now, let's implement strict role checks for critical paths,
		// but allow hierarchy for "Read" operations.
		if requiredRole == RoleViewer {
			return true
		}
	case RoleAuditor:
		if requiredRole == RoleViewer {
			return true
		}
	}

	return false
}

// MockAuthMiddleware is a helper for testing to inject roles
func MockAuthMiddleware(role Role) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := context.WithValue(r.Context(), ContextKeyUserRole, role)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}
