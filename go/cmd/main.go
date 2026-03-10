package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math/big"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"
)

type llmRuntimeConfig struct {
	provider          string
	modelName         string
	apiKey            string
	baseURL           string
	temperature       float32
	seed              int
	requestTimeoutSec int
	enableThinking    bool
	maxRetryAttempts  int
	retryBaseMs       int
	retryJitterMs     int
}

type tokenUsageSummary struct {
	modelCalls       int
	promptTokens     int
	completionTokens int
	totalTokens      int
}

type decisionRequest struct {
	AgentID        int      `json:"agent_id"`
	Openness       float64  `json:"openness"`
	RiskTolerance  float64  `json:"risk_tolerance"`
	AdoptedRatio   float64  `json:"adopted_ratio"`
	EmotionArousal float64  `json:"emotion_arousal"`
	WOMStrength    string   `json:"wom_strength"`
	WOMMessages    []string `json:"wom_messages"`
	InnovationCoef float64  `json:"innovation_coef"`
	ImitationCoef  float64  `json:"imitation_coef"`
	ContextKey     string   `json:"context_key"`
}

type decisionResponse struct {
	Adopt            bool    `json:"adopt"`
	Probability      float64 `json:"probability"`
	Reasoning        string  `json:"reasoning"`
	Source           string  `json:"source"`
	ModelCalls       int     `json:"model_calls"`
	PromptTokens     int     `json:"prompt_tokens"`
	CachedTokens     int     `json:"cached_tokens"`
	CompletionTokens int     `json:"completion_tokens"`
	TotalTokens      int     `json:"total_tokens"`
}

func (s *tokenUsageSummary) add(promptTokens int, completionTokens int, totalTokens int) {
	s.modelCalls++
	s.promptTokens += promptTokens
	s.completionTokens += completionTokens
	s.totalTokens += totalTokens
}

func loadDotEnv(path string) error {
	file, err := os.Open(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.Trim(strings.TrimSpace(parts[1]), "\"`")
		if key == "" {
			continue
		}
		if os.Getenv(key) == "" {
			_ = os.Setenv(key, val)
		}
	}
	return scanner.Err()
}

func getEnvOrDefault(key string, fallback string) string {
	val := strings.TrimSpace(os.Getenv(key))
	if val == "" {
		return fallback
	}
	return val
}

func parseFloat32OrDefault(raw string, fallback float32) float32 {
	if raw == "" {
		return fallback
	}
	val, err := strconv.ParseFloat(raw, 32)
	if err != nil {
		return fallback
	}
	return float32(val)
}

func parseIntOrDefault(raw string, fallback int) int {
	if raw == "" {
		return fallback
	}
	val, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return val
}

func parseBoolOrDefault(raw string, fallback bool) bool {
	if raw == "" {
		return fallback
	}
	val, err := strconv.ParseBool(raw)
	if err != nil {
		return fallback
	}
	return val
}

