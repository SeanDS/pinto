"""Prompt functions."""

import abc
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.validation import Validator, ThreadedValidator
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from appdirs import user_cache_dir
from thefuzz import process
from . import PROGRAM


_CACHE_DIR = Path(user_cache_dir(PROGRAM))


def _history_cache(slug):
    cache = _CACHE_DIR / slug
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.touch()

    return FileHistory(cache)


def date_prompt(handler, dateval=None, message="Enter date: ", **kwargs):
    """Prompt user for a date.

    Several date formats are supported, including natural language dates like "today" or
    "a week ago". See :meth:`.AccountHandler.parse_date` for more information.

    Parameters
    ----------
    handler : :class:`.AccountHandler`
        An account handler instance.
    dateval : str, optional
        The date to prepopulate as the user's input. If None, the initial prompt value
        is empty.
    message : str, optional
        The prompt message.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Keyword arguments supported by :class:`prompt_toolkit.PromptSession`.

    Returns
    -------
    :class:`datetime.date`
        The date parsed from the user's input.
    """

    # Print to empty prompt value if nothing is to be predefined.
    if dateval is None:
        dateval = ""

    date_validator = ThreadedValidator(
        Validator.from_callable(handler.valid_date, error_message="Invalid date")
    )

    session = PromptSession(
        message=message,
        history=_history_cache("date"),
        validator=date_validator,
        validate_while_typing=True,
        placeholder="e.g. today",
        **kwargs,
    )

    dateval = session.prompt(default=dateval, accept_default=True)
    return handler.parse_date(dateval).date()


def account_prompt(
    handler,
    slug,
    account=None,
    suggestions=None,
    message="Enter account: ",
    placeholder="e.g. Expenses:Groceries",
    **kwargs,
):
    """Prompt user for an account, suggesting similar previously used accounts during
    input.

    Parameters
    ----------
    handler : :class:`.AccountHandler`
        An account handler instance.
    slug : str
        An internal identifier for the account type. This is used for caching and to
        provide history lookup from the same prompts in previous sessions.
    account : str, optional
        The account to prepopulate as the user's input. If None, the initial prompt
        value is empty.
    suggestions : sequence, optional
        Accounts to suggest to the user before they provide input. Note: once any input
        has been provided by the user, the provided suggestions are based only on that
        input.
    message : str, optional
        The prompt message.
    placeholder : str, optional
        The placeholder to show when no input has been provided.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Keyword arguments supported by :class:`prompt_toolkit.PromptSession`.

    Returns
    -------
    str
        The account provided by the user.
    """

    if account is None:
        account = ""

    account_validator = ThreadedValidator(
        Validator.from_callable(handler.valid_account, error_message="Invalid account")
    )

    session = PromptSession(
        message=message,
        history=_history_cache(f"account-{slug}"),
        validate_while_typing=True,
        validator=account_validator,
        placeholder=placeholder,
        completer=AccountCompleter(handler, suggestions),
        complete_while_typing=True,
        complete_in_thread=True,
        **kwargs,
    )

    return session.prompt(default=account, accept_default=False, **kwargs)


def payee_prompt(
    handler, payee=None, suggestions=None, message="Enter payee: ", **kwargs
):
    """Prompt user for a payee, suggesting similar previously used payees during input.

    Parameters
    ----------
    handler : :class:`.AccountHandler`
        An account handler instance.
    payee : str, optional
        The payee to prepopulate as the user's input. If None, the initial prompt value
        is empty.
    suggestions : sequence, optional
        Payees to suggest to the user before they provide input. Note: once any input
        has been provided by the user, the provided suggestions are based only on that
        input.
    message : str, optional
        The prompt message.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Keyword arguments supported by :class:`prompt_toolkit.PromptSession`.

    Returns
    -------
    str
        The payee provided by the user.
    """

    if payee is None:
        payee = ""

    session = PromptSession(
        message=message,
        history=_history_cache("payee"),
        placeholder="e.g. Supermarket",
        completer=PayeeCompleter(handler, suggestions),
        complete_while_typing=True,
        complete_in_thread=True,
        **kwargs,
    )

    return session.prompt(default=payee, accept_default=False, **kwargs)


