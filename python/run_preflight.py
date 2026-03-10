import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from config.settings import SimulationConfig, get_config
from models import DiffusionModel


def load_dotenv_if_exists(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def run_one(config: SimulationConfig, log_interval: int) -> dict[str, Any]:
    model = DiffusionModel(config)
    interval = max(1, log_interval)
    started_at = time.perf_counter()
    run_header = (
        f"[run] group={config.group} seed={config.seed} "
        f"n_agents={config.n_agents} n_steps={config.n_steps}"
    )
    print(
        run_header,
        flush=True,
    )
    while model.running:
        model.step()
        if model.current_step % interval == 0 or not model.running:
            adopters = sum(1 for a in model.population.values() if a.memory.has_adopted)
            rate = adopters / config.n_agents
            elapsed = time.perf_counter() - started_at
            progress_line = (
                f"[progress] group={config.group} seed={config.seed} "
                f"step={model.current_step}/{config.n_steps} "
                f"adopters={adopters}/{config.n_agents} rate={rate:.4f} "
                f"elapsed={elapsed:.1f}s"
            )
            print(
                progress_line,
                flush=True,
            )
    metrics = model.get_metrics()
    result = {
        "group": config.group,
        "seed": config.seed,
        "n_agents": config.n_agents,
        "n_steps": config.n_steps,
        "network_type": config.network_type,
        "wom_strength": config.wom_strength,
        "final_adoption_rate": metrics["final_adoption_rate"],
        "total_adopters": metrics["total_adopters"],
        "avg_adoption_time": metrics["avg_adoption_time"],
        "llm_usage": metrics["llm_usage"],
    }
    total_elapsed = time.perf_counter() - started_at
    done_line = (
        f"[done] group={config.group} seed={config.seed} "
        f"final_adoption_rate={result['final_adoption_rate']:.4f} "
        f"model_calls={result['llm_usage']['model_calls']} "
        f"elapsed={total_elapsed:.1f}s"
    )
    print(done_line, flush=True)
    return result


def build_config(
    group: str,
    seed: int,
    n_agents: int | None,
    n_steps: int | None,
    timeout_seconds: int | None,
) -> SimulationConfig:
    cfg = get_config(group)
    cfg.seed = seed
    if n_agents is not None:
        cfg.n_agents = n_agents
    if n_steps is not None:
        cfg.n_steps = n_steps
    if timeout_seconds is not None:
        cfg.llm_timeout_seconds = timeout_seconds
    return cfg


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    cfg = build_config(args.group, args.seed, args.n_agents, args.n_steps, args.timeout_seconds)
    result = run_one(cfg, args.log_interval)
    return {
        "mode": "smoke",
        "config": asdict(cfg),
        "result": result,
    }


def run_calibration(args: argparse.Namespace) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    for group in args.groups:
        for rep in range(args.repetitions):
            seed = args.seed_start + rep
            cfg = build_config(group, seed, args.n_agents, args.n_steps, args.timeout_seconds)
            summaries.append(run_one(cfg, args.log_interval))
    grouped: dict[str, list[float]] = {}
    for row in summaries:
        grouped.setdefault(str(row["group"]), []).append(float(row["final_adoption_rate"]))
    aggregate = {
        group: {
            "mean_final_adoption_rate": sum(values) / len(values),
            "min_final_adoption_rate": min(values),
            "max_final_adoption_rate": max(values),
            "runs": len(values),
        }
        for group, values in grouped.items()
    }
    return {
        "mode": "calibration",
        "settings": {
            "groups": args.groups,
            "repetitions": args.repetitions,
            "seed_start": args.seed_start,
            "n_agents": args.n_agents,
            "n_steps": args.n_steps,
        },
        "aggregate": aggregate,
        "runs": summaries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "calibration"], required=True)
    parser.add_argument("--group", default="A")
    parser.add_argument("--groups", nargs="+", default=["A", "B", "C", "D"])
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--seed-start", type=int, default=201)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--n-agents", type=int, default=None)
    parser.add_argument("--n-steps", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--log-interval", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv_if_exists(project_root)
    if args.mode == "smoke":
        output = run_smoke(args)
    else:
        output = run_calibration(args)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
