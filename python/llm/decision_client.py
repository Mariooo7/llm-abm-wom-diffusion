"""
LLM 决策客户端。

Python 侧不直接对接具体供应商 SDK，而是通过 Go 网关统一转发：
- 网关负责：系统提示词、重试/超时、供应商兼容层、输出清洗。
- Python 负责：把当前时间步的个体状态打包成 JSON，发给网关，并汇总 token 用量。
"""

import json
import os
import subprocess
import time
from atexit import register
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from urllib import error, request

RETRIABLE_ERROR_KEYWORDS = (
    "gateway timeout",
    "timed out",
    "gateway unavailable",
    "http error 429",
    "status=429",
    "limit_burst_rate",
    "http error 502",
    "http error 503",
    "http error 504",
    "status=502",
    "status=503",
    "status=504",
)


def is_retriable_decision_error_message(message: str) -> bool:
    normalized = message.lower()
    return any(keyword in normalized for keyword in RETRIABLE_ERROR_KEYWORDS)


@dataclass
class DecisionRequest:
    """
    单次决策的输入快照（一个 agent 在一个时间步做一次判断）。

    字段命名与 Go 网关的 decisionRequest 保持一致，避免两边各自“翻译”导致字段漂移。
    """

    agent_id: int
    openness: float
    risk_tolerance: float
    adopted_ratio: float
    wom_high_arousal_ratio: float
    wom_strength: str
    wom_messages: list[str]
    innovation_coef: float
    imitation_coef: float


@dataclass
class DecisionResult:
    """单次决策输出（网关已保证 JSON 结构与概率范围）。"""

    adopt: bool
    probability: float
    reasoning: str
    source: str


@dataclass
class DecisionTask:
    req: DecisionRequest
    context_key: str


class DecisionServiceError(RuntimeError):
    pass


