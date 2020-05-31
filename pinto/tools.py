"""Script tools."""

import os
import glob
from pathlib import Path
import yaml
from fuzzywuzzy import process
from beancount.loader import load_file
from beancount.core.data import Open
from .transactions import TransactionFile

TRANSACTION_FILEDATE_FORMAT = "%Y-%m"
TRANSACTION_DATE_FORMAT = "%Y-%m-%d"
ROOT_DIR = Path(__file__).resolve().parent.parent
TRANSACTION_DIR = ROOT_DIR / "transactions"
TEMPLATE_FILE = TRANSACTION_DIR / "templates.yaml"
ACCOUNT_FILE = ROOT_DIR / "accounts.beancount"
TRANSACTION_FILE_WILDCARD = TRANSACTION_DIR / "*.beancount"
TRANSACTION_FILE_BACKUP_DIR = TRANSACTION_DIR / ".backup"


class TemplateNotFoundError(ValueError):
    pass


class NoCompatibleTransactionFile(ValueError):
    pass


class DegenerateChoiceException(ValueError):
    def __init__(self, *args, search=None, matches=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.search = search
        self.matches = matches

    def closest_matches(self, count=5):
        return [match for match, _ in self.matches[:count]]


def transaction_file_paths(include_meta=False):
    for path in sorted(glob.glob(str(TRANSACTION_FILE_WILDCARD))):
        if not include_meta and os.path.basename(path).startswith("0000"):
            continue
        yield path


def _fuzzy_match(candidates, search_term=None, limit=None):
    if search_term is None:
        return [(candidate, 1) for candidate in list(candidates)[:limit]]

    return process.extract(search_term, candidates, limit=limit)


def all_templates():
    with open(TEMPLATE_FILE, "r") as templatefile:
        templates = yaml.safe_load(templatefile)
    return templates


def get_templates(search_term=None, templates=None, **kwargs):
    if templates is None:
        templates = all_templates().keys()

    return _fuzzy_match(templates, search_term=search_term, **kwargs)


def get_template(label):
    templates = all_templates()
    try:
        template = templates[label]
    except KeyError:
        raise TemplateNotFoundError("Template not found")
    template["label"] = label
    return template


def has_template(label):
    try:
        get_template(label)
    except ValueError:
        return False
    return True


def get_payees(search_term=None, payees=None, **kwargs):
    if payees is None:
        payees = set(
            [
                transaction.payee
                for transaction in all_transactions()
                if transaction.payee
            ]
        )

    return _fuzzy_match(payees, search_term=search_term, **kwargs)


def get_unique_payee(search, **kwargs):
    matches = list(get_payees(search, **kwargs))
    if len(matches) == 1:
        return matches[0][0]
    # Check if exact match exists.
    if search is not None:
        lsearch = search.strip().lower()
        for match in matches:
            string = match[0]
            if lsearch == string.strip().lower():
                return string
    raise DegenerateChoiceException(
        f"Non-unique payee '{search}'", search=search, matches=matches
    )


def all_accounts():
    entries, _, _ = load_file(str(ACCOUNT_FILE))
    for entry in entries:
        if not isinstance(entry, Open):
            continue
        yield entry


def get_accounts(search_term=None, accounts=None, **kwargs):
    if accounts is None:
        accounts = [account.account for account in all_accounts()]

    return _fuzzy_match(accounts, search_term=search_term, **kwargs)


def get_unique_account(search, **kwargs):
    matches = list(get_accounts(search, **kwargs))
    if len(matches) == 1:
        return matches[0][0]
    # Check if exact match exists.
    if search is not None:
        lsearch = search.strip().lower()
        for match in matches:
            string = match[0]
            if lsearch == string.strip().lower():
                return string
    raise DegenerateChoiceException(
        f"Non-unique account '{search}'", search=search, matches=matches
    )


def get_transaction_files(**kwargs):
    for path in transaction_file_paths(**kwargs):
        transactions = TransactionFile(path)
        transactions.load()
        yield transactions


def get_file_for_transaction(transaction):
    for transactions in get_transaction_files():
        if transactions.date_compatible(transaction.date):
            return transactions
    raise NoCompatibleTransactionFile("No transaction file compatible.")


def align_transaction_files(backup=False, **kwargs):
    for transactions in get_transaction_files(include_meta=True):
        if backup:
            backup_path = TRANSACTION_FILE_BACKUP_DIR / transactions.basename
            transactions.backup(backup_path)
        transactions.align(**kwargs)


def all_transactions():
    for tfile in get_transaction_files():
        yield from tfile.transactions


def check_transaction_dates():
    for transactions in get_transaction_files():
        transactions.check_date_order()


def add_transaction(transaction):
    try:
        transactions = get_file_for_transaction(transaction)
    except NoCompatibleTransactionFile:
        # Transaction file must be created.
        transactions = TransactionFile.create_from_date(
            transaction.date, TRANSACTION_DIR
        )
    transactions.add(transaction)


def match_statement_transaction(stmt_t, flag=None):
    # Find matching values.
    for transaction in all_transactions():
        if flag is not None and transaction.flag != flag:
            continue

        for posting in transaction.postings:
            if float(posting.units.number) in [stmt_t.debit, stmt_t.credit]:
                yield transaction
