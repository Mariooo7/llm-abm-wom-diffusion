import networkx as nx


def generate_network(
    network_type: str,
    n_nodes: int,
    avg_degree: int,
    rewiring_prob: float = 0.1,
    seed: int | None = None,
) -> nx.Graph:
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
