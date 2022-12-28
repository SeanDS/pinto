"""CLI tools"""

import sys
from itertools import zip_longest
import click


def recoverable_error(msg, err=True, **kwargs):
    click.secho(msg, fg="red", **kwargs)


def exit_error(msg, **kwargs):
    recoverable_error(msg, **kwargs)
    sys.exit(1)


def echo_info(msg=None, **kwargs):
    click.secho(msg, fg="green", **kwargs)


def echo_info_params(msg, params, **kwargs):
    """Echo info with parameters made bold."""
    pieces = msg.split("{}")
    for piece, param in zip_longest(pieces, params):
        if piece is not None:
            echo_info(str(piece), nl=False)
        if param is not None:
            echo_info(str(param), nl=False, bold=True)
    echo_info()


def echo_warning(msg=None, **kwargs):
    click.secho(msg, fg="yellow", **kwargs)


def echo_warning_params(msg, params, **kwargs):
    """Echo warning with parameters made bold."""
    pieces = msg.split("{}")
    for piece, param in zip_longest(pieces, params):
        if piece is not None:
            echo_warning(str(piece), nl=False)
        if param is not None:
            echo_warning(str(param), nl=False, bold=True)
    echo_warning()
