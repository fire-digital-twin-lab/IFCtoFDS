"""Resolve explicit public exports without initializing unrelated kernels or workers."""

from importlib import import_module


def resolve(exports, name):
    try:
        module, attribute = exports[name]
    except KeyError:
        raise AttributeError(name) from None
    return getattr(import_module(module), attribute)
