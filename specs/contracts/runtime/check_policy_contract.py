"""Check a Guize LiteFlow policy and replay an authority-provided snapshot offline."""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from validation import read_json, validate_shape

POLICIES = Path(__file__).resolve().parents[3] / "contracts" / "policies" / "v1"
HIGH_RISK = {
    "DELETE", "RETENTION_CHANGE", "PUBLIC_PRIVATE_CONTENT", "COMMERCIAL_API", "LARGE_RESTORE",
    "WATERMARK_CHANGE", "BATCH_TRANSCODE", "REBUILD_INDEX", "ANONYMOUS_ACCESS",
}


def policy_digest(policy):
    return sha256(json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def validate_policy(policy):
    expression = policy.get("chain", {}) if isinstance(policy, dict) else {}
    expression = expression.get("expression") if isinstance(expression, dict) else None
    pending = [(expression, 0)]
    terms = 0
    while pending:
        term, depth = pending.pop()
        terms += 1
        if depth > 16 or terms > 256:
            raise ValueError("The decision expression exceeds its structural bound")
        if isinstance(term, dict):
            for operator in ("then", "if"):
                children = term.get(operator)
                if isinstance(children, list):
                    pending.extend((child, depth + 1) for child in children[:65])
    validate_shape(POLICIES / "policy.schema.yaml", policy)
    nodes = policy["nodes"]
    used = set()

    def require_node(name, expected):
        if name not in nodes or nodes[name]["kind"] != expected:
            raise ValueError(f"Expected a registered {expected} node: {name}")
        used.add(name)
        return name

    def compile_expression(expr):
        if isinstance(expr, str):
            return require_node(expr, "decision")
        if "then" in expr:
            return "THEN(" + ",".join(compile_expression(step) for step in expr["then"]) + ")"
        condition, yes, no = expr["if"]
        return "IF(" + ",".join((require_node(condition, "predicate"), compile_expression(yes), compile_expression(no))) + ")"

    chain = policy["chain"]
    if chain["el"] != compile_expression(chain["expression"]) + ";":
        raise ValueError("LiteFlow EL does not match the registered expression")
    if used != nodes.keys():
        raise ValueError("The policy contains unused nodes")
    if any(node.get("recommendation") == "DECLINE" and "priority" in node for node in nodes.values()):
        raise ValueError("A declined action cannot carry a dispatch priority")


def evaluate(policy, context):
    validate_policy(policy)
    validate_shape(POLICIES / "context.schema.yaml", context)
    action = policy["chain"]["action"]
    digest = policy_digest(policy)
    result = {"policyId": policy["policyId"], "policyVersionId": policy["policyVersionId"], "policySha256": digest,
              "chainVersion": policy["chain"]["version"],
              "action": action, "deployment": context["deployment"], "nodes": []}

    def finish(status, reason, priority=None):
        if priority is not None:
            result["priority"] = priority
        return result | {"decision": status, "reason": reason}

    if any(policy[key] != context[key] for key in ("policyId", "policyVersionId")):
        return finish("DENY", "POLICY_VERSION_MISMATCH")
    if digest != context["policySha256"]:
        return finish("DENY", "POLICY_CONTENT_MISMATCH")
    if context["deployment"] == "UNAVAILABLE":
        return finish("DENY", "POLICY_UNAVAILABLE")
    if not context["authorized"]:
        return finish("DENY", "AUTHORIZATION_REQUIRED")
    if context["budgets"].keys() != set(policy["chain"]["budgetKinds"]):
        return finish("DENY", "BUDGET_SCOPE_MISMATCH")
    if any(budget["requested"] > budget["available"] for budget in context["budgets"].values()):
        return finish("DENY", "BUDGET_EXCEEDED")
    if action in HIGH_RISK:
        approval = context.get("approval")
        if (approval is None or approval["policyVersionId"] != policy["policyVersionId"] or approval["action"] != action
                or datetime.fromisoformat(approval["expiresAt"].replace("Z", "+00:00"))
                <= datetime.fromisoformat(context["observedAt"].replace("Z", "+00:00"))):
            return finish("REQUIRE_APPROVAL", "ACTION_APPROVAL_REQUIRED")

    def record(name, value):
        result["nodes"].append({"id": name, "version": policy["nodes"][name]["version"], "result": value})

    def decide(expr):
        if isinstance(expr, str):
            node = policy["nodes"][expr]
            record(expr, node["recommendation"])
            return node["recommendation"], node.get("priority")
        if "then" in expr:
            priority = None
            for child in expr["then"]:
                decision, proposed = decide(child)
                if decision != "RECOMMEND":
                    return decision, None
                if proposed is not None:
                    priority = proposed
            return "RECOMMEND", priority
        condition, yes, no = expr["if"]
        fact = policy["nodes"][condition]["fact"]
        value = context["facts"].get(fact)
        record(condition, value)
        return ("FACT_UNAVAILABLE", None) if value is None else decide(yes if value else no)

    outcome, priority = decide(policy["chain"]["expression"])
    return finish("RECOMMEND", "MATCHED", priority) if outcome == "RECOMMEND" else finish("DENY", outcome)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    parser.add_argument("context", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(read_json(args.policy), read_json(args.context))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
