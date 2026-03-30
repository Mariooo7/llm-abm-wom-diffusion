from pathlib import Path

import pandas as pd

DATA_DIR = Path("data/raw/formal_20260319_174207")
OUTPUT_DIR = Path("analysis/tables")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = ""
    for ch in text:
        out += replacements.get(ch, ch)
    return out


def _load_group_frames() -> dict[str, pd.DataFrame]:
    frames: dict[str, list[pd.DataFrame]] = {"A": [], "B": [], "C": [], "D": []}
    for csv_path in sorted(DATA_DIR.glob("simulation_*.csv")):
        name = csv_path.name
        parts = name.split("_")
        if len(parts) < 3:
            continue
        group = parts[1].strip()
        if group not in frames:
            continue
        df = pd.read_csv(csv_path)
        df["group"] = group
        frames[group].append(df)
    return {g: pd.concat(lst, ignore_index=True) for g, lst in frames.items() if lst}


def sample_reasonings_per_group(
    group_df: pd.DataFrame,
    seed: int,
    per_group_samples: int = 8,
) -> pd.DataFrame:
    df = group_df.copy()

    keep_cols = [
        "group",
        "step",
        "agent_id",
        "openness",
        "risk_tolerance",
        "adopted_ratio",
        "wom_count",
        "probability",
        "adopt_final",
        "reasoning",
        "source",
    ]
    df = df[[c for c in keep_cols if c in df.columns]]
    df = df.dropna(subset=["reasoning"])
    df["reasoning"] = df["reasoning"].astype(str).str.strip()
    df = df[df["reasoning"] != ""]

    if df.empty:
        return pd.DataFrame(columns=keep_cols)

    adopters = df[df["adopt_final"]]
    non_adopters = df[~df["adopt_final"]]

    half = per_group_samples // 2
    n_adopt = min(len(adopters), half)
    n_non = min(len(non_adopters), per_group_samples - n_adopt)

    sampled = []
    if n_adopt > 0:
        sampled.append(adopters.sample(n=n_adopt, random_state=int(seed)))
    if n_non > 0:
        sampled.append(non_adopters.sample(n=n_non, random_state=int(seed) + 1))

    if not sampled:
        return pd.DataFrame(columns=keep_cols)

    out = pd.concat(sampled, ignore_index=True)
    out = out.sample(frac=1.0, random_state=int(seed) + 2).reset_index(drop=True)

    for col in ["openness", "risk_tolerance", "adopted_ratio", "probability"]:
        if col in out.columns:
            out[col] = out[col].astype(float).round(3)
    if "wom_count" in out.columns:
        out["wom_count"] = out["wom_count"].astype(int)
    if "step" in out.columns:
        out["step"] = out["step"].astype(int)
    if "agent_id" in out.columns:
        out["agent_id"] = out["agent_id"].astype(int)
    if "adopt_final" in out.columns:
        out["adopt_final"] = out["adopt_final"].astype(bool)

    return out


def write_reasoning_table_tex(
    df: pd.DataFrame, out_path: Path
) -> None:
    cols = [
        "group",
        "step",
        "agent_id",
        "adopted_ratio",
        "wom_count",
        "probability",
        "adopt_final",
        "reasoning",
    ]
    present = [c for c in cols if c in df.columns]
    df = df[present].copy()
    df["reasoning"] = df["reasoning"].astype(str)

    lines: list[str] = []
    lines.append(r"\setlength{\tabcolsep}{4pt}")
    lines.append(
        r"\begin{longtable}{P{0.05\textwidth}P{0.05\textwidth}P{0.07\textwidth}"
        r"P{0.08\textwidth}P{0.06\textwidth}P{0.06\textwidth}P{0.06\textwidth}"
        r"P{0.45\textwidth}}"
    )
    lines.append(
        r"\caption{LLMs 决策 reasoning 抽样（每组 8 条，固定随机种子）}"
        r"\label{tab:reasoning_samples}\\"
    )
    lines.append(r"\toprule")
    lines.append(r"组别 & Step & Agent & 占比 & 条数 & 概率 & 采纳 & 完整决策推演过程（Reasoning） \\")
    lines.append(r"\midrule")
    lines.append(r"\endfirsthead")
    lines.append(r"\toprule")
    lines.append(r"组别 & Step & Agent & 占比 & 条数 & 概率 & 采纳 & 完整决策推演过程（Reasoning） \\")
    lines.append(r"\midrule")
    lines.append(r"\endhead")
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{8}{r}{\textit{续下页}} \\")
    lines.append(r"\endfoot")
    lines.append(r"\bottomrule")
    lines.append(r"\endlastfoot")
    for _, row in df.iterrows():
        group = _latex_escape(str(row.get("group", "")))
        step = str(row.get("step", ""))
        agent = str(row.get("agent_id", ""))
        adopted_ratio = str(row.get("adopted_ratio", ""))
        wom_count = str(row.get("wom_count", ""))
        prob = str(row.get("probability", ""))
        adopt = "T" if bool(row.get("adopt_final", False)) else "F"
        reasoning = _latex_escape(str(row.get("reasoning", "")))
        line = (
            f"{group} & {step} & {agent} & {adopted_ratio} & "
            f"{wom_count} & {prob} & {adopt} & {reasoning} \\\\"
        )
        lines.append(line)
    lines.append(r"\end{longtable}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Raw simulation directory not found: {DATA_DIR}")

    print(f"Loading raw decision traces from: {DATA_DIR}")
    groups = _load_group_frames()
    if not groups:
        raise RuntimeError(f"No simulation_*.csv files found under: {DATA_DIR}")

    all_samples = []
    base_seed = 20260323
    for group, df in groups.items():
        sampled = sample_reasonings_per_group(
            group_df=df,
            seed=base_seed + ord(group),
            per_group_samples=8,
        )
        all_samples.append(sampled)
        print(f"Group {group}: sampled {len(sampled)} reasoning records")

    out_df = pd.concat(all_samples, ignore_index=True)
    out_csv = OUTPUT_DIR / "table2_reasoning_samples_full.csv"
    out_df.to_csv(out_csv, index=False)
    print(f"Saved full reasoning samples CSV: {out_csv}")

    out_tex = OUTPUT_DIR / "table2_reasoning_samples.tex"
    write_reasoning_table_tex(out_df, out_tex)
    print(f"Saved LaTeX tabularx snippet: {out_tex}")


if __name__ == "__main__":
    main()
