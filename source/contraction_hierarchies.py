import heapq
import copy
import math
import time
import networkx as nx

class ContractionHierarchies:
    def __init__(self, graph):
        self.new_edges = []
        self.sto_shortcut = []
        self.G = copy.deepcopy(graph)
        self.n = self.G.number_of_nodes()
        self.nodes_order = [None] * self.n
        self.order_nodes = [None] * self.n
        self.need_recompute = [None] * self.n
        self.shortcut = {}
        self.weight_backward = {}
        self.weight = self._init_weight()
        

    def _init_weight(self):
        weight = {}
        for node in self.G.nodes:
            if node not in weight:
                weight[node] = {}
            for _, v, w1 in list(self.G.out_edges(node, data='length')):
                if v not in weight[node] or w1 < weight[node][v]:
                    weight[node][v] = w1
                
            for u, _, w2 in list(self.G.in_edges(node, data='length')):
                if u not in weight:
                    weight[u] = {}
                if node not in weight[u] or w2 < weight[u][node]:
                    weight[u][node] = w2
            
        self.new_edges = []
        for u in weight.keys():
            if u not in self.shortcut:
                self.shortcut[u] = {}
            for v, w in weight[u].items():
                self.new_edges.append((u, v, w, -1))
                self.shortcut[u][v] = -1
        return weight
        
    def dijkstra_path_local_seach(self, source, target=None, avoid_node=None, threshold=None, hop = -1, theta=50):
        pq = [(0, source, 0)]
        dis = {source: 0}
                    
        visited = set()
        
        while len(pq) > 0 and len(visited) <= theta:
            cur_dis, u, cnt_edge = heapq.heappop(pq)

            if u == target:
                break
            if u == avoid_node or u in visited:
                continue
            if hop != -1 and cnt_edge >= hop:
                continue
            if threshold is not None and cur_dis > threshold:
                continue
            visited.add(u)
            
            for v in list(self.G.successors(u)):
                if v == avoid_node:
                    continue
    
                dis_v = cur_dis + self.weight[u][v]
                if (v not in dis or dis_v < dis[v]):
                    if (threshold == None) or (threshold != None and dis_v <= threshold): 
                        dis[v] = dis_v
                        heapq.heappush(pq, (dis_v, v, cnt_edge + 1))
                    
        return dis
        
    def edge_difference(self, node):

        successors = list(self.G.successors(node))
        predecessors = list(self.G.predecessors(node))
        dif_edge = -len(successors) - len(predecessors)
        
        for u in predecessors:
            
            w2 = self.weight[u][node]
            cur_dis = {}
            limit_weight = -1e9
            for v in successors:
                
                w1 = self.weight[node][v]
                
                cur_dis[v] = w1 + w2
            if len(cur_dis) == 0:
                continue
                
            limit_weight = max(cur_dis.values())
            dis = self.dijkstra_path_local_seach(source=u, avoid_node=node, threshold = limit_weight, hop=5)

            for v in successors:
                
                if (v not in dis) or (dis[v] > cur_dis[v]):
                    dif_edge += 1

        return dif_edge
                    
    def get_nodes_order(self):
        priority_queue = []
        for node in self.G.nodes:
            edge_diff = self.edge_difference(node)
            self.need_recompute[node] = False
            heapq.heappush(priority_queue, (edge_diff, node))
        return priority_queue

    def build_contraction_hierarchy(self):
        priority_queue = self.get_nodes_order()
        cnt = 0
        total_nodes = len(priority_queue)
        while priority_queue:
            score, node = heapq.heappop(priority_queue)
            
            if self.need_recompute[node] == True:
                current_score = self.edge_difference(node)
                self.need_recompute[node] = False
                if priority_queue and current_score > priority_queue[0][0]:
                    heapq.heappush(priority_queue, (current_score, node))
                    continue
                
            
            self.nodes_order[node] = cnt 
            self.order_nodes[cnt] = node
            cnt += 1
            
            successors = list(self.G.successors(node))
            predecessors = list(self.G.predecessors(node))

            for u in predecessors:
                
                w2 = self.weight[u][node]
                cur_dis = {}
                limit_weight = -1e9
                for v in successors:
                    
                    w1 = self.weight[node][v]
                    
                    cur_dis[v] = w1 + w2
                if len(cur_dis) == 0:
                    continue

                limit_weight = max(cur_dis.values())
                dis = self.dijkstra_path_local_seach(source=u, avoid_node=node, threshold = limit_weight, hop=5)
            
                for v in successors:
                    
                    if (v not in dis) or (dis[v] > cur_dis[v]):

                        check_edge = self.G.has_edge(u, v)
                        if not check_edge:
                            self.G.add_edge(u, v)
                        self.weight[u][v] = cur_dis[v]
                        self.shortcut[u][v] = node
                            
            for u in predecessors:
                self.need_recompute[u] = True
                self.new_edges.append((u, node, self.weight[u][node], self.shortcut[u][node]))
                del self.weight[u][node], self.shortcut[u][node]
                
            for v in successors:
                self.need_recompute[v] = True
                self.new_edges.append((node, v, self.weight[node][v], self.shortcut[node][v]))
                del self.weight[node][v], self.shortcut[node][v]
                
            self.G.remove_node(node)
        self._build_new_graph()
        
    def _build_new_graph(self):
        self.weight.clear()
        self.shortcut.clear()
        self.weight = {i: {} for i in range(self.n)}
        self.shortcut = {i: {} for i in range(self.n)}
        
        for u, v, w, shortc in self.new_edges:
            if v not in self.weight[u] or w < self.weight[u][v]:
                self.weight[u][v] = w
                self.shortcut[u][v] = shortc
                if v not in self.weight_backward:
                    self.weight_backward[v] = {}
                self.weight_backward[v][u] = w

    
    def get_shortcut(self, source, target):
        shortcut_node = self.shortcut[source][target]
        if shortcut_node != -1:
            return self.get_shortcut(source, shortcut_node) + [shortcut_node] + self.get_shortcut(shortcut_node, target)
        else:
            return []
            
    def get_path(self, parent, target, forward=True):
        node = target
        path = []
        while (node != -1):
            path.append(node)
            if parent[node] != -1:
                parent_node = parent[node]
                temp_path = self.get_shortcut(parent_node, node) if forward else self.get_shortcut(node, parent_node)
                if forward:
                    temp_path.reverse()
                path += temp_path
                node = parent_node
            else:
                break
        return path

    def dijkstra_search(self, source, weight):
        pq = [(0, source)]
        dis = {source: 0}
        parent = {source: -1}
        visited = set()
        cnt_shortest_path = {source: 1}
        sto_processnode = []
        predes = {}
        
        cnt_sp = None
        
        while pq:
            cur_dis, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)

            cnt_sp = cnt_shortest_path[u]
            sto_processnode.append(u)
            
            for v in weight[u].keys():
                if self.nodes_order[u] < self.nodes_order[v]:
                    dis_v = cur_dis + weight[u][v]
                    
                    if v in dis and dis_v == dis[v]:
                        cnt_shortest_path[v] += cnt_sp
                        predes[v].append(u)
                        
                    if v not in dis or dis_v < dis[v]:
                        dis[v] = dis_v
                        parent[v] = u
                        heapq.heappush(pq, (dis_v, v))
                        
                        cnt_shortest_path[v] = cnt_sp
                        predes[v] = [u]
        return {
            'source': source,
            'dis': dis,
            'parent': parent,
            'cnt_shortest_path': cnt_shortest_path,
            'sto_processnode': sto_processnode,
            'predes': predes
        }
        
    def bidirectional_dijkstra(self, source, target=None, only_need_dis=False):
        
        start = time.time()
        dijkstra_source = self.dijkstra_search(source=source, weight=self.weight)
        dis_s = dijkstra_source['dis']

        dis_t = None
        if target != None:
            dijkstra_target = self.dijkstra_search(source=target, weight=self.weight_backward)
            dis_t = dijkstra_target['dis']
            
            shortest_length = math.inf
            tmp = None
            path = []
            for node in dis_s:
                if node in dis_t and shortest_length > dis_s[node] + dis_t[node]:
                    tmp = node
                    shortest_length = dis_s[node] + dis_t[node]
                
        process_time = time.time() - start
        if only_need_dis == True and target != None:
            return shortest_length
            
        parent_s = dijkstra_source['parent']
        if target != None:
            parent_t = dijkstra_target['parent']
            
            if tmp != None:
                path_s_tmp, path_t_tmp = [], []
                if tmp != source:
                    path_s_tmp = self.get_path(parent_s, tmp)
                    path_s_tmp.reverse()
                if tmp != target:
                    path_t_tmp = self.get_path(parent_t, tmp, forward=False)
                path = path_s_tmp[:-1] + path_t_tmp
        ans = {
            'source': source,
            'latency_s': process_time,
            'dist_s': dis_s,
            'cnt_shortest_path_source': dijkstra_source['cnt_shortest_path'],
            'sto_processnode_source': dijkstra_source['sto_processnode'],
            'predes_source': dijkstra_source['predes'],
        }
        if target != None:
            ans.update({
                'target': target,
                'path_length': shortest_length,
                'path_nodes': path,
                'dist_t': dis_t,
                'cnt_shortest_path_target': dijkstra_target['cnt_shortest_path'],
                'sto_processnode_target': dijkstra_target['sto_processnode'],
                'predes_target': dijkstra_target['predes']
            })
        return ans