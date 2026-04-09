package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func captureRun(t *testing.T, args []string) (int, map[string]interface{}) {
	t.Helper()

	originalStdout := os.Stdout
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatalf("pipe: %v", err)
	}
	os.Stdout = writer

	code := run(args)

	if err := writer.Close(); err != nil {
		t.Fatalf("close writer: %v", err)
	}
	os.Stdout = originalStdout

	var buffer bytes.Buffer
	if _, err := buffer.ReadFrom(reader); err != nil {
		t.Fatalf("read stdout: %v", err)
	}
	if err := reader.Close(); err != nil {
		t.Fatalf("close reader: %v", err)
	}

	var payload map[string]interface{}
	if err := json.Unmarshal(buffer.Bytes(), &payload); err != nil {
		t.Fatalf("decode payload %q: %v", buffer.String(), err)
	}
	return code, payload
}

func runRemoteMutationCommand(t *testing.T, args []string, expectedPath string, assertRequest func(map[string]interface{})) {
	t.Helper()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != expectedPath {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		assertRequest(payload)
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(map[string]interface{}{"status": "queued"}); err != nil {
			t.Fatalf("encode response: %v", err)
		}
	}))
	defer server.Close()

	fullArgs := append([]string{}, args...)
	fullArgs = append(fullArgs, "--server", server.URL, "--token", "secret")
	code, payload := captureRun(t, fullArgs)
	if code != 0 {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
	if payload["status"] != "queued" {
		t.Fatalf("payload=%v", payload)
	}
}

func TestRemoteMutationCommandsDefaultToDetach(t *testing.T) {
	tests := []struct {
		name string
		args []string
		path string
	}{
		{"inject", []string{"inject", "--text", "hello world"}, "/v1/inject"},
		{"promote-raw", []string{"promote-raw", "raw/123"}, "/v1/promote-raw"},
		{"promote-ready", []string{"promote-ready"}, "/v1/promote-ready"},
		{"synthesize-insights", []string{"synthesize-insights"}, "/v1/synthesize-insights"},
	}
	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			runRemoteMutationCommand(t, tt.args, tt.path, func(payload map[string]interface{}) {
				detach, ok := payload["detach"].(bool)
				if !ok || !detach {
					t.Fatalf("expected detach true payload=%v", payload)
				}
			})
		})
	}
}

func TestRemoteMutationWaitFlagClearsDetach(t *testing.T) {
	tests := []struct {
		name string
		args []string
		path string
	}{
		{"inject", []string{"inject", "--text", "hello world", "--wait"}, "/v1/inject"},
		{"promote-raw", []string{"promote-raw", "raw/123", "--wait"}, "/v1/promote-raw"},
		{"promote-ready", []string{"promote-ready", "--wait"}, "/v1/promote-ready"},
		{"synthesize-insights", []string{"synthesize-insights", "--wait"}, "/v1/synthesize-insights"},
	}
	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			runRemoteMutationCommand(t, tt.args, tt.path, func(payload map[string]interface{}) {
				detach, ok := payload["detach"].(bool)
				if !ok || detach {
					t.Fatalf("expected detach false payload=%v", payload)
				}
			})
		})
	}
}

