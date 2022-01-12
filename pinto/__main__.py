"""Pinto CLI"""

import click
from beancount.core.data import Transaction, new_metadata, create_simple_posting
from . import __version__, PROGRAM
from .cli import (
    exit_error,
    echo_info,
    echo_info_params,
    echo_warning,
    echo_warning_params,
    get_valid_string,
    get_valid_date,
    prompt_choice,
    get_valid_payment,
    get_valid_fraction,
)
from .tools import (
    ACCOUNT_DIR_ENVVAR,
    TRANSACTION_DATE_FORMAT,
    TRANSACTION_DATE_LONG_FORMAT,
    AccountHandler,
    TemplateNotFoundError,
    TemplateFileNotSet,
    serialise_entry,
)


def _add_linedata(
    handler,
    transaction,
    account=None,
    value=None,
    no_value=False,
    splits=None,
    do_split=False,
):
    """Validate/prompt user for linedata."""
    taccount = _prompt_account(handler, account, allow_other=True)
    echo_info_params("Account will be {}", [taccount])

    # Get posting value.
    if not no_value:
        # Use value defined in template if present.
        tvalue, tcurrency = get_valid_payment(
            value, msg="Enter value", force_once=True, allow_empty=True
        )
    else:
        # Valueless line.
        tvalue = None
        tcurrency = None

    # Create a copy that we format as a value.
    trvalue = tvalue

    if trvalue is not None:
        # Convert value to rounded string.
        trvalue = f"{round(tvalue, 2):.2f}"

        echo_info_params("Value will be {} {}", [trvalue, tcurrency])
    else:
        echo_info("Value will be empty")

    # Add line.
    create_simple_posting(
        transaction, account=taccount, number=trvalue, currency=tcurrency
    )

    # Get splits.
    if not no_value and tvalue is not None and do_split:
        if splits is not None:
            # Splits defined by template.
            for _, split in enumerate(splits, start=1):
                _add_splitdata(
                    handler, transaction, taccount, tvalue, tcurrency, **split
                )
        else:
            splitno = 1
            splitting = click.confirm("Add split?", default=False)

            while splitting:
                echo_info_params("Adding split {}...", [splitno])
                _add_splitdata(handler, transaction, taccount, tvalue, tcurrency)
                splitting = click.confirm("Add another split?", default=False)
                splitno += 1


def _add_splitdata(
    handler, transaction, taccount, tvalue, tcurrency, account=None, value=-0.5
):
    saccount = _prompt_account(
        handler, account, msg=f"Choose split account for {taccount}"
    )
    echo_info_params("Split account will be {}", [saccount])
    fraction = get_valid_fraction(None, msg="Choose split fraction", default=value)
    svalue = tvalue * fraction
    # Convert values to rounded strings.
    trvalue = f"{round(tvalue, 2):.2f}"
    srvalue = f"{round(svalue, 2):.2f}"

    if svalue != 0:
        echo_info_params(
            "{} {} will be split into {} with value {} {}",
            [trvalue, tcurrency, saccount, srvalue, tcurrency],
        )

        # Add line.
        create_simple_posting(
            transaction, account=saccount, number=srvalue, currency=tcurrency
        )
    else:
        echo_info("Zero value split ignored")


def _ensure_list(item):
    """Ensure `item` is a list. If it's a string, it's converted into a 1-item list."""
    if item is None:
        item = []
    elif isinstance(item, str):
        item = [item]
    return list(item)


def _prompt_account(handler, choices, msg="Enter account", **kwargs):
    """Prompt user for a choice of account, where `choices` can be a single string or
    list of strings."""
    return prompt_choice(
        choices=_ensure_list(choices),
        msg=msg,
        error_msg="Non-unique or invalid account.",
        validator=handler.unique_account,
        **kwargs,
    )


def _prompt_payee(
    handler,
    msg="Enter transaction payee",
    error_msg="Non-unique or invalid payee.",
    **kwargs,
):
    """Prompt user for a choice of payee."""
    return prompt_choice(
        msg=msg, error_msg=error_msg, validator=handler.unique_payee, **kwargs
    )


def _set_account_path(ctx, _, value):
    handler = ctx.ensure_object(AccountHandler)

    if value is None:
        exit_error(
            f"--accounts or environment variable {ACCOUNT_DIR_ENVVAR} "
            "must not be empty."
        )

    handler.accounts_path = value


