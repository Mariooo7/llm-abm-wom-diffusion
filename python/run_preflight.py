import argparse
import csv
import json
import os
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from config.settings import SimulationConfig, get_config
from llm.decision_client import (
    DecisionClient,
    DecisionRequest,
    DecisionTask,
    is_retriable_decision_error_message,
)
from models import DiffusionModel

try:
    from rich.console import Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except Exception:
    Group = Any  # type: ignore[misc,assignment]
    Live = Any  # type: ignore[misc,assignment]
    Panel = Any  # type: ignore[misc,assignment]
    Table = Any  # type: ignore[misc,assignment]
    RICH_AVAILABLE = False


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


def _format_bar(current: int, total: int, width: int = 12) -> str:
    safe_total = max(1, total)
    ratio = max(0.0, min(1.0, current / safe_total))
    filled = int(round(ratio * width))
    return "█" * filled + "·" * (width - filled)


def _status_counts(states: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {"queued": 0, "running": 0, "retrying": 0, "done": 0, "failed": 0}
    for item in states.values():
        status = str(item.get("status", "queued"))
        if status in counts:
            counts[status] += 1
        else:
            counts["queued"] += 1
    return counts


def _run_status_marker(status: str) -> str:
    if status == "done":
        return "✓"
    if status == "failed":
        return "✗"
    if status == "running":
        return "▶"
    if status == "retrying":
        return "↻"
    if status == "starting":
        return "…"
    return "·"


def _format_group_run_steps(
    per_group: list[dict[str, Any]],
    max_items: int | None = None,
) -> str:
    ordered = sorted(per_group, key=lambda item: int(item.get("rep", 0)))
    if max_items is not None:
        visible = ordered[:max_items]
    else:
        visible = ordered
    tokens: list[str] = []
    for item in visible:
        rep = int(item.get("rep", 0))
        step = int(item.get("step", 0))
        n_steps = int(item.get("n_steps", 0))
        status = str(item.get("status", "queued"))
        marker = _run_status_marker(status)
        if status == "done":
            tokens.append(f"r{rep}:{n_steps}{marker}")
        else:
            tokens.append(f"r{rep}:{step}/{n_steps}{marker}")
    hidden = len(ordered) - len(visible)
    if hidden > 0:
        tokens.append(f"+{hidden}")
    return " ".join(tokens) if tokens else "-"


def _build_adoption_timeline(model: DiffusionModel, n_agents: int) -> list[dict[str, float | int]]:
    records: list[dict[str, float | int]] = []
    initial = int(getattr(model, "initial_innovators", 0))
    base_rate = initial / max(1, n_agents)
    records.append(
        {
            "step": 0,
            "total_adopters": initial,
            "adoption_rate": round(base_rate, 6),
        }
    )
    frame = model.datacollector.get_model_vars_dataframe()
    for row_index, (_, row) in enumerate(frame.iterrows(), start=1):
        total_adopters = int(row["total_adopters"])
        adoption_rate = float(row["adoption_rate"])
        records.append(
            {
                "step": row_index,
                "total_adopters": total_adopters,
                "adoption_rate": round(adoption_rate, 6),
            }
        )
    return records


def _build_adoption_checkpoints(
    timeline: list[dict[str, float | int]],
    every_steps: int = 10,
) -> list[dict[str, float | int]]:
    if every_steps <= 0:
        every_steps = 10
    checkpoints: list[dict[str, float | int]] = []
    last_step = int(timeline[-1]["step"]) if timeline else 0
    for row in timeline:
        step = int(row["step"])
        if step == 0 or step % every_steps == 0 or step == last_step:
            checkpoints.append(row)
    return checkpoints


def _first_step_at_rate(
    timeline: list[dict[str, float | int]],
    threshold: float,
) -> int | None:
    for row in timeline:
        if float(row["adoption_rate"]) >= threshold:
            return int(row["step"])
    return None


def _compute_adoption_auc(
    timeline: list[dict[str, float | int]],
    n_steps: int,
) -> float:
    if len(timeline) < 2:
        return round(float(timeline[0]["adoption_rate"]) if timeline else 0.0, 6)
    area = 0.0
    prev_step = int(timeline[0]["step"])
    prev_rate = float(timeline[0]["adoption_rate"])
    for row in timeline[1:]:
        step = int(row["step"])
        rate = float(row["adoption_rate"])
        area += (prev_rate + rate) * 0.5 * max(0, step - prev_step)
        prev_step = step
        prev_rate = rate
    normalized = area / max(1, n_steps)
    return round(normalized, 6)


def _render_formal_batch_compact(
    states: dict[str, dict[str, Any]],
    groups: list[str],
    total_runs: int,
    started_at: float,
    recent_events: list[str],
) -> str:
    counts = _status_counts(states)
    elapsed = time.perf_counter() - started_at
    completion = counts["done"] + counts["failed"]
    lines = [
        (
            f"[batch] elapsed={elapsed:.1f}s "
            f"progress={completion}/{total_runs} failed={counts['failed']}"
        )
    ]
    group_parts: list[str] = []
    for group in groups:
        per_group = [v for v in states.values() if str(v.get("group")) == group]
        group_total = len(per_group)
        done_count = sum(1 for v in per_group if str(v.get("status")) == "done")
        fail_count = sum(1 for v in per_group if str(v.get("status")) == "failed")
        active = sum(
            1
            for v in per_group
            if str(v.get("status")) in {"running", "retrying", "starting"}
        )
        max_step = max((int(v.get("step", 0)) for v in per_group), default=0)
        n_steps = max((int(v.get("n_steps", 0)) for v in per_group), default=0)
        bar = _format_bar(max_step, n_steps if n_steps > 0 else 1)
        rates = [float(v.get("rate", 0.0)) for v in per_group]
        rate_mean = sum(rates) / len(rates) if rates else 0.0
        rate_max = max(rates) if rates else 0.0
        calls_done = sum(
            int(v.get("model_calls", 0))
            for v in per_group
            if str(v.get("status")) == "done"
        )
        summary = (
            f"{group} {done_count}/{group_total} {bar} "
            f"stepμ/max={max_step}/{n_steps} rateμ/max={rate_mean:.2f}/{rate_max:.2f} "
            f"calls={calls_done} active={active} fail={fail_count}"
        )
        group_parts.append(summary)
    lines.append("groups: " + " | ".join(group_parts))
    for group in groups:
        per_group = [v for v in states.values() if str(v.get("group")) == group]
        lines.append(f"runs[{group}]: {_format_group_run_steps(per_group, max_items=10)}")
    lines.append("legend: ✓ done  ✗ failed  ▶ running  ↻ retrying  … starting  · queued")
    if recent_events:
        lines.append("recent: " + " | ".join(recent_events[-2:]))
    return "\n".join(lines)


def _make_snapshot(task_states: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "group": value["group"],
            "rep": value["rep"],
            "seed": value["seed"],
            "status": value["status"],
            "attempt": value["attempt"],
            "step": value["step"],
            "n_steps": value["n_steps"],
            "adopters": value["adopters"],
            "n_agents": value["n_agents"],
            "rate": value["rate"],
            "elapsed": value["elapsed"],
            "model_calls": value["model_calls"],
            "total_tokens": value["total_tokens"],
            "error": value["error"],
        }
        for key, value in task_states.items()
    }


