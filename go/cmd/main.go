package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"thesis-diffusion-simulation/internal/agents"
	"thesis-diffusion-simulation/internal/tools"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino-ext/components/model/openai"
	"github.com/cloudwego/eino/flow/agent/adk"
)

func main() {
	ctx := context.Background()

	// 初始化 LLM (使用 Dashscope/通义千问)
	chatModel, err := openai.NewChatModel(ctx, &openai.ChatModelConfig{
		Model:  os.Getenv("LLM_MODEL"),
		APIKey: os.Getenv("LLM_API_KEY"),
		BaseURL: os.Getenv("LLM_BASE_URL"),
	})
	if err != nil {
		log.Fatalf("Failed to create chat model: %v", err)
	}

	// 注册工具
	diffusionTool := tools.NewDiffusionTool()
	sentimentTool := tools.NewSentimentTool()

	// 创建智能体
	agent, err := adk.NewChatModelAgent(ctx, &adk.ChatModelAgentConfig{
		Model: chatModel,
		ToolsConfig: adk.ToolsConfig{
			Tools: []model.Tool{
				diffusionTool.ToTool(),
				sentimentTool.ToTool(),
			},
		},
	})
	if err != nil {
		log.Fatalf("Failed to create agent: %v", err)
	}

	// 创建 Runner
	runner := adk.NewRunner(ctx, adk.RunnerConfig{
		Agent: agent,
	})

	// 测试查询
	iter := runner.Query(ctx, "分析这个产品的口碑传播效果")
	defer iter.Close()

	for {
		event, err := iter.Recv()
		if err != nil {
			break
		}
		fmt.Printf("Agent: %s\n", event.String())
	}
}
