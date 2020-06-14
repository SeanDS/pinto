"""Pinto CLI"""

import click
from beancount.core.data import Transaction, new_metadata, create_simple_posting
from . import __version__, PROGRAM
from .cli import (
    exit_error,
    echo_info,
    echo_info_params,
    echo_warning,
    get_valid_string,
    get_valid_date,
    get_valid_payee,
    get_valid_account,
    get_valid_payment,
    get_valid_fraction,
)
from .tools import (
    ACCOUNT_DIR_ENVVAR,
    TRANSACTION_DATE_FORMAT,
    AccountHandler,
    TemplateNotFoundError,
    TemplateFileNotSet,
    serialise_entry,
)


def add_linedata(
    handler,
    transaction,
    account=None,
    value=None,
    no_value=False,
    splits=None,
    do_split=False,
):
    """Validate/prompt user for linedata."""
    taccount = _get_valid_account_list_or_string(
        handler, account, allow_other=True, msg="Choose account"
    )
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

    if tvalue is not None:
        echo_info_params("Value will be {} {}", [f"{tvalue:.2f}", tcurrency])
    else:
        echo_info("Value will be empty")

    # Add line.
    create_simple_posting(
        transaction, account=taccount, number=tvalue, currency=tcurrency
    )

    # Get splits.
    if not no_value and tvalue is not None and do_split:
        if splits is not None:
            # Splits defined by template.
            for _, split in enumerate(splits, start=1):
                add_splitdata(
                    handler, transaction, taccount, tvalue, tcurrency, **split
                )
        else:
            splitno = 1
            splitting = click.confirm("Add split?", default=False)

            while splitting:
                echo_info_params("Adding split {}...", [splitno])
                add_splitdata(handler, transaction, taccount, tvalue, tcurrency)
                splitting = click.confirm("Add another split?", default=False)
                splitno += 1


def add_splitdata(
    handler, transaction, taccount, tvalue, tcurrency, account=None, value=-0.5
):
    saccount = _get_valid_account_list_or_string(
        handler, account, msg=f"Choose split account for {taccount}"
    )
    echo_info_params("Split account will be {}", [saccount])
    fraction = get_valid_fraction(None, msg="Choose split fraction", default=value)
    svalue = tvalue * fraction
    trvalue = f"{round(tvalue, 2):.2f}"
    srvalue = f"{round(svalue, 2):.2f}"

    if svalue != 0:
        echo_info_params(
            f"{trvalue} {tcurrency} will be split into {saccount} with value "
            f"{srvalue} {tcurrency}"
        )

        # Add line.
        create_simple_posting(
            transaction, account=saccount, number=svalue, currency=tcurrency
        )
    else:
        echo_info("Zero value split ignored")


def _get_valid_account_list_or_string(handler, account_or_choices, **kwargs):
    """Deal with accounts defined either as strings or list of strings in YAML."""
    # Get account.
    account = None
    choices = None
    if account_or_choices is not None:
        if isinstance(account_or_choices, str):
            account_or_choices = [account_or_choices]
        try:
            choices = list(account_or_choices)
        except TypeError:
            raise ValueError("account must be string or iterable")
        if len(choices) == 1:
            account = choices[0]
            choices = None
    return get_valid_account(handler, account=account, choices=choices, **kwargs)


def set_account_path(ctx, _, value):
    handler = ctx.ensure_object(AccountHandler)

    if value is None:
        exit_error(
            f"--accounts or environment variable {ACCOUNT_DIR_ENVVAR} "
            "must not be empty."
        )

    handler.accounts_path = value


def set_template_path(ctx, _, value):
    """Set account for this session."""
    handler = ctx.ensure_object(AccountHandler)
    handler.template_path = value


@click.group(help="Beancount tools.")
@click.option(
    "--accounts",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, writable=True),
    envvar=ACCOUNT_DIR_ENVVAR,
    callback=set_account_path,
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


@pinto.command()
@click.option("-t", "--template", type=str, help="Transaction template.")
@click.option("-d", "--date", type=str, help="Transaction date.")
@click.option(
    "-p", "--payee", type=str, help="Transaction payee.",
)
@click.option("-n", "--narration", type=str, help="Transaction narration.")
@click.option("--tag", type=str, help="Transaction tag.")
@click.option("--split/--no-split", is_flag=True, default=False, help="Offer splits.")
@click.option(
    "--dry-run", is_flag=True, default=False, help="Make no changes to files."
)
@click.pass_context
def add(ctx, template, date, payee, narration, tag, split, dry_run):
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
        "Date will be {}", [tdate.strftime(TRANSACTION_DATE_FORMAT)], nl=False
    )
    # Payee.
    tpayee = get_valid_payee(
        handler, template.get("payee", payee), msg="Enter transaction payee"
    )
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
            add_linedata(handler, transaction, do_split=split, **line)
        if total < 2:
            # Always prompt for at least 2 lines.
            echo_info("Template provides only one line; adding second.")
            add_linedata(handler, transaction, do_split=split)
    else:
        new_line = True
        lineno = 1
        while new_line:
            echo_info_params("Adding line {}...", [lineno])
            add_linedata(handler, transaction, do_split=split)
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


@pinto.group()
def search():
    """Search account files."""
    pass


@search.command()
@click.argument("search", type=str)
@click.option(
    "-n", type=int, default=5, help="Maximum number of partial matches to return."
)
@click.pass_context
def templates(ctx, search, n):
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


@search.command()
@click.argument("search", type=str)
@click.option(
    "-n", type=int, default=5, help="Maximum number of partial matches to return."
)
@click.pass_context
def accounts(ctx, search, n):
    """Search accounts.

    Partial matches are made automatically. The search term is case-insensitive.
    """
    handler = ctx.ensure_object(AccountHandler)
    found = handler.search_accounts(search, limit=n)

    for account, _ in found:
        click.secho(account, fg="green")


@search.command()
@click.argument("search", type=str)
@click.option(
    "-n", type=int, default=5, help="Maximum number of partial matches to return."
)
@click.pass_context
def payees(ctx, search, n):
    """Search payees.

    Partial matches are made automatically. The search term is case-insensitive.
    """
    handler = ctx.ensure_object(AccountHandler)
    found = handler.search_payees(search, limit=n)

    for payee, _ in found:
        click.secho(payee, fg="green")


@pinto.group()
def format():
    """Format account files."""
    pass


@format.command()
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
def transactions(ctx, prefix_width, currency_column, backup):
    """Format transaction file."""
    handler = ctx.ensure_object(AccountHandler)
    handler.format_transactions(
        prefix_width=prefix_width, currency_column=currency_column, backup=backup,
    )


@pinto.group()
def check():
    """Check account files for various issues."""
    pass


@check.command()
@click.pass_context
def syntax(ctx):
    """Check account syntax is correct."""
    handler = ctx.ensure_object(AccountHandler)

    try:
        handler.check_syntax()
    except ValueError as e:
        exit_error(str(e))


@check.command()
@click.pass_context
def transaction_dates(ctx):
    """Check transactions are correctly ordered by date."""
    handler = ctx.ensure_object(AccountHandler)

    try:
        handler.check_date_order()
    except ValueError as e:
        exit_error(str(e))


if __name__ == "__main__":
    pinto()
