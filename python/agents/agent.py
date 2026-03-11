"""
个体（消费者）代理。

每个 agent 持有两类状态：
- profile：相对稳定的个体特质（开放性、风险承受、分享倾向）。
- memory：随时间步变化的记忆与采纳状态（是否采纳、何时采纳、收到的口碑片段）。
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from llm import DecisionRequest

if TYPE_CHECKING:
    from models.model import DiffusionModel


@dataclass
class AgentProfile:
    """
    个体特质。

    这里内部采样使用 [2, 9] 的连续分数，便于与问卷式量表直觉对齐。
    进入 LLM 前会做一次归一化映射到 [0, 1]，保证与提示词中的取值范围一致。
    """
    agent_id: int
    openness: float = field(default_factory=lambda: float(np.random.uniform(2.0, 9.0)))
    risk_tolerance: float = field(default_factory=lambda: float(np.random.uniform(2.0, 9.0)))
    sharing_tendency: float = field(default_factory=lambda: float(np.random.uniform(2.0, 9.0)))


@dataclass
class AgentMemory:
    """与扩散过程相关的可变状态与短期记忆。"""
    has_adopted: bool = False
    adoption_time: int | None = None
    wom_received: list[str] = field(default_factory=list)


class Agent:
    def __init__(self, agent_id: int, profile: AgentProfile, model: "DiffusionModel") -> None:
        self.unique_id = agent_id
        self.profile = profile
        self.memory = AgentMemory()
        self.model = model

    @staticmethod
    def _normalize_trait(raw: float) -> float:
        """
        把 [2, 9] 的量表分数线性映射到 [0, 1]。

        LLM 提示词明确按 0~1 解释 openness/risk_tolerance，输入侧必须对齐，否则模型会把量纲误读。
        """
        return float(np.clip((raw - 2.0) / 7.0, 0.0, 1.0))

    def step(self) -> None:
        if self.memory.has_adopted:
            return
        adopted_neighbors = self.model.get_adopted_neighbors(self.unique_id)
        total_neighbors = self.model.get_neighbors(self.unique_id)
        adopted_ratio = len(adopted_neighbors) / len(total_neighbors) if total_neighbors else 0.0
        openness = self._normalize_trait(self.profile.openness)
        risk_tolerance = self._normalize_trait(self.profile.risk_tolerance)
        req = DecisionRequest(
            agent_id=self.unique_id,
            openness=openness,
            risk_tolerance=risk_tolerance,
            adopted_ratio=adopted_ratio,
            emotion_arousal=self.model.config.emotion_arousal,
            wom_strength=self.model.config.wom_strength,
            wom_messages=self.memory.wom_received,
            innovation_coef=self.model.config.innovation_coef,
            imitation_coef=self.model.config.imitation_coef,
        )
        decision = self.model.decision_client.decide(req, self.model.context_key)
        prob = decision.probability
        if self.model.random.random() < prob:
            self.memory.has_adopted = True
            self.memory.adoption_time = self.model.current_step
