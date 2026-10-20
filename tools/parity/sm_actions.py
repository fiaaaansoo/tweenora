import json

MAX_ACTIONS = 400
STEP = 0.25
SETTLE = 1.0
NUMBER_VALUES = (0, 1, -1, 50, 100)
POINTER_GRID = ((0.5, 0.5), (0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))


def advance(dt):
    return {"op": "advance", "dt": dt}


def generate(description):
    if not description:
        return None
    actions = [advance(0.0), advance(STEP)]
    for entry in description.get("inputs", []):
        name, kind = entry["name"], entry["kind"]
        if kind == "bool":
            for value in (True, False):
                actions += [{"op": "bool", "name": name, "value": value}, advance(STEP)]
        elif kind == "number":
            for value in NUMBER_VALUES:
                actions += [{"op": "number", "name": name, "value": value}, advance(STEP)]
        elif kind == "trigger":
            actions += [{"op": "trigger", "name": name}, advance(STEP), advance(STEP)]
    width, height = description.get("width", 0), description.get("height", 0)
    if width > 0 and height > 0:
        for fx, fy in POINTER_GRID:
            x, y = round(width * fx, 3), round(height * fy, 3)
            actions += [
                {"op": "pointer", "kind": "move", "x": x, "y": y},
                advance(STEP),
                {"op": "pointer", "kind": "down", "x": x, "y": y},
                advance(STEP),
                {"op": "pointer", "kind": "up", "x": x, "y": y},
                advance(STEP),
            ]
    actions.append(advance(SETTLE))
    return actions[:MAX_ACTIONS - 1] + [advance(SETTLE)] if len(actions) > MAX_ACTIONS else actions


def script_text(actions):
    return "".join(json.dumps(action, sort_keys=True) + "\n" for action in actions)