@click.group(name="pinto", help="Beancount tools.")
@click.option(
    "--accounts",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, writable=True),
    envvar=ACCOUNT_DIR_ENVVAR,
    callback=_set_account_path,
    expose_value=False,
    help=(
        f"Accounts directory. If not specified, the environment variable "
        f"{ACCOUNT_DIR_ENVVAR} is searched."
    ),
)
@click.version_option(version=__version__, prog_name=PROGRAM)
@click.pass_context
def pinto(ctx):
    handler = ctx.ensure_object(AccountHandler)

    if handler.accounts_path is None:
        exit_error(
            f"Accounts path not found. Either --accounts or the environment variable "
            f"{ACCOUNT_DIR_ENVVAR} must be set."
        )


@pinto.command(name="add")
@click.option("-t", "--template", type=str, help="Transaction template.")
@click.option("-d", "--date", type=str, help="Transaction date.")
@click.option(
    "-p", "--payee", type=str, help="Transaction payee.",
)
@click.option("-n", "--narration", type=str, help="Transaction narration.")
@click.option("--tag", type=str, help="Transaction tag.")
@click.option("--split/--no-split", is_flag=True, default=False, help="Offer splits.")
@click.option(
    "-f",
    "--force-prompts",
    is_flag=True,
    default=False,
    help="Force prompts for transaction details, even if the template specifies them.",
)
@click.option(
    "--dry-run", is_flag=True, default=False, help="Make no changes to files."
)
@click.pass_context
def add_transaction(
    ctx, template, date, payee, narration, tag, split, force_prompts, dry_run
):
    """Add new transaction."""
    handler = ctx.ensure_object(AccountHandler)

    if template is not None:
        try:
            template = handler.get_template(template)
        except TemplateNotFoundError:
            exit_error(f"Template '{template}' not found")
    else:
        template = {}

    if dry_run:
        echo_warning("This will be a dry run")

    ## Get/validate transaction parameters.

    # Date.
    tdate = get_valid_date(template.get("date", date))
    echo_info_params(
        "Date will be {} ({})",
        [
            tdate.strftime(TRANSACTION_DATE_FORMAT),
            tdate.strftime(TRANSACTION_DATE_LONG_FORMAT),
        ],
        nl=False,
    )

    # Payee.
    template_payees = _ensure_list(template.get("payee"))
    if payee:
        if force_prompts:
            tpayee = _prompt_payee(
                handler, choices=template_payees, existing_choice=payee
            )
        else:
            # Use the payee passed as an option.
            tpayee = payee

            if template_payees:
                echo_warning_params(
                    "Ignoring {} template payee(s) and instead using {}",
                    [len(template_payees), payee],
                )
    else:
        tpayee = _prompt_payee(handler, choices=template_payees)

    if tpayee:
        echo_info_params("Payee will be {}", [tpayee])
    else:
        echo_info("No payee")

    # Narration.
    tnarration = get_valid_string(
        template.get("narration", narration),
        msg="Enter transaction narration",
        minlen=0,
        force_once="narration" not in template,
        allow_empty=True,
    )

    if tnarration:
        echo_info_params("Narration will be {}", [tnarration])
    else:
        echo_info("No narration")

    # Tag.
    tags = [tag] if tag is not None else []

    transaction = Transaction(
        meta=new_metadata("/dev/stdin", 0),
        date=tdate,
        flag="*",
        payee=tpayee,
        narration=tnarration,
        tags=tags,
        links=[],
        postings=[],
    )

    if "lines" in template:
        # Lines defined by template.
        total = len(template["lines"])

        for lineno, line in enumerate(template["lines"], start=1):
            echo_info_params("Adding line {} of {}...", [lineno, total])
            _add_linedata(handler, transaction, do_split=split, **line)
        if total < 2:
            # Always prompt for at least 2 lines.
            echo_info("Template provides only one line; adding second.")
            _add_linedata(handler, transaction, do_split=split)
    else:
        new_line = True
        lineno = 1

        while new_line:
            echo_info_params("Adding line {}...", [lineno])
            _add_linedata(handler, transaction, do_split=split)

            # Always prompt for at least 2 lines.
            if lineno >= 2:
                new_line = click.confirm("Add another line?", default=False)
            lineno += 1

    echo_info("Draft transaction:")
    echo_info(serialise_entry(transaction), bold=True)

    if click.confirm("Commit?"):
        if not dry_run:
            handler.add_entry(transaction)
        echo_info("Committed!")
    else:
        exit_error("The transaction did not proceed.")


