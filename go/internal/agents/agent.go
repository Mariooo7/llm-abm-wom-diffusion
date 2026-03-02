package agents

import (
	"context"

	"github.com/cloudwego/eino/flow/agent/adk"
)

// AgentConfig 智能体配置
type AgentConfig struct {
	ID                 int     `json:"id"`
	Age                int     `json:"age"`
	Occupation         string  `json:"occupation"`
	IncomeLevel        string  `json:"income_level"`
	Openness           float64 `json:"openness"`            // 开放性 (1-10)
	Extraversion       float64 `json:"extraversion"`        // 外向性 (1-10)
	RiskTolerance      float64 `json:"risk_tolerance"`      // 风险偏好 (1-10)
	SharingTendency    float64 `json:"sharing_tendency"`    // 分享意愿 (1-10)
	ProductInterest    float64 `json:"product_interest"`    // 产品兴趣 (1-10)
	BrandLoyalty       float64 `json:"brand_loyalty"`       // 品牌忠诚度 (1-10)
}

// SimulationAgent 仿真智能体
type SimulationAgent struct {
	Config  AgentConfig
	Memory  *AgentMemory
	Runner  *adk.Runner
}

// AgentMemory 智能体记忆
type AgentMemory struct {
	HasAdopted      bool                `json:"has_adopted"`
	AdoptionTime    int                 `json:"adoption_time"`
	WOMReceived     []WOMMessage        `json:"wom_received"`
	WOMSources      map[int]bool        `json:"wom_sources"`
	CurrentEmotion  string              `json:"current_emotion"`
	EmotionIntensity float64            `json:"emotion_intensity"`
}

// WOMMessage 口碑消息
type WOMMessage struct {
	SourceID  int     `json:"source_id"`
	Content   string  `json:"content"`
	Valence   string  `json:"valence"` // positive/negative/neutral
	Intensity float64 `json:"intensity"`
	Time      int     `json:"time"`
}

// NewSimulationAgent 创建新的仿真智能体
func NewSimulationAgent(ctx context.Context, config AgentConfig, model interface{}) (*SimulationAgent, error) {
	agent := &SimulationAgent{
		Config: config,
		Memory: &AgentMemory{
			WOMSources: make(map[int]bool),
		},
	}

	// TODO: 初始化 LLM Runner
	// runner := adk.NewRunner(ctx, adk.RunnerConfig{...})
	// agent.Runner = runner

	return agent, nil
}

// ReceiveWOM 接收口碑消息
func (a *SimulationAgent) ReceiveWOM(sourceID int, content string, valence string, intensity float64, time int) {
	a.Memory.WOMReceived = append(a.Memory.WOMReceived, WOMMessage{
		SourceID:  sourceID,
		Content:   content,
		Valence:   valence,
		Intensity: intensity,
		Time:      time,
	})
	a.Memory.WOMSources[sourceID] = true
}

// Adopt 标记为已采纳
func (a *SimulationAgent) Adopt(time int) {
	a.Memory.HasAdopted = true
	a.Memory.AdoptionTime = time
}

// GetAdoptedNeighborRatio 计算已采纳邻居比例
func (a *SimulationAgent) GetAdoptedNeighborRatio(neighbors []int, modelState map[int]*SimulationAgent) float64 {
	if len(neighbors) == 0 {
		return 0.0
	}

	adoptedCount := 0
	for _, neighborID := range neighbors {
		if neighbor, exists := modelState[neighborID]; exists && neighbor.Memory.HasAdopted {
			adoptedCount++
		}
	}

	return float64(adoptedCount) / float64(len(neighbors))
}
