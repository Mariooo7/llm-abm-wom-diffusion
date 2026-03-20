"""
扩散仿真核心模型（Mesa ABM）。

这套模型的职责很窄：按配置生成网络与个体，按时间步推进，并把每步的采纳状态与汇总指标落盘。
LLM 只负责“当前时间步是否产生采纳冲动”的一次性判断，不参与跨期规划；工程侧允许并行多个 repetition，
但单次 run 内仍按随机异步顺序逐个 agent 更新，避免把并发引入到行为语义里。
"""

import csv
import time
from pathlib import Path
from typing import Any

import numpy as np
from agents.agent import Agent, AgentProfile
from config.settings import SimulationConfig
from llm import DecisionClient
from llm.decision_client import is_retriable_decision_error_message
from mesa import Model
from mesa.datacollection import DataCollector
from networks.generator import compute_network_metrics, generate_network


class DiffusionModel(Model):
    decision_trace_fields = [
        "step",
        "agent_id",
        "openness",
        "risk_tolerance",
        "adopted_ratio",
        "wom_high_arousal_ratio",
        "innovation_coef",
        "imitation_coef",
        "wom_bucket",
        "wom_count",
        "probability",
        "adopt_by_threshold",
        "adopt_final",
        "reasoning",
        "source",
    ]
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
        self.decision_trace: list[dict[str, Any]] = []
        self.wom_messages_sent = 0
        self.wom_messages_delivered = 0
        self.wom_messages_sent_high = 0
        self.wom_messages_sent_low = 0
        self.initial_innovators = 0
        self.wom_strength = self._normalize_wom_strength(config.wom_strength)
        self.wom_high_arousal_ratio = float(np.clip(config.wom_high_arousal_ratio, 0.0, 1.0))
        self.wom_bucket = f"{self.wom_strength}_mix"
        self.wom_corpus = self._load_wom_corpus(config.wom_corpus_path)

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
        self._seed_initial_innovators()

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
                "last_probability": lambda a: a.memory.last_decision_probability,
                "last_adopt_by_threshold": lambda a: a.memory.last_decision_adopt,
                "last_adopt_final": lambda a: a.memory.last_decision_final_adopt,
                "last_reasoning": lambda a: a.memory.last_decision_reasoning,
                "last_source": lambda a: a.memory.last_decision_source,
            },
        )

    @staticmethod
    def _normalize_wom_strength(strength: str) -> str:
        normalized_strength = strength.strip().lower()
        if normalized_strength not in {"strong", "weak"}:
            raise ValueError("wom.strength must be one of: strong, weak")
        return normalized_strength

    def _load_wom_corpus(self, corpus_path: str) -> dict[str, list[str]]:
        project_root = Path(__file__).resolve().parents[2]
        path = Path(corpus_path)
        if not path.is_absolute():
            path = project_root / path
        if not path.exists():
            raise FileNotFoundError(f"WOM corpus file not found: {path}")
        buckets: dict[str, list[str]] = {
            "strong_low": [],
            "strong_high": [],
            "weak_low": [],
            "weak_high": [],
        }
        with path.open("r", encoding="utf-8", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                strength = str(row.get("strength", "")).strip().lower()
                arousal_bin = str(row.get("arousal_bin", "")).strip().lower()
                text = str(row.get("text", "")).strip()
                if not text:
                    continue
                bucket_key = f"{strength}_{arousal_bin}"
                if bucket_key in buckets:
                    buckets[bucket_key].append(text)
        return buckets

    def _pick_wom_message(self) -> tuple[str, str]:
        arousal_bin = "high" if self.random.random() < self.wom_high_arousal_ratio else "low"
        bucket_key = f"{self.wom_strength}_{arousal_bin}"
        primary_pool = self.wom_corpus.get(bucket_key, [])
        if primary_pool:
            return str(self.random.choice(primary_pool)), bucket_key
        strength = self.wom_strength
        fallback_pool = []
        fallback_bucket = ""
        for key, values in self.wom_corpus.items():
            if key.startswith(f"{strength}_"):
                if not fallback_bucket and values:
                    fallback_bucket = key
                fallback_pool.extend(values)
        if fallback_pool:
            return str(self.random.choice(fallback_pool)), fallback_bucket or bucket_key
        raise ValueError(
            f"WOM corpus has no messages for strength={self.wom_strength}, bucket={bucket_key}"
        )

    def _propagate_wom_messages(self) -> None:
        senders = [agent for agent in self.population.values() if agent.memory.has_adopted]
        for sender in senders:
            if self.random.random() >= sender.sharing_probability():
                continue
            message, bucket_key = self._pick_wom_message()
            neighbors = self.get_neighbors(sender.unique_id)
            if not neighbors:
                continue
            self.wom_messages_sent += 1
            if bucket_key.endswith("_high"):
                self.wom_messages_sent_high += 1
            elif bucket_key.endswith("_low"):
                self.wom_messages_sent_low += 1
            for neighbor_id in neighbors:
                receiver = self.population[neighbor_id]
                receiver.memory.wom_received.append(message)
                if len(receiver.memory.wom_received) > self.config.wom_memory_limit:
                    receiver.memory.wom_received = receiver.memory.wom_received[
                        -self.config.wom_memory_limit :
                    ]
                self.wom_messages_delivered += 1

    def _initialize_agents(self) -> None:
        """
        逐个节点创建 Agent。

        这里把网络节点 ID 作为 agent_id，确保邻接关系与个体索引一一对应，便于复现与排查。
        """
        for node_id in self.network.nodes():
            profile = AgentProfile(agent_id=node_id)
            agent = Agent(agent_id=node_id, profile=profile, model=self)
            self.population[node_id] = agent

    def _seed_initial_innovators(self) -> None:
        """
        按初始火种率设置初始采纳者。

        语义：与外生创新概率(p)解耦，initial_seed_ratio 代表产品内测或冷启动阶段的种子用户比例。
        离散个体场景下用 round(N * initial_seed_ratio) 近似期望创新者数量，
        并在 ratio > 0 时至少保留 1 个种子，避免冷启动阶段 WOM 完全无源。
        """
        expected = int(round(self.config.n_agents * max(0.0, self.config.initial_seed_ratio)))
        if self.config.initial_seed_ratio > 0:
            expected = max(1, expected)
        seed_count = min(self.config.n_agents, expected)
        if seed_count <= 0:
            self.initial_innovators = 0
            return
        seeded_ids = self.random.sample(list(self.population.keys()), seed_count)
        for agent_id in seeded_ids:
            agent = self.population[agent_id]
            agent.memory.has_adopted = True
            agent.memory.adoption_time = 0
        self.initial_innovators = seed_count

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

    def _decision_retry_sleep_seconds(self, attempt_index: int) -> float:
        base = self.config.llm_decision_retry_backoff_seconds
        if base <= 0:
            return 0.0
        return base * (2.0**attempt_index)

    def _run_agent_step_with_retry(self, agent_id: int) -> None:
        attempts_total = max(1, self.config.llm_decision_retry_attempts + 1)
        for attempt in range(attempts_total):
            try:
                self.population[agent_id].step()
                return
            except Exception as exc:
                retriable = is_retriable_decision_error_message(str(exc))
                if attempt >= attempts_total - 1 or not retriable:
                    raise
                sleep_seconds = self._decision_retry_sleep_seconds(attempt)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

    def step(self) -> None:
        """
        推进一个时间步。

        Mesa 的 scheduler 并未使用；这里直接在 model 内部做随机异步更新，
        目的是让“并发”只发生在 repetition 之间，不进入单次 run 的行为语义。

        容错边界：
        - 单个 agent 的决策调用失败时，先在“当前时间步”内局部重试；
        - 只有局部重试耗尽后，才把异常抛给 run 级重试；
        - 因此 run 可以从失败点继续，而不是从 step=0 整轮重跑。
        """
        self._propagate_wom_messages()
        agent_ids = list(self.population.keys())
        self.random.shuffle(agent_ids)
        for agent_id in agent_ids:
            self._run_agent_step_with_retry(agent_id)
        self.datacollector.collect(self)
        self.current_step += 1

        total_adopters = sum(1 for a in self.population.values() if a.memory.has_adopted)
        if total_adopters >= self.config.n_agents or self.current_step >= self.config.n_steps:
            self.running = False

    def record_decision(self, decision_row: dict[str, Any]) -> None:
        self.decision_trace.append(decision_row)

    def get_decision_trace(self) -> list[dict[str, Any]]:
        return list(self.decision_trace)

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
                "wom_bucket": self.wom_bucket,
                "wom_high_arousal_ratio": self.wom_high_arousal_ratio,
                "wom_corpus_path": self.config.wom_corpus_path,
                "wom_memory_limit": self.config.wom_memory_limit,
                "wom_share_multiplier": self.config.wom_share_multiplier,
                "initial_seed_ratio": self.config.initial_seed_ratio,
                "n_agents": self.config.n_agents,
                "n_steps": self.config.n_steps,
            },
            "wom_usage": {
                "messages_sent": self.wom_messages_sent,
                "messages_delivered": self.wom_messages_delivered,
                "messages_sent_high": self.wom_messages_sent_high,
                "messages_sent_low": self.wom_messages_sent_low,
            },
            "bootstrap_usage": {"initial_innovators": self.initial_innovators},
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