@pinto.command(name="import")
@click.argument(
    "file", type=click.Path(exists=True, dir_okay=False, file_okay=True),
)
@click.pass_context
def import_transactions(ctx, file):
    """Import transactions."""
    handler = ctx.ensure_object(AccountHandler)
    transactions = handler.ingest_transactions(file)
    count = len(transactions)

    for i, transaction in enumerate(transactions, start=1):
        echo_info_params(
            'Handling import {}/{}: {} "{}"',
            [
                i,
                count,
                transaction.date.strftime(TRANSACTION_DATE_FORMAT),
                transaction.payee,
            ],
        )

        echo_info_params("{} existing line(s):", [len(transaction.postings)])

        for posting in transaction.postings:
            echo_info_params("{} {} {}", [posting.account, posting.cost, posting.units])

        new_line = True
        lineno = 2

        while new_line:
            echo_info_params("Adding line {}...", [lineno])
            _add_linedata(handler, transaction)
            new_line = click.confirm("Add another line?", default=False)
            lineno += 1


@pinto.group(name="search")
def search():
    """Search account files."""
    pass


@search.command(name="templates")
@click.argument("search", type=str)
@click.option(
    "-n", type=int, default=5, help="Maximum number of partial matches to return."
)
@click.pass_context
def search_templates(ctx, search, n):
    """Search templates.

    Partial matches are made automatically. The search term is case-insensitive.
    """
    handler = ctx.ensure_object(AccountHandler)

    try:
        found = handler.search_templates(search, limit=n)
    except TemplateFileNotSet:
        exit_error(
            f"Templates file path not found. Ensure there is a 'templates.yaml' file "
            f"in {str(handler.accounts_dir.resolve())}."
        )

    for template, _ in found:
        click.secho(template, fg="green")


@search.command(name="accounts")
@click.argument("search", type=str)
@click.option(
    "-n", type=int, default=5, help="Maximum number of partial matches to return."
)
@click.pass_context
def search_accounts(ctx, search, n):
    """Search accounts.

    Partial matches are made automatically. The search term is case-insensitive.
    """
    handler = ctx.ensure_object(AccountHandler)
    found = handler.search_accounts(search, limit=n)

    for account, _ in found:
        click.secho(account, fg="green")


@search.command(name="payees")
@click.argument("search", type=str)
@click.option(
    "-n", type=int, default=5, help="Maximum number of partial matches to return."
)
@click.pass_context
def search_payees(ctx, search, n):
    """Search payees.

    Partial matches are made automatically. The search term is case-insensitive.
    """
    handler = ctx.ensure_object(AccountHandler)
    found = handler.search_payees(search, limit=n)

    for payee, _ in found:
        click.secho(payee, fg="green")


@pinto.group(name="format")
def format():
    """Format account files."""
    pass


@format.command(name="transactions")
@click.option(
    "-p", "--prefix-width", default=4, show_default=True, help="Use this prefix width."
)
@click.option(
    "-c",
    "--currency-column",
    default=90,
    show_default=True,
    help="Align currencies in this column.",
)
@click.option(
    "--backup/--no-backup",
    is_flag=True,
    default=True,
    show_default=True,
    help="Backup transactions before formatting.",
)
@click.pass_context
def format_transactions(ctx, prefix_width, currency_column, backup):
    """Format transaction file."""
    handler = ctx.ensure_object(AccountHandler)
    handler.format_transactions(
        prefix_width=prefix_width, currency_column=currency_column, backup=backup,
    )


@pinto.group(name="check")
def check():
    """Check account files for various issues."""
    pass


@check.command(name="syntax")
@click.pass_context
def check_syntax(ctx):
    """Check account syntax is correct."""
    handler = ctx.ensure_object(AccountHandler)

    try:
        handler.check_syntax()
    except ValueError as e:
        exit_error(str(e))


@check.command(name="transaction-dates")
@click.pass_context
def check_transaction_dates(ctx):
    """Check transactions are correctly ordered by date."""
    handler = ctx.ensure_object(AccountHandler)

    try:
        handler.check_date_order()
    except ValueError as e:
        exit_error(str(e))


if __name__ == "__main__":
    pinto()
