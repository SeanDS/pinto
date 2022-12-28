"""Prompts."""

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
_DATE_CACHE = _CACHE_DIR / "date"
_ACCOUNT_CACHE = _CACHE_DIR / "account"
_PAYEE_CACHE = _CACHE_DIR / "payee"
_NARRATION_CACHE = _CACHE_DIR / "narration"
_PAYMENT_CACHE = _CACHE_DIR / "payment"
_FRACTION_CACHE = _CACHE_DIR / "fraction"

# Create cache files if necessary.
for cache in [_DATE_CACHE, _ACCOUNT_CACHE]:
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.touch()


def date_prompt(handler, dateval=None, message="Enter date: ", **kwargs):
    # Print to empty prompt value if nothing is to be predefined.
    if dateval is None:
        dateval = ""

    date_validator = ThreadedValidator(
        Validator.from_callable(handler.valid_date, error_message="Invalid date")
    )

    session = PromptSession(
        message=message,
        history=FileHistory(_DATE_CACHE),
        validator=date_validator,
        validate_while_typing=True,
        placeholder="e.g. 12th Dec",
        **kwargs
    )

    dateval = session.prompt(default=dateval, accept_default=True)
    return handler.parse_date(dateval).date()


def account_prompt(
    handler,
    account=None,
    suggestions=None,
    message="Enter account: ",
    placeholder="e.g. Expenses:Groceries",
    **kwargs
):
    if account is None:
        account = ""

    account_validator = ThreadedValidator(
        Validator.from_callable(handler.valid_account, error_message="Invalid account")
    )

    session = PromptSession(
        message=message,
        history=FileHistory(_ACCOUNT_CACHE),
        validate_while_typing=True,
        validator=account_validator,
        placeholder=placeholder,
        completer=AccountCompleter(handler, suggestions),
        complete_while_typing=True,
        complete_in_thread=True,
        **kwargs
    )

    return session.prompt(default=account, accept_default=False, **kwargs)


def payee_prompt(
    handler, payee=None, suggestions=None, message="Enter payee: ", **kwargs
):
    if payee is None:
        payee = ""

    session = PromptSession(
        message=message,
        history=FileHistory(_PAYEE_CACHE),
        placeholder="e.g. Supermarket",
        completer=PayeeCompleter(handler, suggestions),
        complete_while_typing=True,
        complete_in_thread=True,
        **kwargs
    )

    return session.prompt(default=payee, accept_default=False, **kwargs)


def narration_prompt(
    handler, narration=None, suggestions=None, message="Enter narration: ", **kwargs
):
    if narration is None:
        narration = ""

    session = PromptSession(
        message=message,
        history=FileHistory(_NARRATION_CACHE),
        placeholder="e.g. Bus to city",
        completer=NarrationCompleter(handler, suggestions),
        complete_while_typing=True,
        complete_in_thread=True,
        **kwargs
    )

    return session.prompt(default=narration, accept_default=False, **kwargs)


def payment_prompt(handler, payment=None, message="Enter value: ", **kwargs):
    if payment is None:
        payment = ""

    payment_validator = ThreadedValidator(
        Validator.from_callable(
            handler.valid_payment,
            error_message="Invalid format; must be '<value> <currency>'",
        )
    )

    session = PromptSession(
        message=message,
        history=FileHistory(_PAYMENT_CACHE),
        placeholder="e.g. -1.23 EUR",
        validator=payment_validator,
        validate_while_typing=True,
        **kwargs
    )

    payment = session.prompt(default=payment, accept_default=False, **kwargs)
    return handler.parse_payment(payment)


def split_fraction_prompt(
    handler, fraction=None, message="Choose split fraction: ", **kwargs
):
    if fraction is None:
        fraction = ""

    fraction_validator = ThreadedValidator(
        Validator.from_callable(
            handler.valid_fraction, error_message="Invalid fraction"
        )
    )

    session = PromptSession(
        message=message,
        history=FileHistory(_FRACTION_CACHE),
        placeholder="e.g. -0.5",
        validator=fraction_validator,
        validate_while_typing=True,
        **kwargs
    )

    fraction = session.prompt(default=str(fraction), accept_default=False, **kwargs)
    return handler.parse_fraction(fraction)


class LevenshteinDistanceCompleter(Completer, metaclass=abc.ABCMeta):
    """Completer that uses Levenshtein Distance to compute matches

    This completer offers better (e.g. typo-forgiving) matching over prompt_toolkit's
    FuzzyCompleter.
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
            document.text_before_cursor, self.possibilities, limit=20
        ):
            yield Completion(
                possibility, start_position=-len(document.text_before_cursor)
            )


class AccountCompleter(LevenshteinDistanceCompleter):
    @property
    def possibilities(self):
        return [account.account for account in self.handler.accounts]


class PayeeCompleter(LevenshteinDistanceCompleter):
    @property
    def possibilities(self):
        return self.handler.payees


class NarrationCompleter(LevenshteinDistanceCompleter):
    @property
    def possibilities(self):
        return self.handler.narrations
