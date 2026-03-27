import random

import matplotlib.pyplot as plt
import networkx as nx
from plot_config import configure_matplotlib, figure_path

configure_matplotlib()

# 统一参数设定 (和我们仿真实验一致)
N_NODES = 100
AVG_DEGREE = 6
REWIRING_PROB = 0.1  # 小世界网络重连概率


def plot_network_comparison():
    print("正在绘制网络拓扑对比图...")
    random.seed(42)

    graph_sw = nx.watts_strogatz_graph(
        n=N_NODES, k=AVG_DEGREE, p=REWIRING_PROB, seed=42
    )
    p_er = AVG_DEGREE / (N_NODES - 1)
    graph_rn = nx.erdos_renyi_graph(n=N_NODES, p=p_er, seed=42)

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    node_color = "#4A90E2"
    edge_color = "#CCCCCC"
    node_size = 50
    alpha = 0.6

    pos_sw = nx.circular_layout(graph_sw)
    nx.draw_networkx_nodes(
        graph_sw,
        pos_sw,
        ax=axes[0],
        node_size=node_size,
        node_color=node_color,
        alpha=0.8,
    )
    nx.draw_networkx_edges(
        graph_sw, pos_sw, ax=axes[0], alpha=alpha, edge_color=edge_color
    )

    sw_clustering = nx.average_clustering(graph_sw)
    sw_path_length = nx.average_shortest_path_length(graph_sw)
    axes[0].set_title(
        "Small-World Network\n(High Clustering, Short Paths)",
        fontsize=16,
        fontweight="bold",
        pad=15,
    )
    axes[0].text(
        0.5,
        -1.1,
        f"Avg Degree: {AVG_DEGREE}\n"
        f"Clustering Coef: {sw_clustering:.3f}\n"
        f"Avg Path Length: {sw_path_length:.2f}",
        ha="center",
        fontsize=12,
        bbox={"facecolor": "white", "alpha": 0.5, "edgecolor": "none"},
    )
    axes[0].axis("off")

    pos_rn = nx.spring_layout(graph_rn, seed=42)
    nx.draw_networkx_nodes(
        graph_rn,
        pos_rn,
        ax=axes[1],
        node_size=node_size,
        node_color=node_color,
        alpha=0.8,
    )
    nx.draw_networkx_edges(
        graph_rn, pos_rn, ax=axes[1], alpha=alpha, edge_color=edge_color
    )

    if nx.is_connected(graph_rn):
        rn_path_length = nx.average_shortest_path_length(graph_rn)
    else:
        largest_cc = max(nx.connected_components(graph_rn), key=len)
        subgraph = graph_rn.subgraph(largest_cc)
        rn_path_length = nx.average_shortest_path_length(subgraph)

    rn_clustering = nx.average_clustering(graph_rn)
    axes[1].set_title(
        "Random Network\n(Low Clustering, Short Paths)",
        fontsize=16,
        fontweight="bold",
        pad=15,
    )
    axes[1].text(
        0.5,
        -1.1,
        f"Avg Degree: {AVG_DEGREE}\n"
        f"Clustering Coef: {rn_clustering:.3f}\n"
        f"Avg Path Length: {rn_path_length:.2f}",
        ha="center",
        fontsize=12,
        bbox={"facecolor": "white", "alpha": 0.5, "edgecolor": "none"},
    )
    axes[1].axis("off")

    out_path = figure_path("fig3_network_topology_comparison")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

    print(f"✅ 网络拓扑图已保存: {out_path}")


def main():
    plot_network_comparison()

if __name__ == "__main__":
    main()
