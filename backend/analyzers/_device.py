import os

import torch

_device = None


def get_device() -> str:
    global _device
    if _device is not None:
        return _device
    if os.environ.get("PROOFLAYER_FORCE_CPU") == "1":
        _device = "cpu"
    elif torch.cuda.is_available():
        _device = "cuda"
    else:
        _device = "cpu"
    return _device


def to_device(model):
    return model.to(get_device())


def inputs_to_device(inputs):
    device = get_device()
    if device == "cpu":
        return inputs
    return {k: (v.to(device) if hasattr(v, "to") else v) for k, v in inputs.items()}