def _render_formal_batch_rich(
    states: dict[str, dict[str, Any]],
    groups: list[str],
    total_runs: int,
    started_at: float,
    recent_events: list[str],
) -> Any:
    counts = _status_counts(states)
    elapsed = time.perf_counter() - started_at
    completion = counts["done"] + counts["failed"]
    header = Table.grid(expand=True)
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        "Formal Batch Live Board",
        f"elapsed={elapsed:.1f}s  done={counts['done']}/{total_runs} failed={counts['failed']}",
    )
    overview = Table.grid(expand=True)
    overview.add_column()
    overview.add_column()
    overview.add_column()
    overview.add_column()
    overview.add_column()
    overview.add_row(
        f"[cyan]queued[/] {counts['queued']}",
        f"[blue]running[/] {counts['running']}",
        f"[yellow]retrying[/] {counts['retrying']}",
        f"[green]done[/] {counts['done']}",
        f"[red]failed[/] {counts['failed']}",
    )
    group_table = Table(expand=True, show_header=True, header_style="bold", box=None)
    group_table.add_column("Group", justify="center", width=6)
    group_table.add_column("Runs", justify="left", width=16)
    group_table.add_column("Step (μ/max)", justify="left", width=20)
    group_table.add_column("Adopt (μ/max)", justify="right", width=14)
    group_table.add_column("Calls", justify="right", width=10)
    group_table.add_column("Active", justify="right", width=8)
    group_table.add_column("Fail", justify="right", width=6)
    group_run_steps: dict[str, str] = {}
    for group in groups:
        per_group = [v for v in states.values() if str(v.get("group")) == group]
        group_total = len(per_group)
        done_count = sum(1 for v in per_group if str(v.get("status")) == "done")
        fail_count = sum(1 for v in per_group if str(v.get("status")) == "failed")
        active = sum(
            1
            for v in per_group
            if str(v.get("status")) in {"running", "retrying", "starting"}
        )
        max_step = max((int(v.get("step", 0)) for v in per_group), default=0)
        mean_step = sum(int(v.get("step", 0)) for v in per_group) / max(1, group_total)
        n_steps = max((int(v.get("n_steps", 0)) for v in per_group), default=0)
        rates = [float(v.get("rate", 0.0)) for v in per_group]
        rate_mean = sum(rates) / len(rates) if rates else 0.0
        rate_max = max(rates) if rates else 0.0
        calls_done = sum(
            int(v.get("model_calls", 0))
            for v in per_group
            if str(v.get("status")) == "done"
        )
        group_run_steps[group] = _format_group_run_steps(per_group, max_items=None)
        runs_bar = _format_bar(done_count, group_total if group_total > 0 else 1, width=10)
        step_bar = _format_bar(int(round(mean_step)), n_steps if n_steps > 0 else 1, width=12)
        runs_color = "green" if done_count == group_total else "white"
        group_table.add_row(
            f"[bold]{group}[/]",
            f"[{runs_color}]{runs_bar}[/] {done_count}/{group_total}",
            f"[cyan]{step_bar}[/] {int(mean_step)}/{max_step}",
            f"{rate_mean:.3f} / {rate_max:.3f}",
            str(calls_done),
            f"[{'blue' if active > 0 else 'dim'}]{active}[/]",
            f"[{'red' if fail_count > 0 else 'dim'}]{fail_count}[/]",
        )
    runs_table = Table(expand=True, show_header=True, header_style="bold", box=None)
    runs_table.add_column("Group", justify="center", width=6)
    runs_table.add_column("Per-Run Step", overflow="fold")
    for group in groups:
        runs_table.add_row(f"[bold]{group}[/]", group_run_steps.get(group, "-"))
    active_table = Table(expand=True, show_header=True, header_style="bold", box=None)
    active_table.add_column("Task", width=26)
    active_table.add_column("Status", width=10)
    active_table.add_column("Step", width=12, justify="right")
    active_table.add_column("Rate", width=8, justify="right")
    active_table.add_column("Try", width=5, justify="right")
    active_rows = [
        v
        for v in states.values()
        if str(v.get("status")) in {"running", "retrying", "starting"}
    ]
    active_rows.sort(
        key=lambda item: (
            str(item.get("status")),
            str(item.get("group")),
            int(item.get("rep", 0)),
        )
    )
    for item in active_rows[:10]:
        status = str(item.get("status"))
        style = "blue"
        if status == "retrying":
            style = "yellow"
        elif status == "starting":
            style = "magenta"
        active_table.add_row(
            f"{item['group']}-r{item['rep']}-s{item['seed']}",
            f"[{style}]{status}[/]",
            f"{item['step']}/{item['n_steps']}",
            f"{float(item['rate']):.3f}",
            str(item["attempt"]),
        )
    if not active_rows:
        active_table.add_row("-", "-", "-", "-", "-")
    events_table = Table(expand=True, show_header=True, header_style="bold", box=None)
    events_table.add_column("Recent Events", style="dim")
    if recent_events:
        for event in recent_events[-5:]:
            events_table.add_row(event)
    else:
        events_table.add_row("no recent events")
    footer = (
        f"progress={completion}/{total_runs} | "
        "legend: ✓ done  ✗ failed  ▶ running  ↻ retrying  … starting  · queued"
    )
    return Panel(
        Group(
            header,
            "",
            overview,
            "",
            group_table,
            "",
            runs_table,
            "",
            active_table,
            "",
            events_table,
            "",
            footer
        ),
        title="Batch Live Dashboard",
        border_style="cyan",
        padding=(1, 2)
    )


