package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"thesis-diffusion-simulation/internal/tools"

	"github.com/cloudwego/eino-ext/components/model/openai"
	aclopenai "github.com/cloudwego/eino-ext/libs/acl/openai"
	"github.com/cloudwego/eino/adk"
	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/compose"
	"github.com/cloudwego/eino/schema"
)

type llmRuntimeConfig struct {
	provider          string
	modelName         string
	apiKey            string
	baseURL           string
	temperature       float32
	maxTokens         int
	seed              int
	requestTimeoutSec int
	maxIterations     int
	enablePrefixCache bool
}

type promptCache struct {
	data map[string]map[string]any
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
	CompletionTokens int     `json:"completion_tokens"`
	TotalTokens      int     `json:"total_tokens"`
}

func newPromptCache() *promptCache {
	return &promptCache{
		data: map[string]map[string]any{},
	}
}

func (s *tokenUsageSummary) add(usage *schema.TokenUsage) {
	if usage == nil {
		return
	}
	s.modelCalls++
	s.promptTokens += usage.PromptTokens
	s.completionTokens += usage.CompletionTokens
	s.totalTokens += usage.TotalTokens
}

func (c *promptCache) getOrBuild(contextKey string) map[string]any {
	if values, ok := c.data[contextKey]; ok {
		return values
	}
	values := map[string]any{
		"ResearchGoal":       "在仿真背景下解释扩散机制，不输出营销文案",
		"DesignBoundary":     "遵循2x2实验设定，不擅自改动变量定义",
		"DecisionConstraint": "当信息不足时明确说明不确定性，不臆造数据",
		"OutputFormat":       "先给结论，再给机制解释，最后列出可验证指标",
		"WritingStyle":       "简洁、可复核、符合学术表达",
	}
	c.data[contextKey] = values
	return values
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
	enablePrefixCache := parseBoolOrDefault(
		strings.TrimSpace(os.Getenv("LLM_PREFIX_CACHE_ENABLED")),
		true,
	)
	if !strings.Contains(strings.ToLower(baseURL), "dashscope") {
		enablePrefixCache = false
	}
	return llmRuntimeConfig{
		provider:          getEnvOrDefault("LLM_PROVIDER", "aliyun_bailian"),
		modelName:         getEnvOrDefault("LLM_MODEL", "qwen3.5-flash"),
		apiKey:            strings.TrimSpace(os.Getenv("LLM_API_KEY")),
		baseURL:           baseURL,
		temperature:       parseFloat32OrDefault(strings.TrimSpace(os.Getenv("LLM_TEMPERATURE")), 0.2),
		maxTokens:         parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_MAX_TOKENS")), 700),
		seed:              parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_SEED")), 42),
		requestTimeoutSec: parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_REQUEST_TIMEOUT_SECONDS")), 120),
		maxIterations:     parseIntOrDefault(strings.TrimSpace(os.Getenv("LLM_DECISION_MAX_ITERATIONS")), 1),
		enablePrefixCache: enablePrefixCache,
	}
}

func runtimeTimeout(cfg llmRuntimeConfig) time.Duration {
	timeoutSec := cfg.requestTimeoutSec
	if timeoutSec <= 0 {
		timeoutSec = 120
	}
	return time.Duration(timeoutSec) * time.Second
}

func runtimeMaxIterations(cfg llmRuntimeConfig) int {
	if cfg.maxIterations <= 0 {
		return 1
	}
	return cfg.maxIterations
}

