import networkx as nx
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import random

# 设置输出路径
FIGURES_DIR = Path("analysis/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# 统一参数设定 (和我们仿真实验一致)
N_NODES = 100
AVG_DEGREE = 6
REWIRING_PROB = 0.1  # 小世界网络重连概率

def plot_network_comparison():
    print("正在绘制网络拓扑对比图...")
    
    # 设置随机种子保证每次画出来的图长得一样
    random.seed(42)
    
    # 1. 生成小世界网络 (Watts-Strogatz)
    # k 是每个节点连接的邻居数，要求是偶数，AVG_DEGREE = 6
    G_sw = nx.watts_strogatz_graph(n=N_NODES, k=AVG_DEGREE, p=REWIRING_PROB, seed=42)
    
    # 2. 生成随机网络 (Erdős-Rényi)
    # 平均度 = p * (N - 1) => p = AVG_DEGREE / (N_NODES - 1)
    p_er = AVG_DEGREE / (N_NODES - 1)
    G_rn = nx.erdos_renyi_graph(n=N_NODES, p=p_er, seed=42)
    
    # 创建画布 (1行2列)
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    
    # 统一点的颜色和大小
    node_color = '#4A90E2'
    edge_color = '#CCCCCC'
    node_size = 50
    alpha = 0.6
    
    # ==== 绘制小世界网络 ====
    # 使用 spring_layout 或者 circular_layout
    # 对于小世界，circular_layout 能很好展示出“局部抱团 + 少量跨圈连线”的特征
    pos_sw = nx.circular_layout(G_sw)
    
    nx.draw_networkx_nodes(G_sw, pos_sw, ax=axes[0], node_size=node_size, node_color=node_color, alpha=0.8)
    nx.draw_networkx_edges(G_sw, pos_sw, ax=axes[0], alpha=alpha, edge_color=edge_color)
    
    # 计算一些网络指标展示在图上
    sw_clustering = nx.average_clustering(G_sw)
    sw_path_length = nx.average_shortest_path_length(G_sw)
    axes[0].set_title("Small-World Network\n(High Clustering, Short Paths)", fontsize=16, fontweight='bold', pad=15)
    axes[0].text(0.5, -1.1, f"Avg Degree: {AVG_DEGREE}\nClustering Coef: {sw_clustering:.3f}\nAvg Path Length: {sw_path_length:.2f}", 
                 ha='center', fontsize=12, bbox=dict(facecolor='white', alpha=0.5, edgecolor='none'))
    axes[0].axis('off')
    
    # ==== 绘制随机网络 ====
    # 随机网络使用 spring_layout 能展示其长程连接杂乱的特征
    pos_rn = nx.spring_layout(G_rn, seed=42)
    
    nx.draw_networkx_nodes(G_rn, pos_rn, ax=axes[1], node_size=node_size, node_color=node_color, alpha=0.8)
    nx.draw_networkx_edges(G_rn, pos_rn, ax=axes[1], alpha=alpha, edge_color=edge_color)
    
    # 如果 ER 网络不连通，计算最短路径会报错，我们需要取最大连通子图
    if nx.is_connected(G_rn):
        rn_path_length = nx.average_shortest_path_length(G_rn)
    else:
        largest_cc = max(nx.connected_components(G_rn), key=len)
        subgraph = G_rn.subgraph(largest_cc)
        rn_path_length = nx.average_shortest_path_length(subgraph)
        
    rn_clustering = nx.average_clustering(G_rn)
    axes[1].set_title("Random Network\n(Low Clustering, Short Paths)", fontsize=16, fontweight='bold', pad=15)
    axes[1].text(0.5, -1.1, f"Avg Degree: {AVG_DEGREE}\nClustering Coef: {rn_clustering:.3f}\nAvg Path Length: {rn_path_length:.2f}", 
                 ha='center', fontsize=12, bbox=dict(facecolor='white', alpha=0.5, edgecolor='none'))
    axes[1].axis('off')
    
    # 保存图片
    out_path = FIGURES_DIR / 'fig3_network_topology_comparison.png'
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ 网络拓扑图已保存: {out_path}")

def main():
    plot_network_comparison()

if __name__ == "__main__":
    main()
