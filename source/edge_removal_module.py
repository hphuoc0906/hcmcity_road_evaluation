from collections import defaultdict
import copy
from tqdm import tqdm
from contraction_hierarchies import ContractionHierarchies
from .utils import stratified_random_queries

def edge_removal_simulator_ver2(ori_graph, betweenness_df, topk=10):
    G = copy.deepcopy(ori_graph)
    df = betweenness_df.sort_values(by='betweenness', ascending=False)
    node_to_edges = defaultdict(list)
    edge_map = []
    queue = []
    delete_edge = []
    

    cnt = 0
    for _, row in df.iterrows():
        u, v, key, b = row['u'], row['v'], row['key'], row['betweenness']
        edge_map.append((int(u), int(v), key, b))
        node_to_edges[u].append(cnt)
        node_to_edges[v].append(cnt)
        cnt += 1
    remove_edge = [False] * len(edge_map)
    visited = [False] * len(edge_map)

    def dfs(node, bet):
        for idx in node_to_edges[node]:
            if remove_edge[idx] == True or visited[idx] == True:
                continue
            visited[idx] = True
            edge = edge_map[idx]
            queue.append(idx)
            v = edge[0] + edge[1] - node
            w = edge[3]
            if abs(bet - w) < 1e-6:
                remove_edge[idx] = True
                delete_edge.append(idx)
                dfs(v, w)

    sto_delete_edge = None
    now_idx = 0
    top_cur = 0
    last_shortest_length = None
    delta_cost = None
    pbar = tqdm(total=topk, desc="Edge removals", position=0)
    benchmark = stratified_random_queries(G, k=1000)
    old_dist = None
    dist = {}
    log_file = []
    d_edge = None

    ch = ContractionHierarchies(G)
    ch.build_contraction_hierarchy()

    shortest_length = 0
    for u, v in tqdm(benchmark, desc="Querying", position=1, leave=False):
        answer = ch.bidirectional_dijkstra(u, v)
        sl = answer['path_length']
        shortest_length += sl
        dist[(u, v)] = sl
    last_shortest_length = shortest_length

    del ch

    sto_delete_edge = None
    begin_edge = None
    sto_data_delete_edge = None
    while top_cur < topk:
        top_cur += 1
        pbar.update(1)
        for i in range(now_idx, len(edge_map)):
            now_idx += 1
            if remove_edge[i] == True:
                continue
            id_edge = i
            bet = edge_map[i][3]
            begin_edge = edge_map[i]
            dfs(edge_map[i][0], bet)
            sto_delete_edge = []
            sto_data_delete_edge = []
            while delete_edge:
                u, v, key, betw = edge_map[delete_edge.pop()]
                if G.has_edge(u, v, key):
                    edge_data = G[u][v][key].copy()
                    sto_data_delete_edge.append((u, v, key, edge_data))
                    G.remove_edge(u, v, key)
                    sto_delete_edge.append((u, v, key))
            while queue:
                idx = queue.pop()
                visited[idx] = False
            break
            
        ch = ContractionHierarchies(G)
        ch.build_contraction_hierarchy()
        
        shortest_length = 0
        for u, v in tqdm(benchmark, desc="Querying", position=1, leave=False):
            answer = ch.bidirectional_dijkstra(u, v)
            sl = answer['path_length']
            shortest_length += sl
            dist[(u, v)] = sl
            
        
        delta_cost = shortest_length - last_shortest_length
        if delta_cost < 0:
            for u, v in benchmark:
                if old_dist[(u, v)] > dist[(u, v)]:
                    print(u, v)
        print(f"Delta cost after delete top{top_cur}:", delta_cost)
        log_file.append({"id_edge": id_edge,
                        "start_edge": begin_edge,
                        "delete_edges": sto_delete_edge,
                        "last_shortest_path": last_shortest_length,
                        "shortest_length": shortest_length,
                        "delta_cost": delta_cost})
        last_shortest_length = shortest_length
        old_dist = copy.deepcopy(dist)

        del ch

        for u, v, key, edge_data in sto_data_delete_edge:
            if not G.has_edge(u, v, key):
                G.add_edge(u, v, **edge_data)
        sto_data_delete_edge = []
        
    pbar.close()
    return log_file

