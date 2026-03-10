package tools

import (
	"context"

	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/components/tool/utils"
)

// DiffusionTool 扩散分析工具
type DiffusionTool struct{}

// DiffusionInput 输入参数
type DiffusionInput struct {
	ProductInfo      string  `json:"product_info" jsonschema:"产品信息"`
	WOMContent       string  `json:"wom_content" jsonschema:"口碑内容"`
	EmotionIntensity float64 `json:"emotion_intensity" jsonschema:"情感强度 (0-1)"`
	AdoptedRatio     float64 `json:"adopted_ratio" jsonschema:"已采纳朋友比例 (0-1)"`
	RiskTolerance    float64 `json:"risk_tolerance" jsonschema:"风险偏好 (0-10)"`
	Openness         float64 `json:"openness" jsonschema:"开放性 (0-10)"`
}

// DiffusionOutput 输出结果
type DiffusionOutput struct {
	Adopt       bool     `json:"adopt"`
	Probability float64  `json:"probability"`
	Reasons     []string `json:"reasons"`
}

// NewDiffusionTool 创建扩散分析工具
func NewDiffusionTool() *DiffusionTool {
	return &DiffusionTool{}
}

// ToTool 转换为 eino Tool
func (t *DiffusionTool) ToTool() (tool.BaseTool, error) {
	return utils.InferTool("analyze_diffusion", "分析产品扩散决策，返回采纳概率和原因", t.Analyze)
}

// Analyze 分析扩散决策
func (t *DiffusionTool) Analyze(ctx context.Context, input DiffusionInput) (*DiffusionOutput, error) {
	// TODO: 实现基于 Bass 模型和社交影响的决策逻辑
	// 目前使用简化的启发式规则

	probability := 0.0

	// 创新系数 (个人特质)
	innovationEffect := input.Openness * 0.05

	// 模仿系数 (社交影响)
	imitationEffect := input.AdoptedRatio * 0.3

	// 情感效应
	emotionEffect := input.EmotionIntensity * 0.2

	probability = innovationEffect + imitationEffect + emotionEffect

	// 风险偏好调节
	if input.RiskTolerance > 7 {
		probability *= 1.2
	} else if input.RiskTolerance < 4 {
		probability *= 0.8
	}

	// 限制在 0-1 范围
	if probability > 1.0 {
		probability = 1.0
	}

	adopt := probability > 0.5

	reasons := []string{}
	if input.AdoptedRatio > 0.5 {
		reasons = append(reasons, "超过一半的朋友已采纳")
	}
	if input.EmotionIntensity > 0.7 {
		reasons = append(reasons, "口碑情感强度很高")
	}
	if input.Openness > 7 {
		reasons = append(reasons, "对新事物接受度高")
	}

	return &DiffusionOutput{
		Adopt:       adopt,
		Probability: probability,
		Reasons:     reasons,
	}, nil
}

// SentimentTool 情感分析工具
type SentimentTool struct{}

// SentimentInput 输入参数
type SentimentInput struct {
	Text string `json:"text" jsonschema:"待分析的文本内容"`
}

// SentimentOutput 输出结果
type SentimentOutput struct {
	Valence   string  `json:"valence"`   // positive/negative/neutral
	Intensity float64 `json:"intensity"` // 0-1
	Emotion   string  `json:"emotion"`   // joy/anger/fear/sadness/surprise
}

// NewSentimentTool 创建情感分析工具
func NewSentimentTool() *SentimentTool {
	return &SentimentTool{}
}

// ToTool 转换为 eino Tool
func (t *SentimentTool) ToTool() (tool.BaseTool, error) {
	return utils.InferTool("analyze_sentiment", "分析文本的情感倾向和强度", t.Analyze)
}

// Analyze 分析情感
func (t *SentimentTool) Analyze(ctx context.Context, input SentimentInput) (*SentimentOutput, error) {
	// TODO: 实现真实的情感分析 (可调用 LLM 或规则)
	// 目前使用简化的关键词匹配

	text := input.Text

	// 简单关键词匹配
	positiveWords := []string{"推荐", "棒", "好", "惊喜", "满意", "喜欢", "爱"}
	negativeWords := []string{"差", "失望", "不好", "糟糕", "讨厌", "恨"}

	positiveCount := 0
	negativeCount := 0

	for _, word := range positiveWords {
		if contains(text, word) {
			positiveCount++
		}
	}

	for _, word := range negativeWords {
		if contains(text, word) {
			negativeCount++
		}
	}

	valence := "neutral"
	intensity := 0.5
	emotion := "neutral"

	if positiveCount > negativeCount {
		valence = "positive"
		intensity = float64(positiveCount) / 10.0
		if intensity > 1.0 {
			intensity = 1.0
		}
		emotion = "joy"
	} else if negativeCount > positiveCount {
		valence = "negative"
		intensity = float64(negativeCount) / 10.0
		if intensity > 1.0 {
			intensity = 1.0
		}
		emotion = "anger"
	}

	return &SentimentOutput{
		Valence:   valence,
		Intensity: intensity,
		Emotion:   emotion,
	}, nil
}

func contains(s string, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && findSubstring(s, substr))
}

func findSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
