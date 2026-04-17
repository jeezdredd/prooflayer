import importlib

from .base import BaseAnalyzer


def load_analyzer_class(dotted_path: str) -> type[BaseAnalyzer]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    if not issubclass(cls, BaseAnalyzer):
        raise TypeError(f"{dotted_path} is not a subclass of BaseAnalyzer")
    return cls