def edge_removal_simulator(ori_graph, betweenness_df, topk=10):
    G = copy.deepcopy(ori_graph)
    df = betweenness_df.sort_values(by='betweenness', ascending=False)
    node_to_edges = defaultdict(list)
    edge_map = []
    queue = []
    delete_edge = []
    

    cnt = 0
    for _, row in df.iterrows():
        u, v, key, b = row['u'], row['v'], row['key'], row['betweenness']
        edge_map.append((int(u), int(v), key, b))
        node_to_edges[u].append(cnt)
        node_to_edges[v].append(cnt)
        cnt += 1
    remove_edge = [False] * len(edge_map)
    visited = [False] * len(edge_map)

    def dfs(node, bet):
        for idx in node_to_edges[node]:
            if remove_edge[idx] == True or visited[idx] == True:
                continue
            visited[idx] = True
            edge = edge_map[idx]
            queue.append(idx)
            v = edge[0] + edge[1] - node
            w = edge[3]
            if abs(bet - w) < 1e-6:
                remove_edge[idx] = True
                delete_edge.append(idx)
                dfs(v, w)

    sto_delete_edge = None
    now_idx = 0
    top_cur = 0
    last_shortest_length = None
    delta_cost = None
    pbar = tqdm(total=topk, desc="Edge removals", position=0)
    benchmark = stratified_random_queries(G, k=1000)
    old_dist = None
    dist = {}
    log_file = []
    d_edge = None

    ch = ContractionHierarchies(G)
    ch.build_contraction_hierarchy()

    shortest_length = 0
    for u, v in tqdm(benchmark, desc="Querying", position=1, leave=False):
        answer = ch.bidirectional_dijkstra(u, v)
        sl = answer['path_length']
        shortest_length += sl
        dist[(u, v)] = sl
    last_shortest_length = shortest_length

    del ch

    sto_delete_edge = None
    begin_edge = None
    while top_cur < topk:
        top_cur += 1
        pbar.update(1)
        for i in range(now_idx, len(edge_map)):
            now_idx += 1
            if remove_edge[i] == True:
                continue
            id_edge = i
            bet = edge_map[i][3]
            begin_edge = edge_map[i]
            dfs(edge_map[i][0], bet)
            sto_delete_edge = []
            while delete_edge:
                u, v, key, betw = edge_map[delete_edge.pop()]
                if G.has_edge(u, v, key):
                    G.remove_edge(u, v, key)
                sto_delete_edge.append((u, v, key))
            while queue:
                idx = queue.pop()
                visited[idx] = False
            break
            
        ch = ContractionHierarchies(G)
        ch.build_contraction_hierarchy()
        
        shortest_length = 0
        for u, v in tqdm(benchmark, desc="Querying", position=1, leave=False):
            answer = ch.bidirectional_dijkstra(u, v)
            sl = answer['path_length']
            shortest_length += sl
            dist[(u, v)] = sl
            
        
        delta_cost = shortest_length - last_shortest_length
        if delta_cost < 0:
            for u, v in benchmark:
                if old_dist[(u, v)] > dist[(u, v)]:
                    print(u, v)
        print(f"Delta cost after delete top{top_cur}:", delta_cost)
        log_file.append({"id_edge": id_edge,
                        "start_edge": begin_edge,
                        "delete_edges": sto_delete_edge,
                        "last_shortest_path": last_shortest_length,
                        "shortest_length": shortest_length,
                        "delta_cost": delta_cost})
        last_shortest_length = shortest_length
        old_dist = copy.deepcopy(dist)

        del ch
    pbar.close()
    return log_file