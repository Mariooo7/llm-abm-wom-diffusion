"""
扩散仿真核心模型（Mesa ABM）。

这套模型的职责很窄：按配置生成网络与个体，按时间步推进，并把每步的采纳状态与汇总指标落盘。
LLM 只负责“当前时间步是否产生采纳冲动”的一次性判断，不参与跨期规划；工程侧允许并行多个 repetition，
但单次 run 内仍按随机异步顺序逐个 agent 更新，避免把并发引入到行为语义里。
"""

from typing import Any

import numpy as np
from agents.agent import Agent, AgentProfile
from config.settings import SimulationConfig
from llm import DecisionClient
from mesa import Model
from mesa.datacollection import DataCollector
from networks.generator import compute_network_metrics, generate_network


class DiffusionModel(Model):
    """
    新产品扩散的 ABM（Agent-Based Model）。

    语义边界：
    - 一个时间步内：随机打乱 agent 更新顺序，逐个更新（异步）。
    - 跨时间步：只累计状态，不做回溯。
    - 决策入口：统一走 DecisionClient，保证输入字段与实验提示词对齐。
    """

    def __init__(self, config: SimulationConfig):
        """
        初始化模型：网络 -> 个体 -> 决策服务 -> 数据采集器。

        config 来自 experiments/configs/group_*.yaml，属于“研究参数”的单一事实来源。
        """
        super().__init__()

        self.config = config
        self.current_step = 0
        self.running = True

        self.network = generate_network(
            network_type=config.network_type,
            n_nodes=config.n_agents,
            avg_degree=config.avg_degree,
            rewiring_prob=config.rewiring_prob,
            seed=config.seed,
        )

        self.network_metrics = compute_network_metrics(self.network)
        self.context_key = (
            f"{config.group}_{config.network_type}_{config.wom_strength}_{config.n_agents}"
        )
        if not config.use_llm:
            raise ValueError("研究模式要求 use_llm 必须为 true")
        if config.llm_sampling_ratio != 1.0:
            raise ValueError("研究模式要求 llm_sampling_ratio 必须为 1.0")
        self.decision_client = DecisionClient(
            model=config.llm_model,
            base_url=config.llm_base_url,
            api_key_env=config.llm_api_key_env,
            temperature=config.llm_temperature,
            timeout_seconds=config.llm_timeout_seconds,
            gateway_url=config.llm_gateway_url,
            gateway_autostart=config.llm_gateway_autostart,
        )
        self.population: dict[int, Agent] = {}
        self._initialize_agents()

        self.datacollector = DataCollector(
            model_reporters={
                "total_adopters": lambda m: sum(
                    1 for a in m.population.values() if a.memory.has_adopted
                ),
                "adoption_rate": lambda m: (
                    sum(1 for a in m.population.values() if a.memory.has_adopted)
                    / m.config.n_agents
                ),
                "cumulative_adoption": lambda m: self._compute_cumulative_adoption(),
            },
            agent_reporters={
                "has_adopted": lambda a: a.memory.has_adopted,
                "adoption_time": lambda a: a.memory.adoption_time,
                "wom_count": lambda a: len(a.memory.wom_received),
            },
        )

    def _initialize_agents(self) -> None:
        """
        逐个节点创建 Agent。

        这里把网络节点 ID 作为 agent_id，确保邻接关系与个体索引一一对应，便于复现与排查。
        """
        for node_id in self.network.nodes():
            profile = AgentProfile(agent_id=node_id)
            agent = Agent(agent_id=node_id, profile=profile, model=self)
            self.population[node_id] = agent

    def _compute_cumulative_adoption(self) -> list[int]:
        """
        计算“累计采纳曲线”。

        返回长度为 current_step+1 的列表，第 t 项表示在 t 步及之前完成采纳的人数。
        """
        adoption_times = [
            a.memory.adoption_time
            for a in self.population.values()
            if a.memory.adoption_time is not None
        ]
        cumulative = []
        for t in range(self.current_step + 1):
            count = sum(1 for time in adoption_times if time <= t)
            cumulative.append(count)
        return cumulative

    def get_neighbors(self, agent_id: int) -> list[int]:
        """返回 agent 的邻居列表（网络结构决定可见同伴集合）。"""
        return list(self.network.neighbors(agent_id))

    def get_adopted_neighbors(self, agent_id: int) -> list[int]:
        """返回已采纳邻居列表，用于计算 adopted_ratio。"""
        neighbors = self.get_neighbors(agent_id)
        return [nid for nid in neighbors if self.population[nid].memory.has_adopted]

    def step(self) -> None:
        """
        推进一个时间步。

        Mesa 的 scheduler 并未使用；这里直接在 model 内部做随机异步更新，
        目的是让“并发”只发生在 repetition 之间，不进入单次 run 的行为语义。
        """
        agent_ids = list(self.population.keys())
        self.random.shuffle(agent_ids)
        for agent_id in agent_ids:
            self.population[agent_id].step()
        self.datacollector.collect(self)
        self.current_step += 1

        total_adopters = sum(1 for a in self.population.values() if a.memory.has_adopted)
        if total_adopters >= self.config.n_agents or self.current_step >= self.config.n_steps:
            self.running = False

    def get_metrics(self) -> dict[str, Any]:
        """
        汇总一次 run 的最终指标。

        该结构会被写入结果文件，用于：
        - 复现实验：记录关键配置快照与网络结构指标；
        - 诊断开销：记录 LLM 调用次数与 token 统计。
        """
        adopters = [a for a in self.population.values() if a.memory.has_adopted]
        adoption_times = [
            a.memory.adoption_time for a in adopters if a.memory.adoption_time is not None
        ]
        metrics = {
            "total_adopters": len(adopters),
            "final_adoption_rate": len(adopters) / self.config.n_agents,
            "avg_adoption_time": np.mean(adoption_times) if adoption_times else None,
            "median_adoption_time": np.median(adoption_times) if adoption_times else None,
            "network_metrics": self.network_metrics,
            "config": {
                "network_type": self.config.network_type,
                "wom_strength": self.config.wom_strength,
                "n_agents": self.config.n_agents,
                "n_steps": self.config.n_steps,
            },
            "llm_usage": {
                "enabled": bool(self.config.use_llm),
                "available": self.decision_client is not None,
                "model": self.config.llm_model,
                "model_calls": (
                    self.decision_client.model_calls if self.decision_client is not None else 0
                ),
                "prompt_tokens": (
                    self.decision_client.prompt_tokens if self.decision_client is not None else 0
                ),
                "completion_tokens": (
                    self.decision_client.completion_tokens
                    if self.decision_client is not None
                    else 0
                ),
                "total_tokens": (
                    self.decision_client.total_tokens if self.decision_client is not None else 0
                ),
            },
        }
        return metrics


__all__ = ["DiffusionModel"]