func buildInstruction() string {
	return strings.Join([]string{
		"你是扩散仿真结果分析器，不是消费者，不参与采纳决策。",
		"研究目标：{ResearchGoal}。",
		"实验边界：{DesignBoundary}。",
		"决策约束：{DecisionConstraint}。",
		"输出格式：{OutputFormat}。",
		"写作风格：{WritingStyle}。",
		"优先调用工具进行可解释推断；若工具输出不足，再补充简短推理。",
		"禁止编造实验结果与统计显著性。",
	}, "\n")
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
		"15) 该前缀用于稳定实验语义边界，并作为可缓存公共前缀。",
	}, "\n")
	return strings.Join([]string{
		researchProtocol,
		"你正在模拟一名普通消费者在当前时间步是否采纳新产品。",
		"你会收到一个JSON对象，包含个体特质、社会影响和口碑信息。",
		"请仅输出JSON对象，字段必须是 adopt(boolean), probability(number), reasoning(string)。",
		"不要输出任何额外文本。",
	}, "\n")
}

func withDashScopePrefixCacheOption() model.Option {
	return aclopenai.WithRequestPayloadModifier(
		func(_ context.Context, _ []*schema.Message, rawBody []byte) ([]byte, error) {
			var payload map[string]any
			if err := json.Unmarshal(rawBody, &payload); err != nil {
				return nil, err
			}
			messageList, ok := payload["messages"].([]any)
			if !ok || len(messageList) == 0 {
				return rawBody, nil
			}
			for i, msgRaw := range messageList {
				msg, ok := msgRaw.(map[string]any)
				if !ok {
					continue
				}
				role, _ := msg["role"].(string)
				if role != "system" {
					continue
				}
				switch content := msg["content"].(type) {
				case string:
					text := strings.TrimSpace(content)
					if text == "" {
						continue
					}
					msg["content"] = []map[string]any{
						{
							"type":          "text",
							"text":          text,
							"cache_control": map[string]any{"type": "ephemeral"},
						},
					}
				case []any:
					if len(content) == 0 {
						continue
					}
					lastIdx := len(content) - 1
					lastPart, ok := content[lastIdx].(map[string]any)
					if !ok {
						continue
					}
					if _, exists := lastPart["cache_control"]; !exists {
						lastPart["cache_control"] = map[string]any{"type": "ephemeral"}
						content[lastIdx] = lastPart
					}
					msg["content"] = content
				default:
					continue
				}
				messageList[i] = msg
				break
			}
			payload["messages"] = messageList
			updatedBody, err := json.Marshal(payload)
			if err != nil {
				return nil, err
			}
			return updatedBody, nil
		},
	)
}

func buildModelOptions(cfg llmRuntimeConfig) []model.Option {
	options := []model.Option{
		model.WithTemperature(cfg.temperature),
		model.WithMaxTokens(cfg.maxTokens),
	}
	if cfg.enablePrefixCache {
		options = append(options, withDashScopePrefixCacheOption())
	}
	return options
}

