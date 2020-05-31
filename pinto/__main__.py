"""Pinto CLI"""

import click
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
    TRANSACTION_DATE_FORMAT,
    get_templates,
    get_template,
    get_accounts,
    align_transaction_files,
    check_transaction_dates,
    add_transaction,
    TemplateNotFoundError,
)
from .transactions import Transaction

TRANSACTION_PATH_TYPE = click.Path(exists=True, file_okay=False, writable=True)
TRANSACTION_PATH_ENVVAR = "BEANCOUNT_TRANSACTION_DIR"
TRANSACTION_PATH_HELP = (
    "Beancount transaction file directory. If not specified, "
    f"the environment variable {TRANSACTION_PATH_ENVVAR} is "
    "searched."
)


def add_linedata(
    transaction, account=None, value=None, no_value=False, splits=None, do_split=False
):
    """Validate/prompt user for linedata."""
    taccount = _get_valid_account_list_or_string(
        account, allow_other=True, msg="Choose account"
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
    transaction.add_line(account=taccount, value=tvalue, currency=tcurrency)
    # Get splits.
    if not no_value and tvalue is not None and do_split:
        if splits is not None:
            # Splits defined by template.
            for splitno, split in enumerate(splits, start=1):
                add_splitdata(transaction, taccount, tvalue, tcurrency, **split)
        else:
            splitno = 1
            splitting = click.confirm("Add split?", default=False)
            while splitting:
                echo_info_params("Adding split {}...", [splitno])
                add_splitdata(transaction, taccount, tvalue, tcurrency)
                splitting = click.confirm("Add another split?", default=False)
                splitno += 1


def add_splitdata(transaction, taccount, tvalue, tcurrency, account=None, value=-0.5):
    saccount = _get_valid_account_list_or_string(
        account, msg=f"Choose split account for {taccount}"
    )
    echo_info_params("Split account will be {}", [saccount])
    fraction = get_valid_fraction(None, msg="Choose split fraction", default=value)
    svalue = tvalue * fraction
    trvalue = f"{round(tvalue, 2):.2f}"
    srvalue = f"{round(svalue, 2):.2f}"
    if svalue != 0:
        echo_info_params(
            f"{{}} {{}} will be split into {{}} with value {{}} {{}}",
            [trvalue, tcurrency, saccount, srvalue, tcurrency],
        )
        transaction.add_line(account=saccount, value=svalue, currency=tcurrency)
    else:
        echo_info("Zero value split ignored")


def _get_valid_account_list_or_string(account_or_choices, **kwargs):
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
    return get_valid_account(account=account, choices=choices, **kwargs)


@click.group(help="Beancount tools.")
def tools():
    pass


@tools.command()
@click.option("-t", "--template", type=str, help="Transaction template.")
@click.option(
    "-d",
    "--directory",
    type=TRANSACTION_PATH_TYPE,
    envvar=TRANSACTION_PATH_ENVVAR,
    help=TRANSACTION_PATH_HELP,
)
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
def add(template, directory, date, payee, narration, tag, split, dry_run):
    """Add transaction"""
    if template is not None:
        try:
            template = get_template(template)
        except TemplateNotFoundError:
            exit_error(f"Template '{template}' not found")
    else:
        template = {}

    if directory is None:
        exit_error(
            f"--directory or environment variable {TRANSACTION_PATH_ENVVAR} "
            "must not be empty."
        )

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
        template.get("payee", payee), msg="Enter transaction payee"
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

    transaction = Transaction(date=tdate, narration=tnarration, payee=tpayee, tag=tag)

    if "lines" in template:
        # Lines defined by template.
        total = len(template["lines"])
        for lineno, line in enumerate(template["lines"], start=1):
            echo_info_params("Adding line {} of {}...", [lineno, total])
            add_linedata(transaction, do_split=split, **line)
        if total < 2:
            # Always prompt for at least 2 lines.
            echo_info("Template provides only one line; adding second.")
            add_linedata(transaction, do_split=split)
    else:
        new_line = True
        lineno = 1
        while new_line:
            echo_info_params("Adding line {}...", [lineno])
            add_linedata(transaction, do_split=split)
            # Always prompt for at least 2 lines.
            if lineno >= 2:
                new_line = click.confirm("Add another line?", default=False)
            lineno += 1

    echo_info("Draft transaction:")
    echo_info(transaction.posting, bold=True)
    if click.confirm("Commit?"):
        if not dry_run:
            add_transaction(transaction)
        echo_info("Committed!")
    else:
        exit_error("The transaction did not proceed.")


@tools.command()
@click.option("-s", "--search", type=str, help="Label filter. Case insensitive.")
@click.option(
    "-n", type=int, default=5, help="Maximum number of partial matches to return."
)
def templates(search, n):
    """Search templates."""
    for template, _ in get_templates(search, limit=n):
        click.secho(template, fg="green")


@tools.command()
@click.option("-s", "--search", type=str, help="Account filter. Case insensitive.")
@click.option(
    "-n", type=int, default=5, help="Maximum number of partial matches to return."
)
def accounts(search, n):
    """Search accounts."""
    for account, _ in get_accounts(search, limit=n):
        click.secho(account, fg="green")


@tools.command()
@click.option("-p", "--prefix-width", default=4, help="Use this prefix width.")
@click.option(
    "-c", "--currency-column", default=90, help="Align currencies in this column."
)
@click.option(
    "--backup/--no-backup",
    is_flag=True,
    default=False,
    help="Backup transactions before formatting.",
)
def format(prefix_width, currency_column, backup):
    """Format transaction files."""
    align_transaction_files(
        prefix_width=prefix_width, currency_column=currency_column, backup=backup
    )


@tools.command()
def check_dates():
    """Check transaction dates are ordered and in the correct file."""
    check_transaction_dates()


if __name__ == "__main__":
    tools()
