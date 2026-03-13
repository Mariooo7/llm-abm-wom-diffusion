import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SimulationConfig:
    """
    单次仿真运行所需的配置快照。

    约定：
    - 研究参数来自 experiments/configs/group_*.yaml
    - 工程参数（如 LLM_API_KEY）来自环境变量
    - 运行期不再“猜测/推断”缺失字段，缺啥就按默认值填充，避免隐式行为
    """
    group: str
    network_type: str
    n_agents: int
    avg_degree: int
    rewiring_prob: float
    wom_strength: str
    emotion_arousal: float
    wom_corpus_path: str
    wom_memory_limit: int
    wom_share_multiplier: float
    innovation_coef: float
    imitation_coef: float
    n_steps: int
    n_repetitions: int
    seed: int | None
    use_llm: bool
    llm_sampling_ratio: float
    llm_provider: str
    llm_model: str
    llm_base_url: str
    llm_api_key_env: str
    llm_temperature: float
    llm_timeout_seconds: int
    llm_gateway_url: str
    llm_gateway_autostart: bool


def get_config(group: str) -> SimulationConfig:
    """
    加载指定实验组配置（A/B/C/D）。

    这里同时把“研究语义边界”固化为硬约束：
    - simulation.use_llm 必须为 true
    - simulation.llm_sampling_ratio 必须为 1.0

    这样做的目的不是限制扩展，而是防止试跑时悄悄进入“半规则半 LLM”的混合模式，
    导致不同批次结果不可比。
    """
    file_name = f"group_{group.lower()}.yaml"
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "experiments" / "configs" / file_name
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    network = data.get("network", {})
    wom = data.get("wom", {})
    bass = data.get("bass", {})
    simulation = data.get("simulation", {})
    use_llm = simulation.get("use_llm", True)
    llm_sampling_ratio = float(simulation.get("llm_sampling_ratio", 1.0))
    if use_llm is not True:
        raise ValueError("研究模式要求 simulation.use_llm 必须为 true")
    if llm_sampling_ratio != 1.0:
        raise ValueError("研究模式要求 simulation.llm_sampling_ratio 必须为 1.0")
    llm_server_addr = os.getenv("LLM_SERVER_ADDR", "").strip() or "127.0.0.1:18080"
    llm_gateway_autostart_raw = os.getenv("LLM_GATEWAY_AUTOSTART", "").strip().lower()
    llm_gateway_url_default = f"http://{llm_server_addr}/decide"
    return SimulationConfig(
        group=data.get("group", group.upper()),
        network_type=network.get("type", "small_world"),
        n_agents=int(network.get("n_nodes", 100)),
        avg_degree=int(network.get("avg_degree", 8)),
        rewiring_prob=float(network.get("rewiring_prob", 0.1)),
        wom_strength=wom.get("strength", "strong"),
        emotion_arousal=float(wom.get("emotion_arousal", 0.5)),
        wom_corpus_path=str(wom.get("corpus_path", "data/wom/wom_corpus.csv")),
        wom_memory_limit=int(wom.get("memory_limit", 5)),
        wom_share_multiplier=float(wom.get("share_multiplier", 1.0)),
        innovation_coef=float(bass.get("innovation_coef", 0.01)),
        imitation_coef=float(bass.get("imitation_coef", 0.3)),
        n_steps=int(simulation.get("n_steps", 60)),
        n_repetitions=int(simulation.get("n_repetitions", 15)),
        seed=simulation.get("seed", 42),
        use_llm=True,
        llm_sampling_ratio=llm_sampling_ratio,
        llm_provider=str(os.getenv("LLM_PROVIDER", "").strip() or "aliyun_bailian"),
        llm_model=str(os.getenv("LLM_MODEL", "").strip() or "qwen3.5-flash"),
        llm_base_url=str(
            os.getenv("LLM_BASE_URL", "").strip()
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ),
        llm_api_key_env=str(os.getenv("LLM_API_KEY_ENV", "").strip() or "LLM_API_KEY"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "").strip() or 0.2),
        llm_timeout_seconds=int(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "").strip() or 180),
        llm_gateway_url=str(os.getenv("LLM_GATEWAY_URL", "").strip() or llm_gateway_url_default),
        llm_gateway_autostart=(
            llm_gateway_autostart_raw in {"1", "true", "yes"}
            if llm_gateway_autostart_raw
            else True
        ),
    )