func collectTokenUsage(event *adk.AgentEvent, summary *tokenUsageSummary) {
	if event == nil || event.Output == nil || event.Output.MessageOutput == nil {
		return
	}
	msg, err := event.Output.MessageOutput.GetMessage()
	if err != nil || msg == nil || msg.ResponseMeta == nil {
		return
	}
	summary.add(msg.ResponseMeta.Usage)
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
		return decisionResponse{}, err
	}
	res := decisionResponse{
		Adopt:       payload.Adopt,
		Probability: clampProbability(payload.Probability),
		Reasoning:   strings.TrimSpace(payload.Reasoning),
		Source:      "llm_eino",
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

func buildDecisionRunner(ctx context.Context, cfg llmRuntimeConfig) (*adk.Runner, error) {
	chatModel, err := openai.NewChatModel(ctx, &openai.ChatModelConfig{
		Model:       cfg.modelName,
		APIKey:      cfg.apiKey,
		BaseURL:     cfg.baseURL,
		Temperature: &cfg.temperature,
		Seed:        &cfg.seed,
		Timeout:     runtimeTimeout(cfg),
	})
	if err != nil {
		return nil, err
	}
	agent, err := adk.NewChatModelAgent(ctx, &adk.ChatModelAgentConfig{
		Name:          "consumer_decision_agent",
		Description:   "消费者采纳决策Agent",
		Instruction:   buildDecisionInstruction(),
		Model:         chatModel,
		OutputKey:     "Decision",
		MaxIterations: runtimeMaxIterations(cfg),
	})
	if err != nil {
		return nil, err
	}
	runner := adk.NewRunner(ctx, adk.RunnerConfig{
		Agent: agent,
	})
	return runner, nil
}

func runDecision(ctx context.Context, runner *adk.Runner, cache *promptCache, cfg llmRuntimeConfig, req decisionRequest) (decisionResponse, error) {
	contextKey := strings.TrimSpace(req.ContextKey)
	if contextKey == "" {
		contextKey = "default_context"
	}
	usageSummary := &tokenUsageSummary{}
	opts := []adk.AgentRunOption{
		adk.WithSessionValues(cache.getOrBuild(contextKey)),
		adk.WithChatModelOptions(buildModelOptions(cfg)),
	}
	iter := runner.Query(ctx, buildDecisionQuery(req), opts...)
	assistantText := ""
	var runErr error
	for {
		event, ok := iter.Next()
		if !ok {
			break
		}
		collectTokenUsage(event, usageSummary)
		if event.Err != nil {
			runErr = event.Err
			continue
		}
		if event.Output == nil || event.Output.MessageOutput == nil {
			continue
		}
		msg, err := event.Output.MessageOutput.GetMessage()
		if err != nil || msg == nil {
			continue
		}
		if msg.Role == schema.Assistant {
			text := strings.TrimSpace(msg.Content)
			if text != "" {
				assistantText = text
			}
		}
	}
	if runErr != nil {
		return decisionResponse{}, runErr
	}
	if assistantText == "" {
		return decisionResponse{}, errors.New("empty assistant response")
	}
	parsed, err := parseDecisionText(assistantText)
	if err != nil {
		return decisionResponse{}, err
	}
	parsed.ModelCalls = usageSummary.modelCalls
	parsed.PromptTokens = usageSummary.promptTokens
	parsed.CompletionTokens = usageSummary.completionTokens
	parsed.TotalTokens = usageSummary.totalTokens
	return parsed, nil
}

func runDecisionServer(ctx context.Context, cfg llmRuntimeConfig) error {
	runner, err := buildDecisionRunner(ctx, cfg)
	if err != nil {
		return err
	}
	cache := newPromptCache()
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
		res, err := runDecision(r.Context(), runner, cache, cfg, req)
		if err != nil {
			http.Error(w, fmt.Sprintf("decision failed: %v", err), http.StatusBadGateway)
			return
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		if err := json.NewEncoder(w).Encode(res); err != nil {
			http.Error(w, "encode error", http.StatusInternalServerError)
		}
	})
	addr := getEnvOrDefault("EINO_SERVER_ADDR", "127.0.0.1:18080")
	server := &http.Server{
		Addr:    addr,
		Handler: mux,
	}
	fmt.Printf("EinoDecisionServer listening on http://%s\n", addr)
	fmt.Printf("DashScopePrefixCacheEnabled: %t\n", cfg.enablePrefixCache)
	fmt.Printf("DecisionRuntime: timeout_seconds=%d max_iterations=%d max_tokens=%d\n", cfg.requestTimeoutSec, runtimeMaxIterations(cfg), cfg.maxTokens)
	return server.ListenAndServe()
}

