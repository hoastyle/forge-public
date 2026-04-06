package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

var (
	version   = "dev"
	commit    = "unknown"
	buildDate = "unknown"
)

const defaultHTTPTimeout = 30 * time.Second

type connection struct {
	Server     string
	Token      string
	Source     string
	ConfigPath string
}

type stringList []string

func (s *stringList) String() string {
	return strings.Join(*s, ",")
}

func (s *stringList) Set(value string) error {
	*s = append(*s, value)
	return nil
}

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	if len(args) == 0 {
		printUsage()
		return 2
	}

	switch args[0] {
	case "login":
		return runLogin(args[1:])
	case "logout":
		return runLogout()
	case "version":
		printJSON(map[string]string{
			"version":    version,
			"commit":     commit,
			"build_date": buildDate,
		})
		return 0
	case "doctor":
		return runDoctor(args[1:])
	case "inject":
		return runInject(args[1:])
	case "review-raw":
		return runQueueRead("review-raw", args[1:])
	case "review-queue":
		return runQueueRead("review-queue", args[1:])
	case "promote-raw":
		return runPromoteRaw(args[1:])
	case "promote-ready":
		return runPromoteReady(args[1:])
	case "synthesize-insights":
		return runSynthesize(args[1:])
	case "receipt":
		return runReceipt(args[1:])
	case "job":
		return runJob(args[1:])
	default:
		printFailure("unknown command: " + args[0])
		return 1
	}
}

