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
	"net"
	"net/http"
	"os"
	"os/signal"
	"regexp"
	"strconv"
	"strings"
	"syscall"
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

// decisionRequest 是 Python 侧每次决策调用的输入快照。
// 该结构的字段名直接用于 JSON 编解码，属于接口契约：改名会导致上游请求字段“静默丢失”。
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

// decisionResponse 是网关对 Python 的返回结构。
// adopt/probability/reasoning 是研究语义字段；其余是工程统计字段，用于估算开销与排查异常。
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

// loadDotEnv 只做最朴素的 KEY=VALUE 读取：不支持 export、引号嵌套、变量展开等扩展语法。
// 目的很简单：让一键脚本跑起来时，用户只需要准备 .env，不必依赖额外工具链。
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
	retryAttempts = max(1, retryAttempts)
	retryBaseMs := parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_RETRY_BASE_MS")), 200)
	retryBaseMs = max(50, retryBaseMs)
	retryJitterMs := parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_RETRY_JITTER_MS")), 120)
	retryJitterMs = max(0, retryJitterMs)
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

// buildDecisionInstruction 返回系统提示词。
//
// 这段字符串是“研究语义”的一部分：它定义了角色边界、输入字段的解释方式以及输出格式。
// 任何微小改动都可能改变行为分布，因此把它集中在一个函数里，便于审计与记录。
func buildDecisionInstruction() string {
	researchProtocol := strings.Join([]string{
		"【角色设定】",
		"你是一名真实的、具备“有限理性”的普通消费者，面临是否采纳一款“新产品”的决策。",
		"你遵循人类的创新抗拒逻辑：默认维持现状，仅在内驱力或外部环境刺激足够大时，才会打破惯性做出改变。",
		"",
		"【决策参数字典与内心推演机制】",
		"每次决策，你将收到一个包含当前状态的 JSON。请严格依据以下字段的现实意义进行第一人称推演：",
		"1. 你的内在特质 (agent_profile)：",
		"- openness (0.0~1.0): 开放性。0代表极度保守，1代表极度拥抱新事物。",
		"- risk_tolerance (0.0~1.0): 风险承受度。值越低，你越害怕试错成本，越需要外部的强烈证实才敢购买。",
		"2. 你的本能基线 (bass_params)：",
		"- innovation_coef: 创新基线概率。这代表即使没有任何人推荐，你自发产生购买冲动的绝对基准概率。",
		"- imitation_coef: 模仿敏感度。这代表你本身有多容易“随大流”。",
		"3. 你面临的外部刺激 (social_context & wom_messages_recent)：",
		"- adopted_ratio (0.0~1.0): 朋友圈中已购买该产品的人数比例。0.1代表刚起步，0.5代表已经普及。结合你的 imitation_coef，比例越高你的同侪压力越大。",
		"- wom_messages_recent: 朋友发给你的真实评价原文。",
		"- emotion_arousal (0.0~1.0): 朋友在推荐时的情绪唤醒度。0代表冷淡客观，1代表极其狂热。高唤醒度能瞬间提升你的购买冲动，但若你的 risk_tolerance 极低，你依然会保持警惕。",
		"",
		"【强制输出规范】",
		"严禁输出任何Markdown标记（如```json）或多余解释。",
		"请严格按以下顺序生成合法JSON对象：",
		"{",
		`  "reasoning": "结合上述字典中具体参数的数值大小，用一两句第一人称内心独白描述你的权衡过程（必须体现你看到了哪些具体数值及其影响）。",`,
		`  "probability": 0.0,`,
		`  "adopt": false`,
		"}",
		"当 probability 大于等于0.5时 adopt 必须为 true，否则必须为 false。",
		"probability 必须是 0.0 到 1.0 的浮点数。",
		"只输出 JSON 对象本体，不要输出任何额外文本。",
	}, "\n")
	return strings.Join([]string{
		researchProtocol,
	}, "\n")
}

// clampProbability 兜底概率边界，避免上游把非法值写入结果文件。
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

// parseDecisionText 的目标不是“严格解析”，而是从可能脏的模型输出里尽量捞出可用字段：
// - 优先尝试完整 JSON 解析；
// - 失败后使用正则兜底提取 adopt/probability/reasoning；
// - 最终对 probability 做 clamp，并按阈值规则修正 adopt。
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
	step := min(attempt-1, 5)
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
	var httpReq *http.Request
	var httpResp *http.Response
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		httpReq, err = http.NewRequestWithContext(
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
		httpResp, err = client.Do(httpReq)
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
	if unmarshalErr := json.Unmarshal(rawBody, &completionResp); unmarshalErr != nil {
		return decisionResponse{}, unmarshalErr
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
	_ = ctx
	httpClient := &http.Client{Timeout: runtimeTimeout(cfg)}
	maxInflight := parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_MAX_INFLIGHT")), 4)
	maxInflight = max(1, maxInflight)
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
		BaseContext: func(_ net.Listener) context.Context {
			return ctx
		},
	}
	fmt.Printf("DecisionServer listening on http://%s\n", addr)
	fmt.Printf(
		"DecisionRuntime: timeout_seconds=%d enable_thinking=%t retry_attempts=%d max_inflight=%d mode=direct_http\n",
		cfg.requestTimeoutSec,
		cfg.enableThinking,
		cfg.maxRetryAttempts,
		maxInflight,
	)
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx)
	}()
	return server.ListenAndServe()
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
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
