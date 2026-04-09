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
	for _, expected := range []string{"--initiator", "--dry-run", "--limit", "--confirm-receipt", "--detach"} {
		if !strings.Contains(message, expected) {
			t.Fatalf("missing %s in %q", expected, message)
		}
	}
	if strings.Contains(message, "synthesize-insights --dry-run") {
		t.Fatalf("unexpected synth preview text in %q", message)
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