def narration_prompt(
    handler, narration=None, suggestions=None, message="Enter narration: ", **kwargs
):
    """Prompt user for a narration, suggesting similar previously used narrations during
    input.

    Parameters
    ----------
    handler : :class:`.AccountHandler`
        An account handler instance.
    narration : str, optional
        The narration to prepopulate as the user's input. If None, the initial prompt
        value is empty.
    suggestions : sequence, optional
        Narrations to suggest to the user before they provide input. Note: once any
        input has been provided by the user, the provided suggestions are based only on
        that input.
    message : str, optional
        The prompt message.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Keyword arguments supported by :class:`prompt_toolkit.PromptSession`.

    Returns
    -------
    str
        The narration provided by the user.
    """

    if narration is None:
        narration = ""

    session = PromptSession(
        message=message,
        history=_history_cache("narration"),
        placeholder="e.g. Bus to city",
        completer=NarrationCompleter(handler, suggestions),
        complete_while_typing=True,
        complete_in_thread=True,
        **kwargs,
    )

    return session.prompt(default=narration, accept_default=False, **kwargs)


def payment_prompt(handler, payment=None, message="Enter value: ", **kwargs):
    """Prompt user for a payment.

    The user's input is expected to be in the form `<value> <currency>`. The value may
    be a quantity such as `-0.49` or an expression such as `21.87/2`. Expressions are
    evaluated before being returned.

    Parameters
    ----------
    handler : :class:`.AccountHandler`
        An account handler instance.
    payment : str, optional
        The payment to prepopulate as the user's input. If None, the initial prompt
        value is empty.
    message : str, optional
        The prompt message.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Keyword arguments supported by :class:`prompt_toolkit.PromptSession`.

    Returns
    -------
    str
        The payment parsed from the user's input.
    """

    if payment is None:
        payment = ""

    payment_validator = ThreadedValidator(
        Validator.from_callable(
            handler.valid_payment_expression,
            error_message="Invalid format; must be '<value> <currency>'",
        )
    )

    session = PromptSession(
        message=message,
        history=_history_cache("payment"),
        placeholder="e.g. -1.23 EUR",
        validator=payment_validator,
        validate_while_typing=True,
        **kwargs,
    )

    payment = session.prompt(default=payment, accept_default=False, **kwargs)
    return handler.parse_payment(payment)


def split_prompt(
    handler,
    total,
    total_currency,
    default=None,
    message="Choose split (fraction or amount with currency): ",
    **kwargs,
):
    """Prompt user for a split value or fraction.

    Parameters
    ----------
    handler : :class:`.AccountHandler`
        An account handler instance.
    total : float
        The total value to split.
    total_currency : str
        The currency associated with the total.
    default : str, optional
        The default split value to prepopulate as the user's input. If None, the initial
        prompt value is empty.
    message : str, optional
        The prompt message.

    Other Parameters
    ----------------
    **kwargs : dict, optional
        Keyword arguments supported by :class:`prompt_toolkit.PromptSession`.

    Returns
    -------
    float
        The split value parsed from the user's input. Note: the currency is assumed to
        be identical to `total_currency`.
    """

    if default is None:
        default = ""
    else:
        default = str(default)
        assert handler.valid_split(default)

    split_validator = ThreadedValidator(
        Validator.from_callable(handler.valid_split, error_message="Invalid split")
    )

    session = PromptSession(
        message=message,
        history=_history_cache("split"),
        placeholder="e.g. -0.5 or 1.23 USD",
        validator=split_validator,
        validate_while_typing=True,
        **kwargs,
    )

    split = session.prompt(default=default, accept_default=False, **kwargs)
    return handler.parse_split(split, total=total, total_currency=total_currency)


class LevenshteinDistanceCompleter(Completer, metaclass=abc.ABCMeta):
    """Completer that uses Levenshtein Distance to compute matches.

    This completer offers better (e.g. typo-forgiving) matching over
    :class:`prompt_toolkit.completion.FuzzyCompleter`.
    """

    def __init__(self, handler, suggestions=None):
        if suggestions is None:
            suggestions = []

        self.handler = handler
        self.suggestions = suggestions

    @property
    @abc.abstractmethod
    def possibilities(self):
        raise NotImplementedError

    def get_completions(self, document, complete_event):
        if not document.text_before_cursor:
            # Use the provided suggestions.
            for suggestion in self.suggestions:
                yield Completion(suggestion, start_position=0)
            return

        # Full search.
        for possibility, _ in process.extract(
            document.text_before_cursor, self.possibilities, limit=10
        ):
            yield Completion(
                possibility, start_position=-len(document.text_before_cursor)
            )


class AccountCompleter(LevenshteinDistanceCompleter):
    """Account completer."""

    @property
    def possibilities(self):
        return self.handler.accounts


class PayeeCompleter(LevenshteinDistanceCompleter):
    """Payee completer."""

    @property
    def possibilities(self):
        return self.handler.payees


class NarrationCompleter(LevenshteinDistanceCompleter):
    """Narration completer."""

    @property
    def possibilities(self):
        return self.handler.narrations
