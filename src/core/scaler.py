
import time

class SwarmScaler:
    def __init__(self):
        self.nodes = {} # {node_id: {"load": 0, "status": "online"}}

    def update_node_load(self, node_id, load_percent):
        self.nodes[node_id] = {"load": load_percent, "last_seen": time.time()}

    def get_optimal_node(self):
        """Выбирает наименее нагруженную ноду для задачи"""
        if not self.nodes: return "local"
        best_node = min(self.nodes, key=lambda x: self.nodes[x]['load'])
        if self.nodes[best_node]['load'] > 90: return "queue"
        return best_node

    def scale_report(self):
        return f"[SCALER] Активных узлов: {len(self.nodes)}. Средняя нагрузка роя: {self._get_avg_load()}%"

    def _get_avg_load(self):
        if not self.nodes: return 0
        return sum(n['load'] for n in self.nodes.values()) / len(self.nodes)
