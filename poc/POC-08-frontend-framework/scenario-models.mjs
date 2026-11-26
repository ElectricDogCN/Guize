import fixture from "./scenarios.json";

const { scenarios } = fixture;

const input = (id) => scenarios.find((scenario) => scenario.scenarioId === id).arguments;

const graph = input("flowchart_equivalent");
export const graphEdges = graph.edges;
export const graphNodes = graph.nodes.map((id, index) => ({ id, label: id, x: index, y: 0 }));

const graphStorageKey = "guize-comparison/graph";

export function loadGraph() {
  const saved = localStorage.getItem(graphStorageKey);
  return saved ? JSON.parse(saved) : graphNodes;
}

export function saveGraph(nodes) {
  localStorage.setItem(graphStorageKey, JSON.stringify(nodes));
}

export function editNode(nodes, id, changes) {
  return nodes.map((node) => node.id === id ? { ...node, ...changes } : node);
}

export const initialRules = input("decision_table_equivalent").rules;

export function ruleError(rules) {
  const statuses = rules.map(({ status }) => status.trim());
  if (statuses.some((status) => !status)) return "Each rule needs a condition.";
  if (new Set(statuses).size !== statuses.length) return "Rule conditions must be unique.";
  return "";
}

export const monitoring = input("monitoring_view_equivalent");
