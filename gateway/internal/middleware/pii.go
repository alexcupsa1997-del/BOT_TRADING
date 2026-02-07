package middleware

import (
	"bytes"
	"io"
	"net/http"
	"regexp"
)

// PII Regex Patterns
var (
	emailRegex    = regexp.MustCompile(`(?i)[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}`)
	phoneRegex    = regexp.MustCompile(`\b\d{3}[-.]?\d{3}[-.]?\d{4}\b`)
	ssnRegex      = regexp.MustCompile(`\b\d{3}-\d{2}-\d{4}\b`)
	apiKeyRegex   = regexp.MustCompile(`(?i)(api_key|apikey|secret|token)["']?\s*[:=]\s*["']?([a-zA-Z0-9_\-]{20,})["']?`)
	jwtRegex      = regexp.MustCompile(`ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*`)
)

// PIIScrubber wraps an http.Handler and sanitizes request/response bodies in logs
// Note: In production, this would integrate with a structured logger like Zap
func PIIScrubber(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 1. Scrub URL query params
		scrubbedQuery := scrubString(r.URL.RawQuery)
		if scrubbedQuery != r.URL.RawQuery {
			r.URL.RawQuery = scrubbedQuery
		}

		// 2. Scrub Body (Limit size to prevent DoS)
		// Read body
		bodyBytes, _ := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20)) // 1MB limit
		r.Body.Close() // Close original

		// Scrub
		scrubbedBody := scrubBytes(bodyBytes)
		
		// Restore body
		r.Body = io.NopCloser(bytes.NewBuffer(scrubbedBody))

		// 3. Pass to next handler
		next.ServeHTTP(w, r)
	})
}

func scrubString(input string) string {
	scrubbed := input
	scrubbed = emailRegex.ReplaceAllString(scrubbed, "[EMAIL_REDACTED]")
	scrubbed = phoneRegex.ReplaceAllString(scrubbed, "[PHONE_REDACTED]")
	scrubbed = ssnRegex.ReplaceAllString(scrubbed, "[SSN_REDACTED]")
	scrubbed = apiKeyRegex.ReplaceAllString(scrubbed, "$1=[REDACTED_SECRET]")
	scrubbed = jwtRegex.ReplaceAllString(scrubbed, "[JWT_REDACTED]")
	return scrubbed
}

func scrubBytes(input []byte) []byte {
	return []byte(scrubString(string(input)))
}
