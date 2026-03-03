from tqdm import tqdm
import copy
from .utils import stratified_random_queries

def distribute_betweenness_to_multiedges(G, betweenness, ch_weight):
    if not G.is_multigraph():
        return betweenness

    edge_bc = {}
    for (u, v), bc in betweenness.items():
        target_wt = ch_weight[u][v]
        
        keys = []
        for k, data in G[u][v].items():
            wt = data.get("length", 1)
            if abs(wt - target_wt) < 1e-4:
                keys.append(k)
        if not keys:
            continue

        bc_per_key = bc / len(keys)
        for k in keys:
            edge_bc[(u, v, k)] = bc_per_key

    return edge_bc

def rescale_edge_betweenness(betweenness, n, k=None, normalized=True, directed=False):
    if normalized:
        if n <= 1:
            scale = None
        else:
            scale = 1.0 / (n * (n - 1))
    else:
        scale = 1.0
        if not directed:
            scale *= 0.5

    if k is not None and k < n:
        scale *= n / k

    if scale is not None:
        for e in betweenness:
            betweenness[e] *= scale
    return betweenness
    
def accumulate_betweenness_edges(betweenness, sto_processnode, predes, cnt_shortest_path, ch, source):
    delta = dict.fromkeys(sto_processnode, 0)
    while sto_processnode:
        u = sto_processnode.pop()
        coeff = (1 + delta[u]) / cnt_shortest_path[u]
        if u == source:
            break
        for v in predes[u]:
            c = cnt_shortest_path[v] * coeff
            edges = [v] + ch.get_shortcut(v, u) + [u]
            for i in range(len(edges) - 1, 0, -1):
                if edges[i - 1] in delta:
                    delta[edges[i - 1]] += c
                betweenness[(edges[i - 1], edges[i])] += c
    return betweenness
    
def edge_betweenness_centrality(ori_graph, ch, benchmark = None, k=10000):
    if benchmark == None:
        benchmark = stratified_random_queries(ori_graph, k, target_gen=False, bootstrapping=False)

    betweenness = dict.fromkeys(ori_graph.edges(), 0.0)
    sto_shortcut = copy.deepcopy(ch.shortcut)

    for x in tqdm(benchmark):
        u = x
        res = ch.bidirectional_dijkstra(u)
        cnt_shortest_path_source = res['cnt_shortest_path_source']
        sto_processnode_source = res['sto_processnode_source']
        predes_source = res['predes_source']
        
        betweenness = accumulate_betweenness_edges(betweenness, 
                                                sto_processnode_source, 
                                                predes_source, 
                                                cnt_shortest_path_source,
                                                ch,
                                                u)
    betweenness = rescale_edge_betweenness(betweenness,
                                        n=ori_graph.number_of_nodes(),
                                        k=len(benchmark), normalized=True,
                                        directed=ori_graph.is_directed())
    if ori_graph.is_multigraph():
        betweenness = distribute_betweenness_to_multiedges(ori_graph, betweenness, ch.weight)

    return betweenness