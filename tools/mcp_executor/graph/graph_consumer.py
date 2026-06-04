import json
import os

LOG_FILE = os.path.expanduser(
    "~/Documents/NEVA/tools/mcp_executor/graph/execution.log"
)


def load_events():
    events = []

    if not os.path.exists(LOG_FILE):
        return events

    with open(LOG_FILE, "r") as f:
        for line in f:
            try:
                events.append(json.loads(line.strip()))
            except Exception:
                continue

    return events


def to_graph(events):
    nodes = []
    edges = []

    for e in events:
        node_id = f"{e.get('timestamp')}_{e.get('action')}"

        nodes.append({
            "id": node_id,
            "label": e.get("action"),
            "timestamp": e.get("timestamp")
        })

        edges.append({
            "from": "NEVA_ROOT",
            "to": node_id,
            "type": "EXECUTION"
        })

    return nodes, edges


def build_graph_packet():
    events = load_events()
    nodes, edges = to_graph(events)

    graph_size = len(nodes)

    density = 0
    if graph_size > 0:
        density = len(edges) / graph_size

    return {
        "status": "ok",
        "metrics": {
            "nodes": graph_size,
            "edges": len(edges),
            "density": density
        },
        "graph": {
            "nodes": nodes,
            "edges": edges
        }
    }