func TestRemoteMutationRejectsWaitWithDetach(t *testing.T) {
	code, payload := captureRun(t, []string{
		"inject",
		"--text", "hello world",
		"--wait",
		"--detach",
	})
	if code != 2 {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
	if payload["status"] != "failed" {
		t.Fatalf("payload=%v", payload)
	}
	message, _ := payload["message"].(string)
	if !strings.Contains(message, "--wait") || !strings.Contains(message, "--detach") {
		t.Fatalf("unexpected message %q", message)
	}
}

func TestRunTopLevelHelpTokensSucceed(t *testing.T) {
	for _, args := range [][]string{{"help"}, {"--help"}, {"-h"}} {
		code, payload := captureRun(t, args)
		if code != 0 {
			t.Fatalf("args %v returned %d payload=%v", args, code, payload)
		}
		if payload["status"] != "success" {
			t.Fatalf("args %v payload=%v", args, payload)
		}
		message, _ := payload["message"].(string)
		if !strings.Contains(message, "usage: forge") {
			t.Fatalf("missing usage in payload=%v", payload)
		}
	}
}

func TestRunPromoteReadyHelpShowsSupportedFlagsOnly(t *testing.T) {
	code, payload := captureRun(t, []string{"promote-ready", "--help"})
	if code != 0 {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
	if payload["status"] != "success" {
		t.Fatalf("payload=%v", payload)
	}
	message, _ := payload["message"].(string)
	for _, expected := range []string{"--initiator", "--dry-run", "--limit", "--confirm-receipt", "--detach", "--wait"} {
		if !strings.Contains(message, expected) {
			t.Fatalf("missing %s in %q", expected, message)
		}
	}
	if strings.Contains(message, "synthesize-insights --dry-run") {
		t.Fatalf("unexpected synth preview text in %q", message)
	}
}

func TestRunSynthesizeHelpShowsExpectedFlags(t *testing.T) {
	code, payload := captureRun(t, []string{"synthesize-insights", "--help"})
	if code != 0 {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
	if payload["status"] != "success" {
		t.Fatalf("payload=%v", payload)
	}
	message, _ := payload["message"].(string)
	for _, expected := range []string{"--initiator", "--dry-run", "--confirm-receipt", "--detach", "--wait", "--operation-id"} {
		if !strings.Contains(message, expected) {
			t.Fatalf("missing %s in %q", expected, message)
		}
	}
}

func TestRunSynthesizeForwardsDryRunAndConfirmReceipt(t *testing.T) {
	t.Run("dry run", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path != "/v1/synthesize-insights" {
				t.Fatalf("unexpected path %s", r.URL.Path)
			}
			var payload map[string]interface{}
			if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
				t.Fatalf("decode request: %v", err)
			}
			if payload["dry_run"] != true {
				t.Fatalf("dry_run not true payload=%v", payload)
			}
			if payload["confirm_receipt"] != "" {
				t.Fatalf("unexpected confirm_receipt payload=%v", payload)
			}
			w.Header().Set("Content-Type", "application/json")
			if err := json.NewEncoder(w).Encode(map[string]interface{}{"status": "queued"}); err != nil {
				t.Fatalf("encode response: %v", err)
			}
		}))
		defer server.Close()

		code, payload := captureRun(t, []string{
			"synthesize-insights",
			"--server", server.URL,
			"--token", "secret",
			"--dry-run",
		})
		if code != 0 {
			t.Fatalf("code=%d payload=%v", code, payload)
		}
		if payload["status"] != "queued" {
			t.Fatalf("unexpected payload=%v", payload)
		}
	})

	t.Run("confirm receipt", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path != "/v1/synthesize-insights" {
				t.Fatalf("unexpected path %s", r.URL.Path)
			}
			var payload map[string]interface{}
			if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
				t.Fatalf("decode request: %v", err)
			}
			if payload["dry_run"] != false {
				t.Fatalf("unexpected dry_run payload=%v", payload)
			}
			if payload["confirm_receipt"] != "receipt/abc" {
				t.Fatalf("confirm_receipt missing payload=%v", payload)
			}
			w.Header().Set("Content-Type", "application/json")
			if err := json.NewEncoder(w).Encode(map[string]interface{}{"status": "queued"}); err != nil {
				t.Fatalf("encode response: %v", err)
			}
		}))
		defer server.Close()

		code, payload := captureRun(t, []string{
			"synthesize-insights",
			"--server", server.URL,
			"--token", "secret",
			"--confirm-receipt", "receipt/abc",
		})
		if code != 0 {
			t.Fatalf("code=%d payload=%v", code, payload)
		}
		if payload["status"] != "queued" {
			t.Fatalf("unexpected payload=%v", payload)
		}
	})
}

func TestRunSynthesizeRejectsConfirmReceiptWithDryRun(t *testing.T) {
	code, payload := captureRun(t, []string{
		"synthesize-insights",
		"--dry-run",
		"--confirm-receipt", "receipt/abc",
	})
	if code != 2 {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
	if payload["status"] != "failed" {
		t.Fatalf("payload=%v", payload)
	}
	message, _ := payload["message"].(string)
	if !strings.Contains(message, "--confirm-receipt") || !strings.Contains(message, "--dry-run") {
		t.Fatalf("unexpected message %q", message)
	}
}

func TestPromoteReadyForwardsOperationID(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/promote-ready" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		if payload["operation_id"] != "op-ready-1" {
			t.Fatalf("payload=%v", payload)
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(map[string]interface{}{
			"status":       "queued",
			"operation_id": "op-ready-1",
		}); err != nil {
			t.Fatalf("encode response: %v", err)
		}
	}))
	defer server.Close()

	code, payload := captureRun(t, []string{
		"promote-ready",
		"--server", server.URL,
		"--token", "secret",
		"--operation-id", "op-ready-1",
		"--detach",
	})
	if code != 0 {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
	if payload["operation_id"] != "op-ready-1" {
		t.Fatalf("payload=%v", payload)
	}
}

func TestKnowledgeGetUsesPublicEndpoint(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/knowledge" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		if got := r.URL.Query().Get("selector"); got != "knowledge/troubleshooting/example.md" {
			t.Fatalf("unexpected selector %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(map[string]interface{}{
			"status":        "success",
			"knowledge_ref": "knowledge/troubleshooting/example.md",
		}); err != nil {
			t.Fatalf("encode response: %v", err)
		}
	}))
	defer server.Close()

	code, payload := captureRun(t, []string{
		"knowledge", "get", "knowledge/troubleshooting/example.md",
		"--server", server.URL,
		"--token", "secret",
	})
	if code != 0 {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
	if payload["knowledge_ref"] != "knowledge/troubleshooting/example.md" {
		t.Fatalf("payload=%v", payload)
	}
}

func TestExplainInsightCommandUsesPublicEndpoint(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/explain/insight" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		if got := r.URL.Query().Get("receipt_ref"); got != "state/receipts/insights/example.json" {
			t.Fatalf("unexpected receipt_ref %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(map[string]interface{}{
			"status":      "success",
			"receipt_ref": "state/receipts/insights/example.json",
		}); err != nil {
			t.Fatalf("encode response: %v", err)
		}
	}))
	defer server.Close()

	code, payload := captureRun(t, []string{
		"explain", "insight", "state/receipts/insights/example.json",
		"--server", server.URL,
		"--token", "secret",
	})
	if code != 0 {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
	if payload["receipt_ref"] != "state/receipts/insights/example.json" {
		t.Fatalf("payload=%v", payload)
	}
}
