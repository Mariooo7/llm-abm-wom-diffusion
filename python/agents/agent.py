from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from llm import DecisionRequest

if TYPE_CHECKING:
    from models.model import DiffusionModel


@dataclass
class AgentProfile:
    agent_id: int
    openness: float = field(default_factory=lambda: float(np.random.uniform(2.0, 9.0)))
    risk_tolerance: float = field(default_factory=lambda: float(np.random.uniform(2.0, 9.0)))
    sharing_tendency: float = field(default_factory=lambda: float(np.random.uniform(2.0, 9.0)))


@dataclass
class AgentMemory:
    has_adopted: bool = False
    adoption_time: int | None = None
    wom_received: list[str] = field(default_factory=list)


class Agent:
    def __init__(self, agent_id: int, profile: AgentProfile, model: "DiffusionModel") -> None:
        self.unique_id = agent_id
        self.profile = profile
        self.memory = AgentMemory()
        self.model = model

    def step(self) -> None:
        if self.memory.has_adopted:
            return
        adopted_neighbors = self.model.get_adopted_neighbors(self.unique_id)
        total_neighbors = self.model.get_neighbors(self.unique_id)
        adopted_ratio = len(adopted_neighbors) / len(total_neighbors) if total_neighbors else 0.0
        req = DecisionRequest(
            agent_id=self.unique_id,
            openness=self.profile.openness,
            risk_tolerance=self.profile.risk_tolerance,
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
