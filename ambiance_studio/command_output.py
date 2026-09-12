"""Declare --out ownership at registration without changing command namespaces."""
import argparse
from enum import Enum


class Output(Enum):
    REPORT = 'result-envelope'
    FILE = 'command-file'
    ARTIFACT = 'artifact-directory'


def add_output(parser, semantics, **kwargs):
    """Register the ordinary path flag; only REPORT is written by the CLI.

    The command service retains path resolution, encoding, immutability and
    recovery rules for FILE and ARTIFACT. Metadata lives on the argument action,
    never in a namespace passed to a scene transaction or saved command recipe.
    """
    if not isinstance(semantics, Output):
        raise ValueError('Output registration needs explicit Output semantics')
    action = parser.add_argument('--out', **kwargs)
    action.output_semantics = semantics
    return action


def selected_output(parser, args):
    """Find the selected leaf's declaration, including nested command groups."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            child = action.choices.get(getattr(args, action.dest, None))
            if child is not None:
                return selected_output(child, args)
    action = parser._option_string_actions.get('--out')
    if action is None:
        return None
    if not isinstance(getattr(action, 'output_semantics', None), Output):
        raise ValueError(f'{parser.prog}: --out needs explicit output semantics')
    return action.output_semantics