func readRuntimeConfig() llmRuntimeConfig {
	baseURL := getEnvOrDefault("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
	retryAttempts := parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_RETRY_MAX_ATTEMPTS")), 3)
	if retryAttempts < 1 {
		retryAttempts = 1
	}
	retryBaseMs := parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_RETRY_BASE_MS")), 200)
	if retryBaseMs < 50 {
		retryBaseMs = 50
	}
	retryJitterMs := parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_RETRY_JITTER_MS")), 120)
	if retryJitterMs < 0 {
		retryJitterMs = 0
	}
	return llmRuntimeConfig{
		provider:          getEnvOrDefault("LLM_PROVIDER", "aliyun_bailian"),
		modelName:         getEnvOrDefault("LLM_MODEL", "qwen3.5-flash"),
		apiKey:            strings.TrimSpace(os.Getenv("LLM_API_KEY")),
		baseURL:           baseURL,
		temperature:       parseFloat32OrDefault(strings.TrimSpace(os.Getenv("LLM_TEMPERATURE")), 0.2),
		seed:              parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_SEED")), 42),
		requestTimeoutSec: parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_REQUEST_TIMEOUT_SECONDS")), 120),
		enableThinking:    parseBoolOrDefault(strings.TrimSpace(os.Getenv("LLM_ENABLE_THINKING")), false),
		maxRetryAttempts:  retryAttempts,
		retryBaseMs:       retryBaseMs,
		retryJitterMs:     retryJitterMs,
	}
}

func runtimeTimeout(cfg llmRuntimeConfig) time.Duration {
	timeoutSec := cfg.requestTimeoutSec
	if timeoutSec <= 0 {
		timeoutSec = 120
	}
	return time.Duration(timeoutSec) * time.Second
}

func buildDecisionInstruction() string {
	researchProtocol := strings.Join([]string{
		"研究协议固定前缀：",
		"1) 研究对象是新产品扩散中的普通消费者个体，不是研究员、顾问或营销文案作者。",
		"2) 每次仅做单步二元采纳判断，不做跨期策略规划，不引入未给定变量。",
		"3) 决策依据限定为个体特质、邻里采纳比例、口碑强度与最近口碑内容。",
		"4) 不允许使用‘我建议企业’‘我认为实验应当’等研究者话语。",
		"5) 概率含义为当前时间步采纳倾向，不等于长期市场份额预测。",
		"6) 若信息不足，可在reasoning中说明不确定性，但仍需给出0到1概率。",
		"7) 不得编造统计显著性、外部样本、真实用户访谈或不存在的历史数据。",
		"8) 当邻里采纳比例升高时，模仿效应可增强，但需结合风险偏好与开放性。",
		"9) 当口碑情绪更强时，短期采纳冲动可提升，但并不必然导致采纳。",
		"10) 口碑消息只使用最近片段，不引用未出现的消息来源。",
		"11) 输出字段固定 adopt/probability/reasoning，字段名不得增删改。",
		"12) 禁止输出markdown、代码块、列表符号或任何JSON外文本。",
		"13) reasoning保持一到两句，聚焦机制，不写修辞。",
		"14) 概率必须闭区间[0,1]，小数精度可自行控制。",
		"15) 该前缀用于稳定实验语义边界。",
	}, "\n")
	return strings.Join([]string{
		researchProtocol,
		"你正在模拟一名普通消费者在当前时间步是否采纳新产品。",
		"你会收到一个JSON对象，包含个体特质、社会影响和口碑信息。",
		"请仅输出JSON对象，字段必须是 adopt(boolean), probability(number), reasoning(string)。",
		"不要输出任何额外文本。",
	}, "\n")
}

func clampProbability(raw float64) float64 {
	if raw < 0 {
		return 0
	}
	if raw > 1 {
		return 1
	}
	return raw
}

func extractJSONObject(text string) string {
	start := strings.Index(text, "{")
	end := strings.LastIndex(text, "}")
	if start < 0 || end < 0 || end < start {
		return "{}"
	}
	return text[start : end+1]
}

func parseDecisionText(text string) (decisionResponse, error) {
	raw := extractJSONObject(text)
	var payload struct {
		Adopt       bool    `json:"adopt"`
		Probability float64 `json:"probability"`
		Reasoning   string  `json:"reasoning"`
	}
	if err := json.Unmarshal([]byte(raw), &payload); err != nil {
		adoptRE := regexp.MustCompile(`(?i)"?adopt"?\s*[:=]\s*(true|false|1|0)`)
		probRE := regexp.MustCompile(`(?i)"?probability"?\s*[:=]\s*([0-9]*\.?[0-9]+)`)
		reasonRE := regexp.MustCompile(`(?i)"?reasoning"?\s*[:=]\s*"([^"]*)"`)
		adoptMatch := adoptRE.FindStringSubmatch(text)
		probMatch := probRE.FindStringSubmatch(text)
		if len(adoptMatch) < 2 || len(probMatch) < 2 {
			return decisionResponse{}, err
		}
		adoptRaw := strings.ToLower(strings.TrimSpace(adoptMatch[1]))
		adoptVal := adoptRaw == "true" || adoptRaw == "1"
		probVal, convErr := strconv.ParseFloat(strings.TrimSpace(probMatch[1]), 64)
		if convErr != nil {
			return decisionResponse{}, err
		}
		reason := ""
		reasonMatch := reasonRE.FindStringSubmatch(text)
		if len(reasonMatch) >= 2 {
			reason = strings.TrimSpace(reasonMatch[1])
		}
		payload.Adopt = adoptVal
		payload.Probability = probVal
		payload.Reasoning = reason
	}
	res := decisionResponse{
		Adopt:       payload.Adopt,
		Probability: clampProbability(payload.Probability),
		Reasoning:   strings.TrimSpace(payload.Reasoning),
		Source:      "llm_http_direct",
	}
	if payload.Probability == 0 && payload.Adopt {
		res.Probability = 0.5
	}
	if payload.Probability > 0 && payload.Probability < 0.5 {
		res.Adopt = false
	}
	if payload.Probability >= 0.5 {
		res.Adopt = true
	}
	return res, nil
}

func buildDecisionQuery(req decisionRequest) string {
	payload := map[string]any{
		"agent_profile": map[string]any{
			"agent_id":       req.AgentID,
			"openness":       req.Openness,
			"risk_tolerance": req.RiskTolerance,
		},
		"social_context": map[string]any{
			"adopted_ratio":   req.AdoptedRatio,
			"wom_strength":    req.WOMStrength,
			"emotion_arousal": req.EmotionArousal,
		},
		"wom_messages_recent": req.WOMMessages,
		"bass_params": map[string]any{
			"innovation_coef": req.InnovationCoef,
			"imitation_coef":  req.ImitationCoef,
		},
		"task": "输出单步采纳决策JSON",
	}
	buf, err := json.Marshal(payload)
	if err != nil {
		return "{}"
	}
	return string(buf)
}

func buildChatCompletionsURL(baseURL string) string {
	return strings.TrimRight(strings.TrimSpace(baseURL), "/") + "/chat/completions"
}

func isRetriableStatus(statusCode int) bool {
	return statusCode == http.StatusBadGateway ||
		statusCode == http.StatusTooManyRequests ||
		statusCode == http.StatusServiceUnavailable ||
		statusCode == http.StatusGatewayTimeout
}

func jitterDuration(maxJitterMs int) time.Duration {
	if maxJitterMs <= 0 {
		return 0
	}
	n, err := rand.Int(rand.Reader, big.NewInt(int64(maxJitterMs+1)))
	if err != nil {
		return 0
	}
	return time.Duration(n.Int64()) * time.Millisecond
}

func retryBackoff(attempt int, cfg llmRuntimeConfig) time.Duration {
	if attempt <= 0 {
		return 0
	}
	baseMs := cfg.retryBaseMs
	step := attempt - 1
	if step > 5 {
		step = 5
	}
	delayMs := baseMs * (1 << step)
	return time.Duration(delayMs)*time.Millisecond + jitterDuration(cfg.retryJitterMs)
}

func runDecision(ctx context.Context, client *http.Client, cfg llmRuntimeConfig, req decisionRequest) (decisionResponse, error) {
	usageSummary := &tokenUsageSummary{}
	payload := map[string]any{
		"model":           cfg.modelName,
		"temperature":     cfg.temperature,
		"seed":            cfg.seed,
		"enable_thinking": cfg.enableThinking,
		"response_format": map[string]any{
			"type": "json_object",
		},
		"messages": []map[string]any{
			{
				"role":    "system",
				"content": buildDecisionInstruction(),
			},
			{
				"role":    "user",
				"content": buildDecisionQuery(req),
			},
		},
	}
	bodyBytes, err := json.Marshal(payload)
	if err != nil {
		return decisionResponse{}, err
	}
	var rawBody []byte
	maxAttempts := cfg.maxRetryAttempts
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		httpReq, err := http.NewRequestWithContext(
			ctx,
			http.MethodPost,
			buildChatCompletionsURL(cfg.baseURL),
			bytes.NewReader(bodyBytes),
		)
		if err != nil {
			return decisionResponse{}, err
		}
		httpReq.Header.Set("Authorization", "Bearer "+cfg.apiKey)
		httpReq.Header.Set("Content-Type", "application/json")
		httpResp, err := client.Do(httpReq)
		if err != nil {
			if attempt == maxAttempts {
				return decisionResponse{}, err
			}
			time.Sleep(retryBackoff(attempt, cfg))
			continue
		}
		rawBody, err = io.ReadAll(httpResp.Body)
		httpResp.Body.Close()
		if err != nil {
			return decisionResponse{}, err
		}
		if httpResp.StatusCode >= 200 && httpResp.StatusCode < 300 {
			break
		}
		if !isRetriableStatus(httpResp.StatusCode) || attempt == maxAttempts {
			return decisionResponse{}, fmt.Errorf("dashscope status=%d body=%s", httpResp.StatusCode, strings.TrimSpace(string(rawBody)))
		}
		time.Sleep(retryBackoff(attempt, cfg))
	}
	var completionResp struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Usage struct {
			PromptTokens        int `json:"prompt_tokens"`
			CompletionTokens    int `json:"completion_tokens"`
			TotalTokens         int `json:"total_tokens"`
			PromptTokensDetails struct {
				CachedTokens int `json:"cached_tokens"`
			} `json:"prompt_tokens_details"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(rawBody, &completionResp); err != nil {
		return decisionResponse{}, err
	}
	usageSummary.add(
		completionResp.Usage.PromptTokens,
		completionResp.Usage.CompletionTokens,
		completionResp.Usage.TotalTokens,
	)
	assistantText := ""
	if len(completionResp.Choices) > 0 {
		assistantText = strings.TrimSpace(completionResp.Choices[0].Message.Content)
	}
	if assistantText == "" {
		return decisionResponse{}, errors.New("empty assistant response")
	}
	parsed, err := parseDecisionText(assistantText)
	if err != nil {
		return decisionResponse{}, err
	}
	parsed.Source = "llm_http_direct"
	parsed.ModelCalls = usageSummary.modelCalls
	parsed.PromptTokens = usageSummary.promptTokens
	parsed.CachedTokens = completionResp.Usage.PromptTokensDetails.CachedTokens
	parsed.CompletionTokens = usageSummary.completionTokens
	parsed.TotalTokens = usageSummary.totalTokens
	return parsed, nil
}

func runDecisionServer(ctx context.Context, cfg llmRuntimeConfig) error {
	httpClient := &http.Client{Timeout: runtimeTimeout(cfg)}
	maxInflight := parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_MAX_INFLIGHT")), 4)
	if maxInflight < 1 {
		maxInflight = 1
	}
	inflight := make(chan struct{}, maxInflight)
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte("ok"))
	})
	mux.HandleFunc("/decide", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		defer r.Body.Close()
		var req decisionRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid json body", http.StatusBadRequest)
			return
		}
		select {
		case inflight <- struct{}{}:
			defer func() { <-inflight }()
		case <-r.Context().Done():
			http.Error(w, "request canceled", http.StatusGatewayTimeout)
			return
		}
		res, err := runDecision(r.Context(), httpClient, cfg, req)
		if err != nil {
			http.Error(w, fmt.Sprintf("decision failed: %v", err), http.StatusBadGateway)
			return
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		if err := json.NewEncoder(w).Encode(res); err != nil {
			http.Error(w, "encode error", http.StatusInternalServerError)
		}
	})
	addr := getEnvOrDefault("LLM_SERVER_ADDR", "127.0.0.1:18080")
	server := &http.Server{
		Addr:    addr,
		Handler: mux,
	}
	fmt.Printf("DecisionServer listening on http://%s\n", addr)
	fmt.Printf(
		"DecisionRuntime: timeout_seconds=%d enable_thinking=%t retry_attempts=%d max_inflight=%d mode=direct_http\n",
		cfg.requestTimeoutSec,
		cfg.enableThinking,
		cfg.maxRetryAttempts,
		maxInflight,
	)
	return server.ListenAndServe()
}

func main() {
	ctx := context.Background()
	if err := loadDotEnv("../.env"); err != nil {
		log.Fatalf("Failed to load .env: %v", err)
	}
	cfg := readRuntimeConfig()
	if cfg.apiKey == "" {
		log.Fatal("LLM_API_KEY is required")
	}
	if err := runDecisionServer(ctx, cfg); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("Decision server failed: %v", err)
	}
}