func runLogin(args []string) int {
	fs := flag.NewFlagSet("login", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	if err := fs.Parse(args); err != nil {
		printFailure(err.Error())
		return 2
	}
	if strings.TrimSpace(*server) == "" || strings.TrimSpace(*token) == "" {
		printFailure("login requires --server and --token")
		return 2
	}

	configPath, err := saveConnection(normalizeServer(*server), *token)
	if err != nil {
		printFailure(err.Error())
		return 1
	}
	printJSON(map[string]string{
		"status":      "success",
		"server":      normalizeServer(*server),
		"config_path": configPath,
		"message":     "remote server saved",
	})
	return 0
}

func runLogout() int {
	configPath, err := clearConnection()
	if err != nil {
		printFailure(err.Error())
		return 1
	}
	printJSON(map[string]string{
		"status":      "success",
		"config_path": configPath,
		"message":     "remote server cleared",
	})
	return 0
}

func runDoctor(args []string) int {
	fs := flag.NewFlagSet("doctor", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	if err := fs.Parse(args); err != nil {
		printFailure(err.Error())
		return 2
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	return runRemoteJSON(conn, http.MethodGet, "/v1/doctor", nil, nil)
}

func runInject(args []string) int {
	fs := flag.NewFlagSet("inject", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	text := fs.String("text", "", "")
	filePath := fs.String("file", "", "")
	feishuLink := fs.String("feishu-link", "", "")
	title := fs.String("title", "", "")
	source := fs.String("source", "", "")
	initiator := fs.String("initiator", "manual", "")
	promoteKnowledge := fs.Bool("promote-knowledge", false, "")
	detach := fs.Bool("detach", false, "")
	var tags stringList
	fs.Var(&tags, "tag", "")
	if err := fs.Parse(args); err != nil {
		printFailure(err.Error())
		return 2
	}

	sources := 0
	if strings.TrimSpace(*text) != "" {
		sources++
	}
	if strings.TrimSpace(*filePath) != "" {
		sources++
	}
	if strings.TrimSpace(*feishuLink) != "" {
		sources++
	}
	if sources != 1 {
		printFailure("inject requires exactly one of --text, --file, or --feishu-link")
		return 2
	}

	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}

	payload := map[string]interface{}{
		"title":             strings.TrimSpace(*title),
		"source":            strings.TrimSpace(*source),
		"initiator":         strings.TrimSpace(*initiator),
		"promote_knowledge": *promoteKnowledge,
		"detach":            *detach,
		"tags":              []string(tags),
	}

	switch {
	case strings.TrimSpace(*text) != "":
		payload["input_kind"] = "text"
		payload["content"] = *text
		payload["source_ref"] = "inline:text"
	case strings.TrimSpace(*filePath) != "":
		content, err := ioutil.ReadFile(*filePath)
		if err != nil {
			printFailure(err.Error())
			return 1
		}
		payload["input_kind"] = "file"
		payload["content"] = string(content)
		payload["source_ref"] = *filePath
	default:
		payload["input_kind"] = "feishu_link"
		payload["link"] = *feishuLink
	}

	return runRemoteJSON(conn, http.MethodPost, "/v1/inject", payload, nil)
}

func runQueueRead(command string, args []string) int {
	fs := flag.NewFlagSet(command, flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	initiator := fs.String("initiator", "manual", "")
	if err := fs.Parse(args); err != nil {
		printFailure(err.Error())
		return 2
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	path := "/v1/" + command
	return runRemoteJSON(conn, http.MethodGet, path, nil, map[string]string{"initiator": *initiator})
}

func runPromoteRaw(args []string) int {
	fs := flag.NewFlagSet("promote-raw", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	initiator := fs.String("initiator", "manual", "")
	detach := fs.Bool("detach", false, "")
	if err := fs.Parse(args); err != nil {
		printFailure(err.Error())
		return 2
	}
	if fs.NArg() != 1 {
		printFailure("promote-raw requires exactly one raw_ref argument")
		return 2
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	payload := map[string]interface{}{
		"raw_ref":   fs.Arg(0),
		"initiator": *initiator,
		"detach":    *detach,
	}
	return runRemoteJSON(conn, http.MethodPost, "/v1/promote-raw", payload, nil)
}

func runPromoteReady(args []string) int {
	fs := flag.NewFlagSet("promote-ready", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	initiator := fs.String("initiator", "manual", "")
	dryRun := fs.Bool("dry-run", false, "")
	limit := fs.Int("limit", -1, "")
	confirmReceipt := fs.String("confirm-receipt", "", "")
	detach := fs.Bool("detach", false, "")
	if err := fs.Parse(args); err != nil {
		printFailure(err.Error())
		return 2
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	payload := map[string]interface{}{
		"initiator":       *initiator,
		"dry_run":         *dryRun,
		"confirm_receipt": strings.TrimSpace(*confirmReceipt),
		"detach":          *detach,
	}
	if *limit >= 0 {
		payload["limit"] = *limit
	}
	return runRemoteJSON(conn, http.MethodPost, "/v1/promote-ready", payload, nil)
}

func runSynthesize(args []string) int {
	fs := flag.NewFlagSet("synthesize-insights", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	initiator := fs.String("initiator", "manual", "")
	detach := fs.Bool("detach", false, "")
	if err := fs.Parse(args); err != nil {
		printFailure(err.Error())
		return 2
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	payload := map[string]interface{}{
		"initiator": *initiator,
		"detach":    *detach,
	}
	return runRemoteJSON(conn, http.MethodPost, "/v1/synthesize-insights", payload, nil)
}

func runReceipt(args []string) int {
	if len(args) == 0 || args[0] != "get" {
		printFailure("receipt supports only `receipt get <selector>`")
		return 2
	}
	fs := flag.NewFlagSet("receipt get", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	if err := fs.Parse(args[1:]); err != nil {
		printFailure(err.Error())
		return 2
	}
	if fs.NArg() != 1 {
		printFailure("receipt get requires a selector")
		return 2
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	return runRemoteJSON(conn, http.MethodGet, "/v1/receipt", nil, map[string]string{"selector": fs.Arg(0)})
}

func runJob(args []string) int {
	if len(args) == 0 || args[0] != "get" {
		printFailure("job supports only `job get <job_id>`")
		return 2
	}
	fs := flag.NewFlagSet("job get", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	if err := fs.Parse(args[1:]); err != nil {
		printFailure(err.Error())
		return 2
	}
	if fs.NArg() != 1 {
		printFailure("job get requires a job_id")
		return 2
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	return runRemoteJSON(conn, http.MethodGet, "/v1/jobs/"+fs.Arg(0), nil, nil)
}

func requireConnection(serverOverride string, tokenOverride string) (*connection, int) {
	conn, err := resolveConnection(serverOverride, tokenOverride)
	if err != nil {
		printFailure(err.Error())
		return nil, 1
	}
	if conn == nil || strings.TrimSpace(conn.Server) == "" {
		printFailure("no Forge service configured; use `forge login --server <url> --token <token>` or set FORGE_SERVER/FORGE_TOKEN")
		return nil, 1
	}
	return conn, 0
}

func runRemoteJSON(conn *connection, method string, path string, payload interface{}, query map[string]string) int {
	response, code, err := requestJSON(conn, method, path, payload, query)
	if err != nil && len(response) == 0 {
		printFailure(err.Error())
		return 1
	}
	printJSON(response)
	if code >= 400 {
		return 1
	}
	return 0
}

func requestJSON(conn *connection, method string, path string, payload interface{}, query map[string]string) (map[string]interface{}, int, error) {
	baseURL, err := url.Parse(normalizeServer(conn.Server))
	if err != nil {
		return nil, 0, err
	}
	relativePath, err := url.Parse(path)
	if err != nil {
		return nil, 0, err
	}
	fullURL := baseURL.ResolveReference(relativePath)
	if query != nil {
		values := fullURL.Query()
		for key, value := range query {
			if strings.TrimSpace(value) != "" {
				values.Set(key, value)
			}
		}
		fullURL.RawQuery = values.Encode()
	}

	var body io.Reader
	if payload != nil {
		encoded, err := json.Marshal(payload)
		if err != nil {
			return nil, 0, err
		}
		body = bytes.NewReader(encoded)
	}

	req, err := http.NewRequest(method, fullURL.String(), body)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Accept", "application/json")
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if strings.TrimSpace(conn.Token) != "" {
		req.Header.Set("Authorization", "Bearer "+strings.TrimSpace(conn.Token))
	}

	client := &http.Client{Timeout: resolveHTTPTimeout()}
	resp, err := client.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()

	rawBody, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, err
	}
	parsed := map[string]interface{}{}
	if len(rawBody) > 0 {
		if err := json.Unmarshal(rawBody, &parsed); err != nil {
			parsed["status"] = "failed"
			parsed["message"] = strings.TrimSpace(string(rawBody))
		}
	}
	if len(parsed) == 0 {
		parsed["status"] = "success"
	}
	if resp.StatusCode >= 400 {
		if _, ok := parsed["status"]; !ok {
			parsed["status"] = "failed"
		}
		if _, ok := parsed["message"]; !ok {
			parsed["message"] = resp.Status
		}
		return parsed, resp.StatusCode, fmt.Errorf("%v", parsed["message"])
	}
	return parsed, resp.StatusCode, nil
}

func resolveConnection(serverOverride string, tokenOverride string) (*connection, error) {
	serverOverride = normalizeServer(serverOverride)
	tokenOverride = strings.TrimSpace(tokenOverride)
	configConn, err := loadConnection()
	if err != nil {
		return nil, err
	}

	if serverOverride != "" {
		token := tokenOverride
		if token == "" {
			token = strings.TrimSpace(os.Getenv("FORGE_TOKEN"))
		}
		if token == "" && configConn != nil {
			token = configConn.Token
		}
		return &connection{Server: serverOverride, Token: token, Source: "flag"}, nil
	}

	envServer := normalizeServer(os.Getenv("FORGE_SERVER"))
	if envServer != "" {
		return &connection{
			Server: envServer,
			Token:  strings.TrimSpace(os.Getenv("FORGE_TOKEN")),
			Source: "environment",
		}, nil
	}

	return configConn, nil
}

func loadConnection() (*connection, error) {
	configPath, err := configFilePath()
	if err != nil {
		return nil, err
	}
	data, err := ioutil.ReadFile(configPath)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	values := map[string]string{}
	for _, line := range strings.Split(string(data), "\n") {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		parts := strings.SplitN(trimmed, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		value := strings.TrimSpace(parts[1])
		unquoted, err := strconv.Unquote(value)
		if err == nil {
			value = unquoted
		}
		values[key] = value
	}

	server := normalizeServer(values["server"])
	if server == "" {
		return nil, nil
	}
	return &connection{
		Server:     server,
		Token:      strings.TrimSpace(values["token"]),
		Source:     "config",
		ConfigPath: configPath,
	}, nil
}

func saveConnection(server string, token string) (string, error) {
	configPath, err := configFilePath()
	if err != nil {
		return "", err
	}
	if err := os.MkdirAll(filepath.Dir(configPath), 0700); err != nil {
		return "", err
	}
	content := fmt.Sprintf("server = %q\ntoken = %q\n", normalizeServer(server), strings.TrimSpace(token))
	if err := ioutil.WriteFile(configPath, []byte(content), 0600); err != nil {
		return "", err
	}
	return configPath, nil
}

func clearConnection() (string, error) {
	configPath, err := configFilePath()
	if err != nil {
		return "", err
	}
	if err := os.Remove(configPath); err != nil && !os.IsNotExist(err) {
		return "", err
	}
	parent := filepath.Dir(configPath)
	_ = os.Remove(parent)
	return configPath, nil
}

func configFilePath() (string, error) {
	configHome := strings.TrimSpace(os.Getenv("XDG_CONFIG_HOME"))
	if configHome == "" {
		homeDir, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		configHome = filepath.Join(homeDir, ".config")
	}
	return filepath.Join(configHome, "forge", "config.toml"), nil
}

func normalizeServer(raw string) string {
	return strings.TrimRight(strings.TrimSpace(raw), "/")
}

func resolveHTTPTimeout() time.Duration {
	raw := strings.TrimSpace(os.Getenv("FORGE_HTTP_TIMEOUT"))
	if raw == "" {
		return defaultHTTPTimeout
	}
	timeout, err := time.ParseDuration(raw)
	if err != nil || timeout <= 0 {
		return defaultHTTPTimeout
	}
	return timeout
}

func printJSON(payload interface{}) {
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	_ = encoder.Encode(payload)
}

func printFailure(message string) {
	printJSON(map[string]string{
		"status":  "failed",
		"message": message,
	})
}

func printUsage() {
	printJSON(map[string]interface{}{
		"status": "failed",
		"message": "usage: forge <login|logout|version|doctor|inject|review-raw|review-queue|promote-raw|promote-ready|synthesize-insights|receipt get|job get> ...",
	})
}
