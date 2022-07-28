import ast
from collections import namedtuple
from typing import Any, Dict, Optional


def is_module_function_call(node: ast.Call, module: str, function: str) -> bool:
    try:
        return node.func.attr == function and node.func.value.id == module  # type: ignore
    except AttributeError:
        return False


ParseResult = namedtuple(
    "ParseResult", ["step", "parameters", "inputs", "image", "environment"]
)


class PrepareParser(ast.NodeVisitor):
    """Parses .py file for Valohai inputs, parameters, step name

    Using AST parser, visits all method calls of a Python file.

    If a call to valohai.prepare() method is found, iterate through
    it's arguments and look for inputs, parameters and a step name.

    All possible ways to call prepare() are not supported

    Works:
        valohai.prepare(parameters={"param1": "foobar"})

    Works:
        parameters={"param1": "foobar"}
        valohai.prepare(parameters=parameters)

    Fails:
        import valohai as herpderp
        herpderp.prepare(parameters={"param1": "foobar"})

    Fails:
        from valohai import prepare
        prepare(parameters={"param1": "foobar"})

    Fails:
        valohai.prepare(parameters=get_parameters())
    """

    assignments: Dict[str, Any]  # TODO: embetter type
    parameters: Dict[str, Any]  # TODO: embetter type
    inputs: Dict[str, Any]  # TODO: embetter type
    step: Optional[str]
    environment: Optional[str]

    def __init__(self) -> None:
        self.assignments = {}
        self.parameters = {}
        self.inputs = {}
        self.step = None
        self.image = None
        self.environment = None

    def visit_Assign(self, node: ast.Assign) -> None:
        try:
            self.assignments[node.targets[0].id] = ast.literal_eval(node.value)  # type: ignore
        except (ValueError, AttributeError):
            # We don't care about assignments that can't be literal_eval():ed
            pass

    def visit_Call(self, node: ast.Call) -> None:
        if is_module_function_call(node, "valohai", "prepare"):
            self.process_valohai_prepare_call(node)

    def process_valohai_prepare_call(self, node: ast.Call) -> None:
        self.step = "default"
        if hasattr(node, "keywords"):
            for key in node.keywords:
                if key.arg == "default_parameters":
                    self.process_default_parameters_arg(key)
                elif key.arg == "default_inputs":
                    self.process_default_inputs_arg(key)
                elif key.arg == "step":
                    self.step = ast.literal_eval(key.value)
                elif key.arg == "image":
                    self.image = ast.literal_eval(key.value)
                elif key.arg == "environment":
                    self.environment = ast.literal_eval(key.value)

    def _process_kwarg(self, key: ast.keyword, *, error_hint: str = "") -> Any:
        if isinstance(key.value, ast.Name) and key.value.id in self.assignments:
            return self.assignments[key.value.id]
        if isinstance(key.value, ast.Dict):
            return ast.literal_eval(key.value)
        raise NotImplementedError(f"Unable to parse {error_hint}: {key.value!r}")

    def process_default_inputs_arg(self, key: ast.keyword) -> None:
        self.inputs = self._process_kwarg(key, error_hint="inputs=")

    def process_default_parameters_arg(self, key: ast.keyword) -> None:
        self.parameters = self._process_kwarg(key, error_hint="parameters=")


def parse(source: str) -> ParseResult:
    tree = ast.parse(source)
    parser = PrepareParser()
    parser.visit(tree)
    return ParseResult(
        step=parser.step,
        parameters=parser.parameters,
        inputs=parser.inputs,
        image=parser.image,
        environment=parser.environment,
    )
