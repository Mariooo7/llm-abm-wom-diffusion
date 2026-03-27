from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from plot_config import configure_matplotlib, figure_path

configure_matplotlib()

# 数据路径
DATA_DIR = Path("data/raw/formal_20260319_174207")
B1_FILE = DATA_DIR / "simulation_B_1.csv"
D1_FILE = DATA_DIR / "simulation_D_1.csv"

# 网络参数 (从配置文件可知)
N_NODES = 100
AVG_DEGREE = 6
REWIRING_PROB = 0.1
SEED = 12001  # 从 metrics_B_1.json 读取的种子


def get_adopters(csv_file: Path, n_nodes: int = 100) -> set:
    """解析仿真原始日志，找出所有最终采纳者的ID"""
    df = pd.read_csv(csv_file)

    # 1. 找出在 step 0 被评估的 agent (说明他们不是初始 seed)
    step_0_agents = set(df[df["step"] == 0]["agent_id"].unique())
    all_agents = set(range(n_nodes))

    # 初始火种 = 所有 agent 减去 step 0 还没采纳的 agent
    initial_seeds = all_agents - step_0_agents

    # 2. 找出在仿真过程中发生采纳的 agent (adopt_final == True)
    adopted_during_sim = set(df[df["adopt_final"]]["agent_id"].unique())

    # 返回所有采纳者
    return initial_seeds.union(adopted_during_sim)


def plot_micro_mechanism():
    print("正在提取采纳者状态...")
    adopters_b = get_adopters(B1_FILE, N_NODES)
    adopters_d = get_adopters(D1_FILE, N_NODES)

    print(f"Group B (小世界+弱产品) 最终采纳人数: {len(adopters_b)}")
    print(f"Group D (随机网络+弱产品) 最终采纳人数: {len(adopters_d)}")

    print("正在重建网络拓扑...")
    graph_sw = nx.watts_strogatz_graph(
        n=N_NODES, k=AVG_DEGREE, p=REWIRING_PROB, seed=SEED
    )
    p_er = AVG_DEGREE / (N_NODES - 1)
    graph_rn = nx.erdos_renyi_graph(n=N_NODES, p=p_er, seed=SEED)

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    color_adopter = "#E74C3C"
    color_non_adopter = "#BDC3C7"

    pos_sw = nx.spring_layout(graph_sw, seed=42)
    node_colors_b = [
        color_adopter if node in adopters_b else color_non_adopter
        for node in graph_sw.nodes()
    ]
    nx.draw_networkx_nodes(
        graph_sw,
        pos_sw,
        ax=axes[0],
        node_size=60,
        node_color=node_colors_b,
        alpha=0.9,
    )
    edges_sw_adopters = [
        (u, v) for u, v in graph_sw.edges() if u in adopters_b and v in adopters_b
    ]
    edges_sw_others = [
        (u, v) for u, v in graph_sw.edges() if not (u in adopters_b and v in adopters_b)
    ]
    nx.draw_networkx_edges(
        graph_sw,
        pos_sw,
        ax=axes[0],
        edgelist=edges_sw_others,
        alpha=0.2,
        edge_color="#999999",
    )
    nx.draw_networkx_edges(
        graph_sw,
        pos_sw,
        ax=axes[0],
        edgelist=edges_sw_adopters,
        alpha=0.8,
        edge_color=color_adopter,
        width=2,
    )
    axes[0].set_title(
        f"Small-World Network (Group B)\nAdopters: {len(adopters_b)}",
        fontsize=16,
        pad=15,
    )
    axes[0].text(
        0.5,
        -0.1,
        "Weak products get trapped in local clusters.\n"
        "Without strong WOM, diffusion stops easily.",
        ha="center",
        va="top",
        transform=axes[0].transAxes,
        fontsize=12,
        style="italic",
    )
    axes[0].axis("off")

    pos_rn = nx.spring_layout(graph_rn, seed=42)
    node_colors_d = [
        color_adopter if node in adopters_d else color_non_adopter
        for node in graph_rn.nodes()
    ]
    nx.draw_networkx_nodes(
        graph_rn,
        pos_rn,
        ax=axes[1],
        node_size=60,
        node_color=node_colors_d,
        alpha=0.9,
    )
    edges_rn_adopters = [
        (u, v) for u, v in graph_rn.edges() if u in adopters_d and v in adopters_d
    ]
    edges_rn_others = [
        (u, v) for u, v in graph_rn.edges() if not (u in adopters_d and v in adopters_d)
    ]
    nx.draw_networkx_edges(
        graph_rn,
        pos_rn,
        ax=axes[1],
        edgelist=edges_rn_others,
        alpha=0.2,
        edge_color="#999999",
    )
    nx.draw_networkx_edges(
        graph_rn,
        pos_rn,
        ax=axes[1],
        edgelist=edges_rn_adopters,
        alpha=0.8,
        edge_color=color_adopter,
        width=2,
    )
    axes[1].set_title(
        f"Random Network (Group D)\nAdopters: {len(adopters_d)}",
        fontsize=16,
        pad=15,
    )
    axes[1].text(
        0.5,
        -0.1,
        "Long-range bridges help weak products jump across the network,\n"
        "finding susceptible nodes even with weak WOM.",
        ha="center",
        va="top",
        transform=axes[1].transAxes,
        fontsize=12,
        style="italic",
    )
    axes[1].axis("off")

    out_path = figure_path("fig5_micro_mechanism")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

    print(f"✅ 微观机制对比图已保存: {out_path}")

if __name__ == "__main__":
    plot_micro_mechanism()
