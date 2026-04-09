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
		printUsageFailure()
		return 2
	}
	if isHelpToken(args[0]) {
		printUsageSuccess()
		return 0
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
	case "knowledge":
		return runKnowledge(args[1:])
	case "explain":
		return runExplain(args[1:])
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
	if ok, code := parseFlags(fs, args, loginHelpText()); !ok {
		return code
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
	if ok, code := parseFlags(fs, args, doctorHelpText()); !ok {
		return code
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
	operationID := fs.String("operation-id", "", "")
	var tags stringList
	fs.Var(&tags, "tag", "")
	if ok, code := parseFlags(fs, args, injectHelpText()); !ok {
		return code
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
	if strings.TrimSpace(*operationID) != "" {
		payload["operation_id"] = strings.TrimSpace(*operationID)
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
	if ok, code := parseFlags(fs, args, queueHelpText(command)); !ok {
		return code
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
	operationID := fs.String("operation-id", "", "")
	if ok, code := parseFlags(fs, reorderInterspersedArgs(args, map[string]bool{"detach": true}), promoteRawHelpText()); !ok {
		return code
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
	if strings.TrimSpace(*operationID) != "" {
		payload["operation_id"] = strings.TrimSpace(*operationID)
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
	operationID := fs.String("operation-id", "", "")
	if ok, code := parseFlags(fs, args, promoteReadyHelpText()); !ok {
		return code
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
	if strings.TrimSpace(*operationID) != "" {
		payload["operation_id"] = strings.TrimSpace(*operationID)
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
	operationID := fs.String("operation-id", "", "")
	if ok, code := parseFlags(fs, args, synthesizeHelpText()); !ok {
		return code
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	payload := map[string]interface{}{
		"initiator": *initiator,
		"detach":    *detach,
	}
	if strings.TrimSpace(*operationID) != "" {
		payload["operation_id"] = strings.TrimSpace(*operationID)
	}
	return runRemoteJSON(conn, http.MethodPost, "/v1/synthesize-insights", payload, nil)
}

func runKnowledge(args []string) int {
	if len(args) == 0 || isHelpToken(args[0]) {
		printHelp(knowledgeHelpText())
		return 0
	}
	if args[0] != "get" {
		printFailure("knowledge supports only `knowledge get <selector>`")
		return 2
	}
	fs := flag.NewFlagSet("knowledge get", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	if ok, code := parseFlags(fs, reorderInterspersedArgs(args[1:], map[string]bool{}), knowledgeGetHelpText()); !ok {
		return code
	}
	if fs.NArg() != 1 {
		printFailure("knowledge get requires a selector")
		return 2
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	return runRemoteJSON(conn, http.MethodGet, "/v1/knowledge", nil, map[string]string{"selector": fs.Arg(0)})
}

func runExplain(args []string) int {
	if len(args) == 0 || isHelpToken(args[0]) {
		printHelp(explainHelpText())
		return 0
	}
	if args[0] != "insight" {
		printFailure("explain supports only `explain insight <receipt_ref>`")
		return 2
	}
	fs := flag.NewFlagSet("explain insight", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	if ok, code := parseFlags(fs, reorderInterspersedArgs(args[1:], map[string]bool{}), explainInsightHelpText()); !ok {
		return code
	}
	if fs.NArg() != 1 {
		printFailure("explain insight requires a receipt_ref")
		return 2
	}
	conn, code := requireConnection(*server, *token)
	if code != 0 {
		return code
	}
	return runRemoteJSON(
		conn,
		http.MethodGet,
		"/v1/explain/insight",
		nil,
		map[string]string{"receipt_ref": fs.Arg(0)},
	)
}

func runReceipt(args []string) int {
	if len(args) == 0 || isHelpToken(args[0]) {
		printHelp(receiptHelpText())
		return 0
	}
	if len(args) == 0 || args[0] != "get" {
		printFailure("receipt supports only `receipt get <selector>`")
		return 2
	}
	fs := flag.NewFlagSet("receipt get", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	if ok, code := parseFlags(fs, reorderInterspersedArgs(args[1:], map[string]bool{}), receiptGetHelpText()); !ok {
		return code
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
	if len(args) == 0 || isHelpToken(args[0]) {
		printHelp(jobHelpText())
		return 0
	}
	if len(args) == 0 || args[0] != "get" {
		printFailure("job supports only `job get <job_id>`")
		return 2
	}
	fs := flag.NewFlagSet("job get", flag.ContinueOnError)
	fs.SetOutput(ioutil.Discard)
	server := fs.String("server", "", "")
	token := fs.String("token", "", "")
	if ok, code := parseFlags(fs, reorderInterspersedArgs(args[1:], map[string]bool{}), jobGetHelpText()); !ok {
		return code
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

func isHelpToken(value string) bool {
	trimmed := strings.TrimSpace(value)
	return trimmed == "help" || trimmed == "--help" || trimmed == "-h"
}

func parseFlags(fs *flag.FlagSet, args []string, helpText string) (bool, int) {
	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			printHelp(helpText)
			return false, 0
		}
		printFailure(err.Error())
		return false, 2
	}
	return true, 0
}

func reorderInterspersedArgs(args []string, booleanFlags map[string]bool) []string {
	flags := []string{}
	positionals := []string{}
	for index := 0; index < len(args); index++ {
		arg := args[index]
		if arg == "--" {
			positionals = append(positionals, args[index+1:]...)
			break
		}
		if strings.HasPrefix(arg, "-") {
			flags = append(flags, arg)
			if strings.Contains(arg, "=") {
				continue
			}
			flagName := strings.TrimLeft(arg, "-")
			if booleanFlags[flagName] {
				continue
			}
			if index+1 < len(args) {
				index++
				flags = append(flags, args[index])
			}
			continue
		}
		positionals = append(positionals, arg)
	}
	return append(flags, positionals...)
}

func topLevelUsageText() string {
	return strings.Join([]string{
		"usage: forge <login|logout|version|doctor|inject|review-raw|review-queue|promote-raw|promote-ready|synthesize-insights|knowledge get|explain insight|receipt get|job get> ...",
		"",
		"Use `forge <command> --help` for command-specific options.",
	}, "\n")
}

func loginHelpText() string {
	return strings.Join([]string{
		"usage: forge login --server <url> --token <token>",
		"",
		"Options:",
		"  --server <url>    Forge service URL to save in local config",
		"  --token <token>   bearer token to save in local config",
	}, "\n")
}

func doctorHelpText() string {
	return strings.Join([]string{
		"usage: forge doctor [--server <url>] [--token <token>]",
		"",
		"Options:",
		"  --server <url>    override configured Forge service URL",
		"  --token <token>   override configured bearer token",
	}, "\n")
}

func injectHelpText() string {
	return strings.Join([]string{
		"usage: forge inject (--text <content> | --file <path> | --feishu-link <url>) [options]",
		"",
		"Options:",
		"  --server <url>             override configured Forge service URL",
		"  --token <token>            override configured bearer token",
		"  --text <content>           inject inline text content",
		"  --file <path>              inject file content from disk",
		"  --feishu-link <url>        inject a Feishu document link",
		"  --title <title>            title to store with the raw note",
		"  --source <source>          provenance/source label",
		"  --tag <tag>               repeatable tag flag",
		"  --initiator <initiator>    provenance initiator value",
		"  --promote-knowledge        trigger raw -> knowledge after inject",
		"  --detach                   queue the mutation and return a job id",
		"  --operation-id <id>        stable mutation identifier for safe retries",
	}, "\n")
}

func queueHelpText(command string) string {
	return strings.Join([]string{
		"usage: forge " + command + " [--server <url>] [--token <token>] [--initiator <initiator>]",
		"",
		"Options:",
		"  --server <url>             override configured Forge service URL",
		"  --token <token>            override configured bearer token",
		"  --initiator <initiator>    provenance initiator value",
	}, "\n")
}

func promoteRawHelpText() string {
	return strings.Join([]string{
		"usage: forge promote-raw <raw_ref> [--server <url>] [--token <token>] [--initiator <initiator>] [--detach]",
		"",
		"Options:",
		"  --server <url>             override configured Forge service URL",
		"  --token <token>            override configured bearer token",
		"  --initiator <initiator>    provenance initiator value",
		"  --detach                   queue the mutation and return a job id",
		"  --operation-id <id>        stable mutation identifier for safe retries",
	}, "\n")
}

func promoteReadyHelpText() string {
	return strings.Join([]string{
		"usage: forge promote-ready [--server <url>] [--token <token>] [--initiator <initiator>] [--dry-run] [--limit <n>] [--confirm-receipt <receipt_ref>] [--detach]",
		"",
		"Options:",
		"  --server <url>                   override configured Forge service URL",
		"  --token <token>                  override configured bearer token",
		"  --initiator <initiator>          provenance initiator value",
		"  --dry-run                        preview the ready batch without promoting",
		"  --limit <n>                      limit the number of ready items inspected",
		"  --confirm-receipt <receipt_ref>  execute a previously previewed ready batch",
		"  --detach                         queue the mutation and return a job id",
		"  --operation-id <id>              stable mutation identifier for safe retries",
	}, "\n")
}

func synthesizeHelpText() string {
	return strings.Join([]string{
		"usage: forge synthesize-insights [--server <url>] [--token <token>] [--initiator <initiator>] [--detach]",
		"",
		"Options:",
		"  --server <url>             override configured Forge service URL",
		"  --token <token>            override configured bearer token",
		"  --initiator <initiator>    provenance initiator value",
		"  --detach                   queue the mutation and return a job id",
		"  --operation-id <id>        stable mutation identifier for safe retries",
	}, "\n")
}

func receiptHelpText() string {
	return strings.Join([]string{
		"usage: forge receipt get <selector>",
		"",
		"Use `forge receipt get --help` for selector options.",
	}, "\n")
}

func knowledgeHelpText() string {
	return strings.Join([]string{
		"usage: forge knowledge get <knowledge_ref>",
		"",
		"Use `forge knowledge get --help` for selector options.",
	}, "\n")
}

func knowledgeGetHelpText() string {
	return strings.Join([]string{
		"usage: forge knowledge get <knowledge_ref> [--server <url>] [--token <token>]",
		"",
		"Options:",
		"  --server <url>    override configured Forge service URL",
		"  --token <token>   override configured bearer token",
	}, "\n")
}

func explainHelpText() string {
	return strings.Join([]string{
		"usage: forge explain insight <receipt_ref>",
		"",
		"Use `forge explain insight --help` for selector options.",
	}, "\n")
}

func explainInsightHelpText() string {
	return strings.Join([]string{
		"usage: forge explain insight <receipt_ref> [--server <url>] [--token <token>]",
		"",
		"Options:",
		"  --server <url>    override configured Forge service URL",
		"  --token <token>   override configured bearer token",
	}, "\n")
}

func receiptGetHelpText() string {
	return strings.Join([]string{
		"usage: forge receipt get <selector> [--server <url>] [--token <token>]",
		"",
		"Options:",
		"  --server <url>    override configured Forge service URL",
		"  --token <token>   override configured bearer token",
	}, "\n")
}

func jobHelpText() string {
	return strings.Join([]string{
		"usage: forge job get <job_id>",
		"",
		"Use `forge job get --help` for polling options.",
	}, "\n")
}

func jobGetHelpText() string {
	return strings.Join([]string{
		"usage: forge job get <job_id> [--server <url>] [--token <token>]",
		"",
		"Options:",
		"  --server <url>    override configured Forge service URL",
		"  --token <token>   override configured bearer token",
	}, "\n")
}

func printJSON(payload interface{}) {
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	_ = encoder.Encode(payload)
}

func printHelp(message string) {
	printJSON(map[string]string{
		"status":  "success",
		"message": message,
	})
}

func printFailure(message string) {
	printJSON(map[string]string{
		"status":  "failed",
		"message": message,
	})
}

func printUsageSuccess() {
	printHelp(topLevelUsageText())
}

func printUsageFailure() {
	printFailure(topLevelUsageText())
}