def run_one(
    config: SimulationConfig,
    log_interval: int,
    raw_output_path: Path | None = None,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
    emit_logs: bool = True,
    rep: int | None = None,
) -> dict[str, Any]:
    model = DiffusionModel(config)
    interval = max(1, log_interval)
    started_at = time.perf_counter()
    rep_prefix = f" rep={rep}" if rep is not None else ""
    run_header = (
        f"[run] group={config.group}{rep_prefix} seed={config.seed} "
        f"n_agents={config.n_agents} n_steps={config.n_steps}"
    )
    if emit_logs:
        print(
            run_header,
            flush=True,
        )
    if progress_hook is not None:
        progress_hook(
            {
                "event": "run_start",
                "group": config.group,
                "rep": rep,
                "seed": config.seed,
                "step": 0,
                "n_steps": config.n_steps,
                "adopters": 0,
                "n_agents": config.n_agents,
                "rate": 0.0,
                "elapsed": 0.0,
            }
        )
    while model.running:
        model.step()
        adopters = sum(1 for a in model.population.values() if a.memory.has_adopted)
        rate = adopters / config.n_agents
        elapsed = time.perf_counter() - started_at
        if progress_hook is not None:
            progress_hook(
                {
                    "event": "run_progress",
                    "group": config.group,
                    "rep": rep,
                    "seed": config.seed,
                    "step": model.current_step,
                    "n_steps": config.n_steps,
                    "adopters": adopters,
                    "n_agents": config.n_agents,
                    "rate": rate,
                    "elapsed": elapsed,
                }
            )
        if model.current_step % interval == 0 or not model.running:
            progress_line = (
                f"[progress] group={config.group}{rep_prefix} seed={config.seed} "
                f"step={model.current_step}/{config.n_steps} "
                f"adopters={adopters}/{config.n_agents} rate={rate:.4f} "
                f"elapsed={elapsed:.1f}s"
            )
            if emit_logs:
                print(
                    progress_line,
                    flush=True,
                )
    metrics = model.get_metrics()
    if raw_output_path is not None:
        raw_output_path.parent.mkdir(parents=True, exist_ok=True)
        trace_rows = model.get_decision_trace()
        with raw_output_path.open("w", encoding="utf-8", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=DiffusionModel.decision_trace_fields)
            writer.writeheader()
            if trace_rows:
                writer.writerows(trace_rows)
    adoption_timeline = _build_adoption_timeline(model, config.n_agents)
    adoption_checkpoints = _build_adoption_checkpoints(adoption_timeline, every_steps=10)
    t10_step = _first_step_at_rate(adoption_timeline, threshold=0.10)
    t50_step = _first_step_at_rate(adoption_timeline, threshold=0.50)
    auc_adoption = _compute_adoption_auc(adoption_timeline, n_steps=config.n_steps)
    result = {
        "group": config.group,
        "seed": config.seed,
        "n_agents": config.n_agents,
        "n_steps": config.n_steps,
        "network_type": config.network_type,
        "wom_strength": config.wom_strength,
        "wom_bucket": metrics["config"]["wom_bucket"],
        "final_adoption_rate": metrics["final_adoption_rate"],
        "total_adopters": metrics["total_adopters"],
        "avg_adoption_time": metrics["avg_adoption_time"],
        "wom_usage": metrics["wom_usage"],
        "bootstrap_usage": metrics.get("bootstrap_usage", {"initial_innovators": 0}),
        "llm_usage": metrics["llm_usage"],
        "adoption_timeline": adoption_timeline,
        "adoption_checkpoints": adoption_checkpoints,
        "t10_step": t10_step,
        "t50_step": t50_step,
        "auc_adoption": auc_adoption,
    }
    total_elapsed = time.perf_counter() - started_at
    result["elapsed_seconds"] = round(total_elapsed, 2)
    done_line = (
        f"[done] group={config.group}{rep_prefix} seed={config.seed} "
        f"final_adoption_rate={result['final_adoption_rate']:.4f} "
        f"model_calls={result['llm_usage']['model_calls']} "
        f"elapsed={total_elapsed:.1f}s"
    )
    if emit_logs:
        print(done_line, flush=True)
    if progress_hook is not None:
        progress_hook(
            {
                "event": "run_done",
                "group": config.group,
                "rep": rep,
                "seed": config.seed,
                "step": config.n_steps,
                "n_steps": config.n_steps,
                "adopters": result["total_adopters"],
                "n_agents": config.n_agents,
                "rate": result["final_adoption_rate"],
                "elapsed": total_elapsed,
                "model_calls": result["llm_usage"]["model_calls"],
            }
        )
    return result


