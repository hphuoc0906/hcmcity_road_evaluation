from pyrosm import OSM
import networkx as nx
import pandas as pd
import geopandas as gpd

def expand_edges_by_oneway(edges: pd.DataFrame) -> pd.DataFrame:
    new_edges = []

    for idx, row in edges.iterrows():
        u, v = row['u'], row['v']
        length = row.get('length')
        if length == None or u == v:
            continue
        oneway = str(row.get('oneway')).lower()
        row_data = row.to_dict()

        if oneway == 'yes':
            new_edges.append({**row_data, 'u': u, 'v': v})
        elif oneway == '-1':
            new_edges.append({**row_data, 'u': v, 'v': u})
        elif oneway in ['no', 'none', 'nan']:
            # thêm cả hai chiều
            new_edges.append({**row_data, 'u': u, 'v': v})
            new_edges.append({**row_data, 'u': v, 'v': u})
        else:
            # coi mặc định là hai chiều nếu nhãn lạ
            new_edges.append({**row_data, 'u': u, 'v': v})
            new_edges.append({**row_data, 'u': v, 'v': u})
    new_edges = pd.DataFrame(new_edges)
    edges_clean = gpd.GeoDataFrame(new_edges, geometry=new_edges['geometry'], crs=edges.crs)
    
    return edges_clean

def preprocess_graph(G):
    id_map = {nid: i for i, nid in enumerate(G.nodes)}
    G = nx.relabel_nodes(G, id_map, copy=True)
    
    edges_to_remove = []

    for u, v, k, data in G.edges(keys=True, data=True):
        if data.get('length') is None:
            edges_to_remove.append((u, v, k))

    G.remove_edges_from(edges_to_remove)

    edges_to_add = []
    edges_to_remove = []

    for u, v, k, data in G.edges(keys=True, data=True):
        oneway = str(data.get('oneway')).lower()
        if u == v:
            edges_to_remove.append((u, v, k))
            continue
        
        if oneway == 'yes':
            continue
        elif oneway == '-1':
            edges_to_add.append((v, u, data.copy()))
            edges_to_remove.append((u, v, k))
        elif oneway in ['no', 'none', 'nan']:
            edges_to_add.append((v, u, data.copy()))
        else:
            edges_to_add.append((v, u, data.copy()))

    for u, v, k in edges_to_remove:
        G.remove_edge(u, v, key=k)
    
    for u, v, data in edges_to_add:
        G.add_edge(u, v, **data)

    return G


osm = OSM("hochiminh.osm.pbf")
nodes, edges = osm.get_network(network_type="all", nodes=True)
graph = osm.to_graph(nodes, edges, graph_type='networkx')
graph = preprocess_graph(graph)