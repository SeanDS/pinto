"""CLI tools"""

import sys
from itertools import zip_longest
import click


def recoverable_error(msg, **kwargs):
    """Print a recoverable error.

    Parameters
    ----------
    msg : str
        The error message.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Arguments supported by :func:`click.secho`.
    """
    click.secho(msg, fg="red", err=True, **kwargs)


def exit_error(msg, **kwargs):
    """Print a fatal error.

    Parameters
    ----------
    msg : str
        The error message.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Arguments supported by :func:`click.secho`.
    """
    recoverable_error(msg, **kwargs)
    sys.exit(1)


def echo_info(msg=None, **kwargs):
    """Print an informational message.

    Parameters
    ----------
    msg : str, optional
        The informational message. If None, an empty line is printed.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Keyword arguments supported by :func:`click.secho`.
    """
    click.secho(msg, fg="green", **kwargs)


def echo_info_params(msg, params, **kwargs):
    """Print an informational message, optionally with sections highlighted in bold.

    Parameters
    ----------
    msg : str
        The message. Occurrances of `{}` are replaced by the next item in `params`, in
        bold.
    params : sequence
        The bold parameters to insert into `msg`.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Arguments supported by :func:`click.secho`.
    """
    pieces = msg.split("{}")
    for piece, param in zip_longest(pieces, params):
        if piece is not None:
            echo_info(str(piece), nl=False)
        if param is not None:
            echo_info(str(param), nl=False, bold=True)
    echo_info()


def echo_warning(msg=None, **kwargs):
    """Print a warning.

    Parameters
    ----------
    msg : str
        The warning message. If None, an empty line is printed.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Arguments supported by :func:`click.secho`.
    """
    click.secho(msg, fg="yellow", **kwargs)


def echo_warning_params(msg, params, **kwargs):
    """Print a warning message, optionally with sections highlighted in bold.

    Parameters
    ----------
    msg : str
        The warning message. Occurrances of `{}` are replaced by the next item in
        `params`, in bold.
    params : sequence
        The bold parameters to insert into `msg`.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Arguments supported by :func:`click.secho`.
    """
    pieces = msg.split("{}")
    for piece, param in zip_longest(pieces, params):
        if piece is not None:
            echo_warning(str(piece), nl=False)
        if param is not None:
            echo_warning(str(param), nl=False, bold=True)
    echo_warning()