def run_formal_batch(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[1]
    raw_dir = (project_root / args.raw_dir).resolve()
    results_dir = (project_root / args.output_dir).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    if args.summary_file:
        summary_path = (project_root / args.summary_file).resolve()
    else:
        summary_path = (results_dir / "batch_summary.csv").resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    tasks: list[tuple[str, int, int]] = []
    for group in args.groups:
        for rep in range(1, args.repetitions + 1):
            seed = args.seed_start + rep - 1
            tasks.append((group, rep, seed))

    workers = max(1, min(args.repetition_workers, len(tasks)))
    rows: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    recent_events: list[str] = []
    state_lock = threading.Lock()
    event_log_lock = threading.Lock()
    started_at = time.perf_counter()
    event_log_path = results_dir / "batch_events.jsonl"
    task_states: dict[str, dict[str, Any]] = {}
    for group, rep, seed in tasks:
        key = f"{group}:{rep}:{seed}"
        task_states[key] = {
            "key": key,
            "group": group,
            "rep": rep,
            "seed": seed,
            "status": "queued",
            "attempt": 0,
            "step": 0,
            "n_steps": int(args.n_steps or 0),
            "adopters": 0,
            "n_agents": int(args.n_agents or 0),
            "rate": 0.0,
            "elapsed": 0.0,
            "model_calls": 0,
            "total_tokens": 0,
            "error": "",
            "last_event_step": -1,
        }

    def _append_event(event: dict[str, Any]) -> None:
        payload = dict(event)
        payload["ts"] = round(time.time(), 3)
        with event_log_lock:
            with event_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    _append_event(
        {
            "event": "batch_start",
            "groups": list(args.groups),
            "repetitions": int(args.repetitions),
            "workers": int(workers),
            "n_agents": int(args.n_agents or 0),
            "n_steps": int(args.n_steps or 0),
        }
    )

    def _retry_sleep_seconds(attempt_index: int) -> float:
        base = cast(float, args.retry_backoff_seconds)
        if base <= 0:
            return 0.0
        if attempt_index <= 0:
            return base
        return base * (2.0**attempt_index)

    def _run_task(group: str, rep: int, seed: int) -> dict[str, Any]:
        run_retries = cast(int, args.run_retries)
        attempts_total = max(1, run_retries + 1)
        last_exc: Exception | None = None
        key = f"{group}:{rep}:{seed}"
        for attempt in range(attempts_total):
            with state_lock:
                current = task_states[key]
                current["status"] = "starting" if attempt == 0 else "retrying"
                current["attempt"] = attempt + 1
                current["error"] = ""
            _append_event(
                {
                    "event": "run_start",
                    "group": group,
                    "rep": rep,
                    "seed": seed,
                    "attempt": attempt + 1,
                }
            )

            def _on_progress(event: dict[str, Any]) -> None:
                should_log_event = False
                event_payload: dict[str, Any] | None = None
                with state_lock:
                    current = task_states[key]
                    current["status"] = "running"
                    current["step"] = int(event.get("step", current["step"]))
                    current["n_steps"] = int(event.get("n_steps", current["n_steps"]))
                    current["adopters"] = int(event.get("adopters", current["adopters"]))
                    current["n_agents"] = int(event.get("n_agents", current["n_agents"]))
                    current["rate"] = float(event.get("rate", current["rate"]))
                    current["elapsed"] = float(event.get("elapsed", current["elapsed"]))
                    step_now = int(current["step"])
                    n_steps_now = int(current["n_steps"])
                    if step_now > int(current["last_event_step"]) and (
                        step_now % 10 == 0 or step_now >= n_steps_now
                    ):
                        current["last_event_step"] = step_now
                        should_log_event = True
                        event_payload = {
                            "event": "run_progress",
                            "group": group,
                            "rep": rep,
                            "seed": seed,
                            "step": step_now,
                            "n_steps": n_steps_now,
                            "rate": round(float(current["rate"]), 6),
                            "adopters": int(current["adopters"]),
                            "elapsed": round(float(current["elapsed"]), 3),
                        }
                if should_log_event and event_payload is not None:
                    _append_event(event_payload)
            try:
                cfg = build_config(group, seed, args.n_agents, args.n_steps, args.timeout_seconds)
                raw_path = raw_dir / f"simulation_{cfg.group}_{rep}.csv"
                result = run_one(
                    cfg,
                    args.log_interval,
                    raw_path,
                    progress_hook=_on_progress,
                    emit_logs=False,
                    rep=rep,
                )
                model_slug = str(cfg.llm_model).replace("/", "_")
                metrics_payload = {
                    "group": cfg.group,
                    "rep": rep,
                    "seed": cfg.seed,
                    "attempt": attempt + 1,
                    "config": asdict(cfg),
                    "result": result,
                    "raw_file": str(raw_path),
                }
                timeline_path = results_dir / f"adoption_timeline_{cfg.group}_{rep}.csv"
                with timeline_path.open("w", encoding="utf-8", newline="") as timeline_file:
                    writer = csv.DictWriter(
                        timeline_file,
                        fieldnames=["step", "total_adopters", "adoption_rate", "is_checkpoint"],
                    )
                    writer.writeheader()
                    checkpoint_rows = cast(list[dict[str, Any]], result["adoption_checkpoints"])
                    checkpoint_steps = {int(item["step"]) for item in checkpoint_rows}
                    for item in cast(list[dict[str, Any]], result["adoption_timeline"]):
                        writer.writerow(
                            {
                                "step": int(item["step"]),
                                "total_adopters": int(item["total_adopters"]),
                                "adoption_rate": float(item["adoption_rate"]),
                                "is_checkpoint": int(item["step"]) in checkpoint_steps,
                            }
                        )
                metrics_path = results_dir / f"metrics_{cfg.group}_{rep}.json"
                metrics_payload["adoption_timeline_file"] = str(timeline_path)
                metrics_path.write_text(
                    json.dumps(metrics_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                row = {
                    "group": cfg.group,
                    "rep": rep,
                    "seed": cfg.seed,
                    "n_agents": cfg.n_agents,
                    "n_steps": cfg.n_steps,
                    "model": model_slug,
                    "final_adoption_rate": result["final_adoption_rate"],
                    "t10_step": result["t10_step"],
                    "t50_step": result["t50_step"],
                    "auc_adoption": result["auc_adoption"],
                    "total_adopters": result["total_adopters"],
                    "model_calls": result["llm_usage"]["model_calls"],
                    "prompt_tokens": result["llm_usage"]["prompt_tokens"],
                    "completion_tokens": result["llm_usage"]["completion_tokens"],
                    "total_tokens": result["llm_usage"]["total_tokens"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "raw_file": str(raw_path),
                    "adoption_timeline_file": str(timeline_path),
                    "metrics_file": str(metrics_path),
                    "attempt": attempt + 1,
                }
                with state_lock:
                    current = task_states[key]
                    current["status"] = "done"
                    current["step"] = int(cfg.n_steps)
                    current["n_steps"] = int(cfg.n_steps)
                    current["adopters"] = int(result["total_adopters"])
                    current["n_agents"] = int(cfg.n_agents)
                    current["rate"] = float(result["final_adoption_rate"])
                    current["elapsed"] = float(result["elapsed_seconds"])
                    current["model_calls"] = int(result["llm_usage"]["model_calls"])
                    current["total_tokens"] = int(result["llm_usage"]["total_tokens"])
                return row
            except Exception as exc:
                last_exc = exc
                message = str(exc)
                retriable = is_retriable_decision_error_message(message)
                with state_lock:
                    current = task_states[key]
                    current["error"] = message
                    if retriable and attempt < attempts_total - 1:
                        event = (
                            f"retry {group}-r{rep}-s{seed} "
                            f"attempt={attempt + 2}/{attempts_total}"
                        )
                        recent_events.append(event)
                        if len(recent_events) > 8:
                            del recent_events[:-8]
                if attempt >= attempts_total - 1 or not retriable:
                    _append_event(
                        {
                            "event": "run_error",
                            "group": group,
                            "rep": rep,
                            "seed": seed,
                            "attempt": attempt + 1,
                            "error": message[:240],
                            "retriable": bool(retriable),
                        }
                    )
                    raise
                sleep_seconds = _retry_sleep_seconds(attempt)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
        raise RuntimeError(str(last_exc) if last_exc is not None else "unknown error")

    def _consume_future_result(
        future: Any,
        future_to_task: dict[Any, tuple[str, int, int]],
    ) -> None:
        group, rep, seed = future_to_task[future]
        key = f"{group}:{rep}:{seed}"
        try:
            row = future.result()
            rows.append(row)
            with state_lock:
                event = f"done {group}-r{rep}-s{seed} rate={float(row['final_adoption_rate']):.3f}"
                recent_events.append(event)
                if len(recent_events) > 8:
                    del recent_events[:-8]
            _append_event(
                {
                    "event": "run_done",
                    "group": group,
                    "rep": rep,
                    "seed": seed,
                    "final_adoption_rate": round(float(row["final_adoption_rate"]), 6),
                    "t10_step": row["t10_step"],
                    "t50_step": row["t50_step"],
                    "auc_adoption": row["auc_adoption"],
                    "elapsed_seconds": round(float(row["elapsed_seconds"]), 3),
                }
            )
        except Exception as exc:
            with state_lock:
                current = task_states[key]
                current["status"] = "failed"
                current["error"] = str(exc)
                recent_events.append(f"failed {group}-r{rep}-s{seed} err={str(exc)[:90]}")
                if len(recent_events) > 8:
                    del recent_events[:-8]
            _append_event(
                {
                    "event": "run_failed",
                    "group": group,
                    "rep": rep,
                    "seed": seed,
                    "error": str(exc)[:240],
                }
            )
            failed.append(
                {
                    "group": group,
                    "rep": rep,
                    "seed": seed,
                    "error": str(exc),
                }
            )

    refresh_seconds = max(0.2, float(getattr(args, "ui_refresh_seconds", 1.0)))
    use_live_ui = RICH_AVAILABLE and sys.stdout.isatty()
    if not use_live_ui:
        reason = "rich 不可用" if not RICH_AVAILABLE else "终端非交互模式"
        print(f"[ui] 已切换为 quiet 进度模式: {reason}", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_task = {
            pool.submit(_run_task, group, rep, seed): (group, rep, seed)
            for group, rep, seed in tasks
        }
        if use_live_ui:
            with Live(
                _render_formal_batch_rich(
                    _make_snapshot(task_states),
                    list(args.groups),
                    len(tasks),
                    started_at,
                    list(recent_events),
                ),
                refresh_per_second=max(1, int(round(1.0 / refresh_seconds))),
                transient=False,
            ) as live:
                pending = set(future_to_task.keys())
                while pending:
                    done, pending = wait(
                        pending,
                        timeout=refresh_seconds,
                        return_when=FIRST_COMPLETED,
                    )
                    for future in done:
                        _consume_future_result(future, future_to_task)
                    with state_lock:
                        snapshot = _make_snapshot(task_states)
                        events_snapshot = list(recent_events)
                    live.update(
                        _render_formal_batch_rich(
                            snapshot,
                            list(args.groups),
                            len(tasks),
                            started_at,
                            events_snapshot,
                        )
                    )
                with state_lock:
                    snapshot = _make_snapshot(task_states)
                    events_snapshot = list(recent_events)
                live.update(
                    _render_formal_batch_rich(
                        snapshot,
                        list(args.groups),
                        len(tasks),
                        started_at,
                        events_snapshot,
                    )
                )
        else:
            last_completion = -1
            for future in as_completed(future_to_task):
                _consume_future_result(future, future_to_task)
                with state_lock:
                    snapshot = _make_snapshot(task_states)
                counts = _status_counts(snapshot)
                completion = counts["done"] + counts["failed"]
                if completion != last_completion:
                    print(
                        (
                            f"[progress] completed={completion}/{len(tasks)} "
                            f"done={counts['done']} failed={counts['failed']} "
                            f"running={counts['running']} queued={counts['queued']}"
                        ),
                        flush=True,
                    )
                    last_completion = completion

    rows.sort(key=lambda item: (str(item["group"]), int(item["rep"])))
    fieldnames = [
        "group",
        "rep",
        "seed",
        "n_agents",
        "n_steps",
        "model",
        "final_adoption_rate",
        "t10_step",
        "t50_step",
        "auc_adoption",
        "total_adopters",
        "model_calls",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "elapsed_seconds",
        "raw_file",
        "adoption_timeline_file",
        "metrics_file",
        "attempt",
    ]
    with summary_path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    usage_totals = {
        "model_calls": sum(int(row["model_calls"]) for row in rows),
        "prompt_tokens": sum(int(row["prompt_tokens"]) for row in rows),
        "completion_tokens": sum(int(row["completion_tokens"]) for row in rows),
        "total_tokens": sum(int(row["total_tokens"]) for row in rows),
    }
    elapsed_total = sum(float(row["elapsed_seconds"]) for row in rows)
    _append_event(
        {
            "event": "batch_done",
            "total_runs": len(tasks),
            "success_runs": len(rows),
            "failed_runs": len(failed),
            "elapsed_seconds_total": round(elapsed_total, 2),
            "summary_file": str(summary_path),
        }
    )
    return {
        "mode": "formal_batch",
        "groups": args.groups,
        "repetitions": args.repetitions,
        "seed_start": args.seed_start,
        "repetition_workers": workers,
        "total_runs": len(tasks),
        "success_runs": len(rows),
        "failed_runs": len(failed),
        "failures": failed,
        "summary_file": str(summary_path),
        "usage_totals": usage_totals,
        "elapsed_seconds_total": round(elapsed_total, 2),
        "event_log_file": str(event_log_path),
    }


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


def run_gateway_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    cfg = build_config(args.group, args.seed, args.n_agents, args.n_steps, args.timeout_seconds)
    client = DecisionClient(
        model=cfg.llm_model,
        base_url=cfg.llm_base_url,
        api_key_env=cfg.llm_api_key_env,
        temperature=cfg.llm_temperature,
        timeout_seconds=cfg.llm_timeout_seconds,
        gateway_url=cfg.llm_gateway_url,
        gateway_autostart=cfg.llm_gateway_autostart,
    )
    req = DecisionRequest(
        agent_id=1,
        openness=0.62,
        risk_tolerance=0.41,
        adopted_ratio=0.35,
        emotion_arousal=0.58,
        wom_strength="strong",
        wom_messages=["message a", "message b", "message c"],
        innovation_coef=0.01,
        imitation_coef=0.30,
    )
    sequential: list[dict[str, Any]] = []
    for i in range(args.calls):
        started = time.perf_counter()
        _ = client.decide(req, f"bench_seq_{i}")
        elapsed_ms = (time.perf_counter() - started) * 1000
        sequential.append({"index": i + 1, "elapsed_ms": round(elapsed_ms, 2)})

    tasks = [
        DecisionTask(
            req=DecisionRequest(
                agent_id=1000 + i,
                openness=0.62,
                risk_tolerance=0.41,
                adopted_ratio=0.35,
                emotion_arousal=0.58,
                wom_strength="strong",
                wom_messages=["message a", "message b", "message c"],
                innovation_coef=0.01,
                imitation_coef=0.30,
            ),
            context_key=f"bench_con_{i}",
        )
        for i in range(args.concurrency)
    ]
    started_concurrent = time.perf_counter()
    concurrent_results = client.decide_many(tasks, concurrency=args.concurrency)
    concurrent_elapsed_ms = (time.perf_counter() - started_concurrent) * 1000
    sequential_avg_ms = (
        sum(item["elapsed_ms"] for item in sequential) / len(sequential) if sequential else 0.0
    )
    return {
        "mode": "gateway_benchmark",
        "calls": args.calls,
        "concurrency": args.concurrency,
        "sequential_avg_ms": round(sequential_avg_ms, 2),
        "sequential_runs": sequential,
        "concurrent_total_ms": round(concurrent_elapsed_ms, 2),
        "concurrent_count": len(concurrent_results),
        "usage_totals": {
            "model_calls": client.model_calls,
            "prompt_tokens": client.prompt_tokens,
            "completion_tokens": client.completion_tokens,
            "total_tokens": client.total_tokens,
        },
    }


def run_concurrency_sweep(args: argparse.Namespace) -> dict[str, Any]:
    cfg = build_config(args.group, args.seed, args.n_agents, args.n_steps, args.timeout_seconds)
    client = DecisionClient(
        model=cfg.llm_model,
        base_url=cfg.llm_base_url,
        api_key_env=cfg.llm_api_key_env,
        temperature=cfg.llm_temperature,
        timeout_seconds=cfg.llm_timeout_seconds,
        gateway_url=cfg.llm_gateway_url,
        gateway_autostart=cfg.llm_gateway_autostart,
    )
    levels = list(range(args.concurrency_min, args.concurrency_max + 1, args.concurrency_step))
    rows: list[dict[str, Any]] = []
    stable_max = 0
    for concurrency in levels:
        task_count = concurrency * args.rounds_per_level
        started = time.perf_counter()
        success = 0
        failed = 0
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = []
            for i in range(task_count):
                req = DecisionRequest(
                    agent_id=10000 + concurrency * 100 + i,
                    openness=0.62,
                    risk_tolerance=0.41,
                    adopted_ratio=0.35,
                    emotion_arousal=0.58,
                    wom_strength="strong",
                    wom_messages=["message a", "message b", "message c"],
                    innovation_coef=0.01,
                    imitation_coef=0.30,
                )
                futures.append(pool.submit(client.decide, req, f"sweep_c{concurrency}_{i}"))
            for future in as_completed(futures):
                try:
                    _ = future.result()
                    success += 1
                except Exception as exc:
                    failed += 1
                    if len(errors) < 5:
                        errors.append(str(exc))
        elapsed_ms = (time.perf_counter() - started) * 1000
        row = {
            "concurrency": concurrency,
            "task_count": task_count,
            "success": success,
            "failed": failed,
            "elapsed_ms": round(elapsed_ms, 2),
            "avg_ms_per_task": round(elapsed_ms / task_count, 2) if task_count > 0 else 0.0,
            "sample_errors": errors,
        }
        rows.append(row)
        if failed == 0:
            stable_max = concurrency
    return {
        "mode": "concurrency_sweep",
        "group": args.group,
        "rounds_per_level": args.rounds_per_level,
        "concurrency_min": args.concurrency_min,
        "concurrency_max": args.concurrency_max,
        "concurrency_step": args.concurrency_step,
        "stable_max_no_failure": stable_max,
        "levels": rows,
        "usage_totals": {
            "model_calls": client.model_calls,
            "prompt_tokens": client.prompt_tokens,
            "completion_tokens": client.completion_tokens,
            "total_tokens": client.total_tokens,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=[
            "smoke",
            "calibration",
            "gateway_benchmark",
            "concurrency_sweep",
            "formal_batch",
        ],
        required=True,
    )
    parser.add_argument("--group", default="A")
    parser.add_argument("--groups", nargs="+", default=["A", "B", "C", "D"])
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--seed-start", type=int, default=201)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--n-agents", type=int, default=None)
    parser.add_argument("--n-steps", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--log-interval", type=int, default=5)
    parser.add_argument("--calls", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--concurrency-min", type=int, default=5)
    parser.add_argument("--concurrency-max", type=int, default=40)
    parser.add_argument("--concurrency-step", type=int, default=5)
    parser.add_argument("--rounds-per-level", type=int, default=2)
    parser.add_argument("--repetition-workers", type=int, default=1)
    parser.add_argument("--run-retries", type=int, default=1)
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--ui-refresh-seconds", type=float, default=1.0)
    parser.add_argument("--output-dir", default="data/results")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--summary-file", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv_if_exists(project_root)
    if args.mode == "smoke":
        output = run_smoke(args)
    elif args.mode == "calibration":
        output = run_calibration(args)
    elif args.mode == "gateway_benchmark":
        output = run_gateway_benchmark(args)
    elif args.mode == "formal_batch":
        output = run_formal_batch(args)
    else:
        output = run_concurrency_sweep(args)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
