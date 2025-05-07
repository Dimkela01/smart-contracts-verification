from solcx import compile_source
import os


def parse_index_access(node):
    if node["nodeType"] == "IndexAccess":
        base = parse_expression(node["baseExpression"])
        index = parse_expression(node["indexExpression"])

        if base == "balances":
            if index == "msg.sender":
                return "sender_balance"
            elif index in ("to", "recipient"):
                return "receiver_balance"
            else:
                return f"balances_{index}"
    return "<unknown>"


def normalize_variable(name):
    if name in ("value", "amount", "tokens"):
        return "amount"
    return name


def parse_expression(expr):
    node_type = expr["nodeType"]

    if node_type == "MemberAccess":
        base = expr['expression']
        base_name = parse_expression(base)
        return f"{base_name}.{expr['memberName']}"
    elif node_type == "Identifier":
        return normalize_variable(expr["name"])
    elif node_type == "Literal":
        return expr["value"]
    elif node_type == "BinaryOperation":
        left = parse_expression(expr["leftExpression"])
        op = expr["operator"]
        right = parse_expression(expr["rightExpression"])
        return f"{left} {op} {right}"
    elif node_type == "UnaryOperation":
        op = expr["operator"]
        sub = parse_expression(expr["subExpression"])
        return f"{op}{sub}"
    elif node_type == "IndexAccess":
        return parse_index_access(expr)
    return "<unknown>"


def extract_transfer_logic(ast_root):
    guard_expr = None
    transitions = []
    used_vars = set()
    require_seen = False

    def visit(node):
        nonlocal guard_expr, transitions, require_seen

        if node.get("nodeType") == "FunctionDefinition":
            if node.get("name") != "transfer":
                return  # Only process the `transfer` function

            body = node.get("body", {}).get("statements", [])
            for stmt in body:
                if stmt["nodeType"] == "ExpressionStatement":
                    expr = stmt["expression"]
                    if expr["nodeType"] == "FunctionCall":
                        fn_name = expr["expression"].get("name")
                        if fn_name == "require":
                            require_seen = True
                            condition = expr["arguments"][0]
                            guard_expr = parse_expression(condition)
                            used_vars.update(extract_identifiers(condition))

                    elif expr["nodeType"] == "Assignment":
                        operator = expr.get("operator", "=")
                        lhs = parse_index_access(expr["leftHandSide"])
                        rhs = parse_expression(expr["rightHandSide"])

                        if lhs == "<unknown>" or rhs == "<unknown>":
                            continue

                        if rhs == "1000":  # Skip constant overwrite noise
                            continue

                        if operator == "-=":
                            transition_rhs = f"{lhs} - {rhs}"
                        elif operator == "+=":
                            transition_rhs = f"{lhs} + {rhs}"
                        else:
                            transition_rhs = rhs

                        transitions.append({
                            "lhs": lhs,
                            "rhs": transition_rhs,
                            "guarded": require_seen
                        })

                        used_vars.add(lhs)
                        used_vars.update(extract_identifiers(expr["rightHandSide"]))

                elif stmt["nodeType"] == "IfStatement":
                    condition = stmt["condition"]
                    true_body = stmt.get("trueBody", {})
                    revert_found = False

                    if true_body.get("nodeType") == "ExpressionStatement":
                        expr = true_body.get("expression", {})
                        if expr.get("nodeType") == "FunctionCall":
                            callee = expr.get("expression", {})
                            if callee.get("nodeType") == "Identifier" and callee.get("name") == "revert":
                                revert_found = True

                    elif true_body.get("nodeType") == "Block":
                        for sub in true_body.get("statements", []):
                            expr = sub.get("expression", {})
                            if expr.get("nodeType") == "FunctionCall":
                                callee = expr.get("expression", {})
                                if callee.get("nodeType") == "Identifier" and callee.get("name") == "revert":
                                    revert_found = True

                    if revert_found:
                        parsed = parse_expression(condition)
                        guard_expr = f"!({parsed})"
                        require_seen = True
                        used_vars.update(extract_identifiers(condition))

        for key, value in node.items():
            if isinstance(value, dict) and 'nodeType' in value:
                visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and 'nodeType' in item:
                        visit(item)

    visit(ast_root)
    return guard_expr, transitions, used_vars


def extract_identifiers(expr):
    identifiers = set()
    def recurse(node):
        if isinstance(node, dict):
            if node.get("nodeType") == "Identifier":
                identifiers.add(normalize_variable(node["name"]))
            for v in node.values():
                recurse(v)
        elif isinstance(node, list):
            for item in node:
                recurse(item)
    recurse(expr)
    return identifiers


def generate_smv_from_sol(sol_path, smv_output_path):
    with open(sol_path, "r") as f:
        source_code = f.read()

    compiled = compile_source(source_code, output_values=["ast"], solc_version="0.8.20")
    (_, contract_data), = compiled.items()
    ast = contract_data.get("ast")

    guard, transitions, used_vars = extract_transfer_logic(ast)

    state_vars = {
        "sender_balance": "0..1000",
        "receiver_balance": "0..1000",
        "amount": "0..1000"
    }

    if transitions:
        variables = "VAR\n" + "\n".join([
            f"    {name} : {range_str};" for name, range_str in state_vars.items()
        ])

        init = """\nINIT\n    sender_balance = 500 & receiver_balance = 500 & amount = 0;"""

        guarded_trans = []
        unguarded_trans = []
        assigned = set()

        for t in transitions:
            if t["lhs"] not in assigned and t["rhs"] != "1000":
                expr = f"next({t['lhs']}) = {t['rhs']}"
                if t["guarded"]:
                    guarded_trans.append(expr)
                else:
                    unguarded_trans.append(expr)
                assigned.add(t["lhs"])

        trans_sections = []

        if unguarded_trans:
            trans_sections.append(
                "TRANS\n    " + " &\n    ".join(unguarded_trans) + ";"
            )

        if guarded_trans and guard:
            trans_sections.append(
                f"TRANS\n    ({guard}) ->\n    (" + " &\n    ".join(guarded_trans) + ");"
            )

        trans = "\n\n".join(trans_sections)

        smv_code = f"MODULE main\n{variables}\n{init}\n{trans}"

        os.makedirs(os.path.dirname(smv_output_path), exist_ok=True)
        with open(smv_output_path, "w") as f:
            f.write(smv_code)

        print(f"Model saved to {smv_output_path}")
    else:
        raise Exception("Could not extract valid logic from AST!")

