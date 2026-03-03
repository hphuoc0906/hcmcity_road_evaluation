import time
import networkx as nx
import math
import numpy as np
from tqdm import tqdm
import json
import datetime
import random
import requests
from collections import Counter

def haversine_distances(G, u, v):
    lat1 = math.radians(G.nodes[u]['y'])
    lon1 = math.radians(G.nodes[u]['x'])
    lat2 = math.radians(G.nodes[v]['y'])
    lon2 = math.radians(G.nodes[v]['x'])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371000 * c

def shortest_path_alogrithm(G, source, target, algo='dijkstra', heuristic='haversine'):
    t0, t1 = None, None
    if algo == 'dijkstra':
        t0 = time.time()
        path = nx.dijkstra_path(G, source, target, weight='length')
        t1 = time.time()
    elif algo == 'astar':
        if heuristic == 'haversine':
            heuristic = haversine_distances
        t0 = time.time()
        path = nx.astar_path(G, source, target, heuristic=lambda u, v: heuristic(G, u, v), weight='length')
        t1 = time.time()
    else:
        raise Exception("No algo in database")
    
    return {
        "algorithm": algo,
        "source": source,
        "target": target,
        "latency_s": round((t1 - t0), 4),
        "path_length": nx.path_weight(G, path, weight='length'),
        "path_nodes": path
    }

def calculate_avg_time(results):
    deg_level = 3
    total = 1000
    k = total // deg_level
    sto = {}
    for i in range(deg_level):
        start = k*i
        end = k*(i+1)
        if i == deg_level - 1:
            end = total
            
        latencies = [entry["latency_s"] for entry in results[start:end]]
        sto['deg_' + str(i + 1)] =  round(np.sum(latencies) / len(latencies), 6)
        
    latencies = [entry["latency_s"] for entry in results]
    sto['overall'] =  round(np.sum(latencies) / len(latencies), 6)
    return sto

def check_valid_path(ori_graph, path):
    check_path = True
    for i in range(len(path) - 1):
        if ori_graph.has_edge(path[i], path[i + 1]) == False:
            print(path[i], path[i + 1])
            check_path = False
    return check_path
    
def evaluate_contraction_hierachies(benchmark, ori_graph, ch):
    log = []
    for u, v in tqdm(benchmark):
        res = ch.bidirectional_dijkstra(u, v)
        filtered_res = {
            'source': res['source'],
            'target': res['target'],
            'latency_s': res['latency_s'],
            'path_length': res['path_length'],
            'path_nodes': res['path_nodes']
        }
        log.append(filtered_res)
        check_valid = check_valid_path(ori_graph, filtered_res["path_nodes"])
        if check_valid == False:
            break
    
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  
    output_file = "CH_" + now + ".json"
    with open(output_file, 'w') as f:
        json.dump(log, f, indent=4)

def run_shortest_path_benchmark(G, benchmark, algo='dijkstra', heuristic='haversine'):
    log = []
    for u, v in tqdm(benchmark):
        log.append(shortest_path_alogrithm(G, u, v, algo, heuristic))
    
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  
    output_file = algo + "_" + now + ".json"
    with open(output_file, 'w') as f:
        json.dump(log, f, indent=4)
        
def stratified_random_queries(G, k=1000, target_gen=True, seed=42, bootstrapping=True):
    random.seed(seed)
    np.random.seed(seed)

    degree_dict = dict(G.degree())
    nodes = list(G.nodes())
    
    low_deg = [n for n in nodes if degree_dict[n] <= 4]
    med_deg = [n for n in nodes if 5 <= degree_dict[n] <= 9]
    high_deg = [n for n in nodes if degree_dict[n] >= 10]

    queries = []
    k_per_group = k // 3

    def sample_group(group, num_samples, used_set=None):
        samples = []
        group = list(set(group))
        if not target_gen and not bootstrapping:
            group = list(set(group) - used_set)
            random.shuffle(group)
            for i in range(min(num_samples, len(group))):
                u = group[i]
                samples.append(u)
                used_set.add(u)
        else:
            for _ in range(num_samples):
                if len(group) < 1 + int(target_gen):
                    break
                if target_gen:
                    u, v = random.sample(group, 2)
                    samples.append((u, v))
                else:
                    u = random.choice(group)
                    samples.append(u)
                    if not bootstrapping:
                        used_set.add(u)
                        group.remove(u)
        return samples

    used = set()
    queries.extend(sample_group(low_deg, k_per_group, used))
    queries.extend(sample_group(med_deg, k_per_group, used))
    queries.extend(sample_group(high_deg, k - len(queries), used))

    if len(queries) < k:
        remaining = k - len(queries)
        flat_pool = low_deg + med_deg + high_deg
        flat_pool = list(set(flat_pool))
        for _ in range(remaining):
            if target_gen:
                u, v = random.sample(flat_pool, 2)
                queries.append((u, v))
            else:
                u = random.choice(flat_pool)
                queries.append(u)

    return queries

def get_road_name_from_edge(u, v, key, G, radius=30):
    try:
        data = G[u][v][key]
        name = data.get("name")
        if name:
            return name

        geom = data.get("geometry")
        if geom:
            lon, lat = geom.coords[0]
        else:
            lat = G.nodes[u]['lat']
            lon = G.nodes[u]['lon']

        query = f"""
        [out:json];
        way(around:{radius},{lat},{lon})["highway"];
        out tags center;
        """
        r = requests.get(
            "https://overpass-api.de/api/interpreter",
            params={'data': query},
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        r.raise_for_status()
        data = r.json()
        names = [el['tags'].get('name') for el in data.get("elements", []) if el['tags'].get('name')]
        if names:
            most_common = Counter(names).most_common(1)[0][0]
            return most_common

        types = [el['tags'].get('highway') for el in data.get("elements", []) if el['tags'].get('highway')]
        if types:
            return f"Unnamed {Counter(types).most_common(1)[0][0]}"
        return "Unknown road"

    except Exception as e:
        return f"[Error] {e}"