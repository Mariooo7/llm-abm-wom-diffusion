import networkx as nx


def generate_network(
    network_type: str,
    n_nodes: int,
    avg_degree: int,
    rewiring_prob: float = 0.1,
    seed: int | None = None,
) -> nx.Graph:
    """
    生成扩散网络。

    研究侧关心的是“每个个体能接触到多少邻居”以及“信息是否会通过桥接边跨群体扩散”，因此只保留两类可控结构：
    - small_world：局部聚类 + 少量重连，既能刻画朋友圈结构，也便于控制跨圈传播。
    - random：不强调局部结构，用平均度近似控制接触机会，用作对照。

    avg_degree 表示期望平均度（small_world 的 k，random 会转换为边概率 p）。
    """
    if network_type == "small_world":
        return nx.watts_strogatz_graph(
            n=n_nodes,
            k=avg_degree,
            p=rewiring_prob,
            seed=seed,
        )
    if network_type == "random":
        p = avg_degree / max(1, n_nodes - 1)
        return nx.erdos_renyi_graph(
            n=n_nodes,
            p=p,
            seed=seed,
        )
    raise ValueError(f"Unsupported network type: {network_type}")


def compute_network_metrics(graph: nx.Graph) -> dict[str, float]:
    """
    计算用于记录与复现的网络指标。

    - density：整体连边密度，和平均度高度相关，用于快速核对配置是否生效。
    - avg_clustering：局部聚类系数，反映“朋友圈闭环”程度。
    - avg_path_length：平均最短路径长度，近似反映跨圈传播的阻力。

    非连通图时只在最大连通分量上计算路径长度，避免指标被孤立点拉到无穷大。
    """
    if graph.number_of_nodes() == 0:
        return {
            "density": 0.0,
            "avg_clustering": 0.0,
            "avg_path_length": 0.0,
        }
    if nx.is_connected(graph):
        avg_path_length = nx.average_shortest_path_length(graph)
    else:
        largest_cc = max(nx.connected_components(graph), key=len)
        subgraph = graph.subgraph(largest_cc)
        avg_path_length = (
            nx.average_shortest_path_length(subgraph) if subgraph.number_of_nodes() > 1 else 0.0
        )
    return {
        "density": nx.density(graph),
        "avg_clustering": nx.average_clustering(graph),
        "avg_path_length": float(avg_path_length),
    }
