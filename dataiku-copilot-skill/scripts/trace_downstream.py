import json

flow_file = (
    r"c:\Users\barth\AppData\Roaming\Code\User\workspaceStorage"
    r"\d4777deee59f6feaa8a3f1b7d97944ef\GitHub.copilot-chat\chat-session-resources"
    r"\1eb0ddb8-a0bb-4e9e-a235-add18dc9b0f9"
    r"\toolu_bdrk_01GBurKhwnxEyWuLzZ67WNvi__vscode-1777568842199\content.json"
)

with open(flow_file) as f:
    data = json.load(f)

flow = data["result"]["flow"]
nodes = {n["id"]: n for n in flow["nodes"]}
edges = flow["edges"]
target = "26A_multiseason_after_erreur_intrants_claims"

tnode = next((n for n in flow["nodes"] if n["name"] == target), None)
if not tnode:
    print("Target node not found")
    raise SystemExit(1)

print(f"Target: {tnode['name']} (id={tnode['id']})")

def trace(node_id, depth=0, visited=None):
    if visited is None:
        visited = set()
    if node_id in visited:
        return
    visited.add(node_id)
    down = [e for e in edges if e["from"] == node_id]
    for e in down:
        n = nodes[e["to"]]
        print("  " * depth + f"-> [{n['type']}] {n['name']}")
        trace(n["id"], depth + 1, visited)

trace(tnode["id"])
