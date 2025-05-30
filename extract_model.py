from solcx import compile_source
import os


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
        base = parse_expression(expr["baseExpression"])
        index = parse_expression(expr["indexExpression"])
        return f"{base}_{index}"
    return "<unknown>"


def extract_logic(ast_root):
    function_map = {}
    used_vars = set()

    def visit(node):
        if node.get("nodeType") == "FunctionDefinition" and node.get("body"):
            func_name = node.get("name")
            transitions = []
            current_guard = None

            body = node.get("body", {}).get("statements", [])
            for stmt in body:
                if stmt["nodeType"] == "ExpressionStatement":
                    expr = stmt["expression"]

                    if expr["nodeType"] == "FunctionCall":
                        fn_name = expr["expression"].get("name")
                        if fn_name == "require":
                            current_guard = parse_expression(expr["arguments"][0])
                            used_vars.update(extract_identifiers(expr["arguments"][0]))

                    elif expr["nodeType"] == "Assignment":
                        operator = expr.get("operator", "=")
                        lhs = parse_expression(expr["leftHandSide"])
                        rhs = parse_expression(expr["rightHandSide"])

                        if lhs == "<unknown>" or rhs == "<unknown>":
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
                            "guard": current_guard
                        })

                        used_vars.add(lhs)
                        used_vars.update([rhs])

            if transitions:
                function_map[func_name] = transitions

        for key, value in node.items():
            if isinstance(value, dict) and 'nodeType' in value:
                visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and 'nodeType' in item:
                        visit(item)

    visit(ast_root)
    return function_map, used_vars


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


def generate_dot_from_transitions(function_map, dot_output_path):
    lines = ["digraph FSM {", "    rankdir=LR;"]
    for func, transitions in function_map.items():
        for t in transitions:
            from_var = t['lhs']
            to_expr = t['rhs']
            guard = f" [{t['guard']}]" if t.get("guard") else ""
            lines.append(f'    "{from_var}" -> "{to_expr}" [label="{func}{guard}"];')
    lines.append("}")
    with open(dot_output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Graphviz .dot model saved to {dot_output_path}")


def generate_smv_from_sol(sol_path, smv_output_path, dot_output_path="./.dot"):
    with open(sol_path, "r") as f:
        source_code = f.read()

    compiled = compile_source(source_code, output_values=["ast"], solc_version="0.8.20")
    (_, contract_data), = compiled.items()
    ast = contract_data.get("ast")

    function_map, used_vars = extract_logic(ast)
    state_vars = {var: "0..1000" for var in used_vars if var != "<unknown>"}

    if function_map:
        variables = "VAR\n" + "\n".join([
            f"    {name} : {range_str};" for name, range_str in state_vars.items()
        ]) + "\n    call : {{" + ", ".join(function_map.keys()) + "}};"

        init = "\nINIT\n    " + " & ".join([
            f"{var} = 0" for var in state_vars
        ]) + f" & call = {list(function_map.keys())[0]};"

        trans_sections = []
        for func_name, transitions in function_map.items():
            guarded = []
            unguarded = []
            for t in transitions:
                expr = f"next({t['lhs']}) = {t['rhs']}"
                if t.get("guard"):
                    guarded.append((t["guard"], expr))
                else:
                    unguarded.append(expr)

            if unguarded:
                trans_sections.append(f"TRANS\n    (call = {func_name}) ->\n    (" + " &\n    ".join(unguarded) + ");")

            if guarded:
                grouped = {}
                for guard, expr in guarded:
                    grouped.setdefault(guard, []).append(expr)
                for guard, exprs in grouped.items():
                    trans_sections.append(
                        f"TRANS\n    (call = {func_name} & {guard}) ->\n    (" + " &\n    ".join(exprs) + ");"
                    )

        trans = "\n\n".join(trans_sections)

        smv_code = f"MODULE main\n{variables}\n{init}\n{trans}"

        os.makedirs(os.path.dirname(smv_output_path), exist_ok=True)
        with open(smv_output_path, "w") as f:
            f.write(smv_code)

        print(f"Model saved to {smv_output_path}")

        if dot_output_path:
            generate_dot_from_transitions(function_map, dot_output_path)

    else:
        raise Exception("No valid transitions extracted from AST!")