func runAnalysisDemo(ctx context.Context, cfg llmRuntimeConfig) {
	chatModel, err := openai.NewChatModel(ctx, &openai.ChatModelConfig{
		Model:       cfg.modelName,
		APIKey:      cfg.apiKey,
		BaseURL:     cfg.baseURL,
		Temperature: &cfg.temperature,
		Seed:        &cfg.seed,
		Timeout:     runtimeTimeout(cfg),
	})
	if err != nil {
		log.Fatalf("Failed to create chat model: %v", err)
	}

	diffusionTool := tools.NewDiffusionTool()
	sentimentTool := tools.NewSentimentTool()
	diffusionBaseTool, err := diffusionTool.ToTool()
	if err != nil {
		log.Fatalf("Failed to create diffusion tool: %v", err)
	}
	sentimentBaseTool, err := sentimentTool.ToTool()
	if err != nil {
		log.Fatalf("Failed to create sentiment tool: %v", err)
	}

	agent, err := adk.NewChatModelAgent(ctx, &adk.ChatModelAgentConfig{
		Name:          "diffusion_research_agent",
		Description:   "面向扩散仿真实验的可解释决策分析Agent",
		Instruction:   buildInstruction(),
		Model:         chatModel,
		OutputKey:     "LastAnswer",
		MaxIterations: 8,
		ToolsConfig: adk.ToolsConfig{
			ToolsNodeConfig: compose.ToolsNodeConfig{
				Tools: []tool.BaseTool{
					diffusionBaseTool,
					sentimentBaseTool,
				},
			},
		},
	})
	if err != nil {
		log.Fatalf("Failed to create agent: %v", err)
	}

	runner := adk.NewRunner(ctx, adk.RunnerConfig{
		Agent: agent,
	})

	cache := newPromptCache()
	sessionValues := cache.getOrBuild("pilot_a_context")
	opts := []adk.AgentRunOption{
		adk.WithSessionValues(sessionValues),
		adk.WithChatModelOptions(buildModelOptions(cfg)),
	}

	fmt.Printf("Provider: %s\n", cfg.provider)
	fmt.Printf("Model: %s\n", cfg.modelName)
	fmt.Printf("Temperature: %.2f\n", cfg.temperature)
	fmt.Printf("MaxTokens: %d\n", cfg.maxTokens)
	fmt.Printf("DashScopePrefixCacheEnabled: %t\n", cfg.enablePrefixCache)
	iter := runner.Query(ctx, "请基于组A场景给出扩散风险与建议观测指标。", opts...)
	usageSummary := &tokenUsageSummary{}
	for {
		event, ok := iter.Next()
		if !ok {
			break
		}
		collectTokenUsage(event, usageSummary)
		if event.Err != nil {
			fmt.Printf("AgentError: %v\n", event.Err)
			continue
		}
		if event.Output == nil || event.Output.MessageOutput == nil {
			continue
		}
		msg, err := event.Output.MessageOutput.GetMessage()
		if err != nil || msg == nil {
			continue
		}
		text := strings.TrimSpace(msg.Content)
		if text != "" {
			switch msg.Role {
			case schema.Assistant:
				fmt.Printf("Assistant: %s\n", text)
			case schema.Tool:
				fmt.Printf("Tool[%s]: %s\n", msg.ToolName, text)
			default:
				fmt.Printf("Message[%s]: %s\n", msg.Role, text)
			}
		}
		if len(msg.ToolCalls) > 0 {
			fmt.Printf("AssistantToolCalls: %d\n", len(msg.ToolCalls))
		}
	}
	fmt.Printf(
		"TokenUsage => model_calls=%d input_tokens=%d output_tokens=%d total_tokens=%d\n",
		usageSummary.modelCalls,
		usageSummary.promptTokens,
		usageSummary.completionTokens,
		usageSummary.totalTokens,
	)
	if usageSummary.modelCalls > 0 {
		fmt.Printf(
			"TokenUsageAvgPerCall => input=%.2f output=%.2f total=%.2f\n",
			float64(usageSummary.promptTokens)/float64(usageSummary.modelCalls),
			float64(usageSummary.completionTokens)/float64(usageSummary.modelCalls),
			float64(usageSummary.totalTokens)/float64(usageSummary.modelCalls),
		)
	}
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
	mode := getEnvOrDefault("EINO_MODE", "analysis_demo")
	if mode == "decision_server" {
		if err := runDecisionServer(ctx, cfg); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("Decision server failed: %v", err)
		}
		return
	}
	runAnalysisDemo(ctx, cfg)
}
