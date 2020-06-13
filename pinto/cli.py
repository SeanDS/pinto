"""CLI tools"""

import sys
from itertools import zip_longest
import click
import maya
from .tools import DegenerateChoiceException


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


def get_valid_string(cur, msg, minlen=1, force_once=False, allow_empty=False):
    def validate(string):
        if string is None or string == "":
            return allow_empty
        if len(string) < minlen:
            recoverable_error(f"Minimum length is {minlen}")
            return False
        return True

    kwargs = {}

    if allow_empty:
        kwargs["default"] = ""

    while force_once or not validate(cur):
        cur = click.prompt(msg, type=str, **kwargs)
        force_once = False
    if allow_empty and cur is None or cur == "":
        return ""
    return cur


def get_valid_payee(
    handler, payee=None, choices=None, allow_other=True, msg="Enter transaction payee"
):
    def prompt_numeric_choice_with_user_choice(pchoices, user_choice=None):
        if user_choice is not None:
            pchoices.insert(0, user_choice)

        if len(pchoices) == 1:
            choice = pchoices[0]
        else:
            choice = prompt_numeric_choice(msg, pchoices)
        return choice

    while True:
        if choices is not None:
            payee = prompt_numeric_choice_with_user_choice(choices)
        while True:
            try:
                payee = handler.unique_payee(payee)
            except DegenerateChoiceException as e:
                if payee is not None:
                    recoverable_error("Non-unique or invalid payee.")
                    user_payee = payee
                    payee = prompt_numeric_choice_with_user_choice(
                        e.closest_matches(4), user_payee
                    )

                    if payee == user_payee:
                        return user_payee
                else:
                    payee = click.prompt(msg, type=str)
            else:
                break
        break

    return payee


def get_valid_date(date, msg="Enter transaction date"):
    dateval = date
    while True:
        try:
            if dateval is None:
                dateval = click.prompt(msg, default="today")
            date = maya.when(dateval).datetime().date()
        except ValueError:
            continue
        else:
            break
    return date


def get_valid_account(
    handler, account=None, choices=None, allow_other=True, msg="Enter account"
):
    def prompt_numeric_choice_with_other(pchoices):
        otherstr = "Other"
        if pchoices is not None and allow_other:
            if otherstr in pchoices:
                raise Exception(
                    f"Choice value cannot be '{otherstr}' (used internally)"
                )
            pchoices.append(otherstr)
        if len(pchoices) == 1:
            naccount = pchoices[0]
        else:
            naccount = prompt_numeric_choice(msg, pchoices)
        if allow_other and naccount == otherstr:
            naccount = click.prompt(msg, type=str)
        return naccount

    while True:
        if choices is not None:
            account = prompt_numeric_choice_with_other(choices)
        while True:
            try:
                account = handler.unique_account(account)
            except DegenerateChoiceException as e:
                if account is not None:
                    recoverable_error("Non-unique or invalid account.")
                    account = prompt_numeric_choice_with_other(e.closest_matches())
                else:
                    account = click.prompt(msg, type=str)
            else:
                break
        break

    return account


def prompt_numeric_choice(msg, choices, **kwargs):
    """Prompt user to choose from a list of choices by number."""
    choicetype = NumericChoice(choices, case_sensitive=False)
    return click.prompt(msg, type=choicetype, default=None, **kwargs)


def get_valid_payment(payment, msg, force_once=False, allow_empty=False):
    def validate(payment):
        if payment is None or payment == "":
            return allow_empty
        pieces = payment.split()
        if len(pieces) != 2:
            msg = "Invalid format. Must be [value] [currency]."
            recoverable_error(msg)
            return False
        return True

    kwargs = {}

    if allow_empty:
        kwargs["default"] = ""

    while force_once or not validate(payment):
        payment = click.prompt(msg, type=str, **kwargs)
        force_once = False
    if allow_empty and payment is None or payment == "":
        return None, None
    value, currency = payment.split()
    value = float(value)
    return value, currency


def get_valid_fraction(fraction, msg, **kwargs):
    while True:
        try:
            fraction = float(fraction)
        except ValueError:
            fraction = click.prompt(msg, **kwargs)
        else:
            break
    return fraction


class NumericChoice(click.Choice):
    def __init__(self, choices, **kwargs):
        choicepairs = []
        choicestrs = []
        for i, choice in enumerate(choices, start=1):
            choicepairs.append((str(i), choice))
            choicestrs.append(f"[{i}] {choice}")
        self.choicemap = dict(choicepairs)
        super().__init__(choicestrs, **kwargs)

    def convert(self, value, param, ctx):
        try:
            return self.choicemap[value]
        except KeyError:
            self.fail(
                "invalid choice: %s. (choose from %s)"
                % (value, ", ".join(self.choices)),
                param,
                ctx,
            )