class DecisionClient:
    """
    决策入口封装。

    两种工作方式：
    - gateway_autostart=True：本地未检测到网关时自动 `go run` 拉起（适合脚本一键跑）。
    - gateway_autostart=False：要求外部先启动网关（适合部署/容器化）。
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key_env: str,
        temperature: float,
        timeout_seconds: int,
        gateway_url: str,
        gateway_autostart: bool,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.api_key_env = api_key_env
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.gateway_url = gateway_url
        self.gateway_autostart = gateway_autostart
        if os.getenv(api_key_env, "").strip() == "":
            raise DecisionServiceError(f"missing api key env: {api_key_env}")
        self.model_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self._usage_lock = Lock()
        self._server_process: subprocess.Popen[str] | None = None
        self._server_log_handle: Any | None = None
        self._ensure_gateway()

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _health_url(self) -> str:
        return self.gateway_url.replace("/decide", "/health")

    def _gateway_alive(self) -> bool:
        """探活：用于判断是否需要自动拉起网关。"""
        health_req = request.Request(self._health_url(), method="GET")
        try:
            with request.urlopen(health_req, timeout=self.timeout_seconds) as resp:
                status_code = int(getattr(resp, "status", 0))
                return 200 <= status_code < 300
        except Exception:
            return False

    def _stop_gateway(self) -> None:
        """退出时清理自动拉起的网关进程与日志句柄。"""
        if self._server_process is None:
            if self._server_log_handle is not None:
                self._server_log_handle.close()
                self._server_log_handle = None
            return
        if self._server_process.poll() is None:
            self._server_process.terminate()
        if self._server_log_handle is not None:
            self._server_log_handle.close()
            self._server_log_handle = None

    def _start_gateway(self) -> None:
        """
        自动拉起 Go 网关。

        这里只注入网关运行所需的最小环境变量，避免把 Python 侧的杂项 env 带进来污染实验。
        """
        go_dir = self._project_root() / "go"
        log_dir = self._project_root() / "data" / "results"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "go_gateway_autostart.log"
        env = os.environ.copy()
        env["LLM_SERVER_ADDR"] = self.gateway_url.removeprefix("http://").split("/")[0]
        env["LLM_MODEL"] = self.model
        env["LLM_BASE_URL"] = self.base_url
        env["LLM_TEMPERATURE"] = str(self.temperature)
        env["LLM_REQUEST_TIMEOUT_SECONDS"] = str(self.timeout_seconds)
        self._server_log_handle = log_path.open("a", encoding="utf-8")
        self._server_process = subprocess.Popen(
            ["go", "run", "cmd/main.go"],
            cwd=str(go_dir),
            env=env,
            stdout=self._server_log_handle,
            stderr=self._server_log_handle,
            text=True,
        )
        register(self._stop_gateway)

    def _ensure_gateway(self) -> None:
        """保证网关可用；不可用时按配置选择自动拉起或直接失败。"""
        if self._gateway_alive():
            return
        if not self.gateway_autostart:
            raise DecisionServiceError("gateway unavailable and autostart disabled")
        try:
            self._start_gateway()
        except Exception as exc:
            raise DecisionServiceError(f"failed to start gateway: {exc}") from exc
        for _ in range(25):
            if self._gateway_alive():
                return
            time.sleep(0.2)
        raise DecisionServiceError("gateway startup timeout")

    def _parse_content(self, content: str) -> DecisionResult:
        """
        解析网关响应内容。

        网关端已经做过 JSON 提取与概率 clamp，这里再做一次边界保护，保证上游调用不因脏数据崩溃。
        """
        data = json.loads(content)
        probability = float(data.get("probability", 0.0))
        probability = max(0.0, min(1.0, probability))
        adopt = bool(data.get("adopt", probability >= 0.5))
        reasoning = str(data.get("reasoning", ""))
        source = str(data.get("source", "llm_http_direct"))
        return DecisionResult(
            adopt=adopt,
            probability=probability,
            reasoning=reasoning,
            source=source,
        )

    def _build_payload(self, req: DecisionRequest, context_key: str) -> dict[str, Any]:
        """
        构造发送到网关的 payload。

        wom_messages 只取最近 5 条：既贴近“近期口碑”的认知事实，也能控制提示长度与 token 成本。
        """
        return {
            "agent_id": req.agent_id,
            "openness": round(req.openness, 4),
            "risk_tolerance": round(req.risk_tolerance, 4),
            "adopted_ratio": round(req.adopted_ratio, 4),
            "wom_high_arousal_ratio": round(req.wom_high_arousal_ratio, 4),
            "wom_strength": req.wom_strength,
            "wom_messages": req.wom_messages[-5:],
            "innovation_coef": round(req.innovation_coef, 4),
            "imitation_coef": round(req.imitation_coef, 4),
            "context_key": context_key,
        }

    def _call_gateway(self, payload: dict[str, Any]) -> dict[str, Any]:
        """同步调用网关的 /decide 接口，错误统一包装成 DecisionServiceError。"""
        req = request.Request(
            self.gateway_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    return parsed
                raise ValueError("gateway response is not a JSON object")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise DecisionServiceError(f"gateway http error {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise DecisionServiceError(f"gateway unavailable: {exc}") from exc
        except TimeoutError as exc:
            raise DecisionServiceError(f"gateway timeout: {exc}") from exc

    def decide(self, req: DecisionRequest, context_key: str) -> DecisionResult:
        """对单个 agent 做一次决策调用，并把 token 统计累积到 client 上。"""
        payload = self._build_payload(req, context_key)
        response = self._call_gateway(payload)
        result = self._parse_content(json.dumps(response, ensure_ascii=False))
        self._merge_usage(response)
        return result

    def _merge_usage(self, response: dict[str, Any]) -> None:
        with self._usage_lock:
            self.model_calls += int(response.get("model_calls", 1) or 0)
            self.prompt_tokens += int(response.get("prompt_tokens", 0) or 0)
            self.completion_tokens += int(response.get("completion_tokens", 0) or 0)
            self.total_tokens += int(response.get("total_tokens", 0) or 0)

    def decide_many(self, tasks: list[DecisionTask], concurrency: int = 10) -> list[DecisionResult]:
        """
        批量并发决策。

        注意：并发仅用于提升吞吐；语义上每个 task 仍是“某个 agent 在某一步的独立判断”，
        不在这里引入跨 task 的共享状态。
        """
        if not tasks:
            return []
        workers = max(1, min(concurrency, len(tasks)))
        results: list[DecisionResult | None] = [None] * len(tasks)

        def _run_one(index: int, task: DecisionTask) -> tuple[int, DecisionResult]:
            return index, self.decide(task.req, task.context_key)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_run_one, idx, task) for idx, task in enumerate(tasks)]
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result
        return [item for item in results if item is not None]
