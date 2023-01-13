"""Script tools."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from functools import cached_property
from collections import Counter
import locale
import dateparser
import yaml
from thefuzz import process
from beancount.loader import load_file
from beancount.core import data
from beancount.parser import printer

ACCOUNT_DIR_ENVVAR = "PINTO_DIR"
TRANSACTION_DATE_FORMAT = "%Y-%m-%d"
TRANSACTION_DATE_LONG_FORMAT = "%a %d %b %Y"


def fuzzy_match(candidates, search_term=None, limit=None):
    if search_term is None:
        return [(candidate, 1) for candidate in list(candidates)[:limit]]

    return process.extract(search_term, candidates, limit=limit)


def ranked_set(items):
    """Get set of `items` ranked in descending order of number of appearances."""
    counts = Counter(items)
    return sorted(counts, key=counts.get, reverse=True)


def serialise_entry(entry):
    return printer.format_entry(entry)


class TemplateFileNotSet(ValueError):
    """Template file not set."""


class TemplateNotFoundError(ValueError):
    """Template name not found."""


class AccountHandler:
    def __init__(self):
        self._accounts_path = None

    @property
    def accounts_path(self):
        return self._accounts_path

    @accounts_path.setter
    def accounts_path(self, path):
        self._accounts_path = Path(path)

    @property
    def accounts_file(self):
        return self.accounts_path / "main.beancount"

    @property
    def transactions_file(self):
        return self.accounts_path / "transactions.beancount"

    @property
    def transaction_backup_file(self):
        return self.transactions_file.with_suffix(
            self.transactions_file.suffix + ".backup"
        )

    @property
    def template_path(self):
        return self.accounts_path / "templates.yaml"

    @property
    def importers_config_path(self):
        return self.accounts_path / "importers.py"

    @cached_property
    def transactions(self):
        """All transactions found at the account path."""
        entries, _, _ = load_file(self.accounts_file)
        return tuple(data.filter_txns(entries))

    def filter_transactions(self, payee=None, narration=None):
        """Filter transactions by their metadata.

        Transactions must match all non-None parameters.
        """
        for transaction in self.transactions:
            if payee is not None and transaction.payee != payee:
                continue

            if narration is not None and transaction.narration != narration:
                continue

            yield transaction

    def filter_narrations(self, **kwargs):
        """Get narrations for transactions by transaction metadata."""
        return ranked_set(
            transaction.narration
            for transaction in self.filter_transactions(**kwargs)
            if transaction.narration
        )

    def filter_accounts(self, lineno=None, **kwargs):
        """Get accounts for transactions by transaction metadata.

        Parameters
        ----------
        lineno : int, optional
            Posting line number (1-indexed) of the filtered transaction to get. If None,
            all postings are returned.
        """
        accounts = []

        for transaction in self.filter_transactions(**kwargs):
            postings = transaction.postings

            if lineno is not None:
                postings = [postings[lineno - 1]]

            for posting in postings:
                accounts.append(posting.account)

        return ranked_set(accounts)

    @cached_property
    def templates(self):
        if self.template_path is None:
            raise TemplateFileNotSet

        with self.template_path.open() as templatefile:
            templates = yaml.safe_load(templatefile)

        return templates

    def search_templates(self, search_term=None, **kwargs):
        return fuzzy_match(self.templates.keys(), search_term=search_term, **kwargs)

    def get_template(self, label):
        try:
            template = self.templates[label]
        except KeyError as e:
            raise TemplateNotFoundError("Template not found") from e

        template["label"] = label

        return template

    def has_template(self, label):
        try:
            self.get_template(label)
        except ValueError:
            return False
        return True

    def search_payees(self, search_term=None, **kwargs):
        return fuzzy_match(self.payees, search_term=search_term, **kwargs)

    @cached_property
    def accounts(self):
        entries, _, _ = load_file(str(self.accounts_file))
        out = []

        for entry in entries:
            if not isinstance(entry, data.Open):
                continue

            out.append(entry.account)

        return out

    @cached_property
    def payees(self):
        return set(
            [
                transaction.payee
                for transaction in self.transactions
                if transaction.payee
            ]
        )

    @cached_property
    def narrations(self):
        return set(
            [
                transaction.narration
                for transaction in self.transactions
                if transaction.narration
            ]
        )

    def add_entry(self, transaction):
        from shutil import copyfile

        insert_lineno = self._new_transaction_lineno(transaction)
        parent_dir = str(self.transactions_file.resolve().parent)
        destination = NamedTemporaryFile(mode="w", dir=parent_dir)

        with self.transactions_file.open(mode="r") as source:
            lineno = 1

            while lineno < insert_lineno:
                destination.file.write(source.readline())
                lineno += 1

            # Insert the new entry.
            destination.file.write(serialise_entry(transaction))

            # Write the rest in chunks.
            while True:
                data = source.read(1024)

                if not data:
                    break

                destination.file.write(data)

        # Finish writing data.
        destination.flush()
        # Overwrite the transaction file with the new one.
        copyfile(destination.name, str(self.transactions_file.resolve()))
        # Delete the temporary file.
        destination.close()

    def _new_transaction_lineno(self, transaction):
        """Get the line number at which the specified transaction should go."""
        for existing_transaction in self.transactions:
            if existing_transaction.date > transaction.date:
                return existing_transaction.meta["lineno"]

        # Transaction should go on the last line of the file.
        last_txn_start = existing_transaction.meta["lineno"]
        entry = serialise_entry(existing_transaction)
        return last_txn_start + len(entry.splitlines())

    def check_syntax(self):
        """Check the syntax of the account file."""
        from beancount import loader
        from beancount.ops import validation

        _, errors, _ = loader.load_file(
            str(self.accounts_file),
            # Force slow and hardcore validations, just for check.
            extra_validations=validation.HARDCORE_VALIDATIONS,
        )

        if errors:
            errorlist = [printer.format_error(error).strip() for error in errors]
            raise ValueError("\n".join(errorlist))

    def check_date_order(self):
        """Check the transactions are correctly ordered by date."""
        errors = []
        last_lineno = None
        last_date = None

        for transaction in self.transactions:
            lineno = transaction.meta["lineno"]
            date = transaction.date

            if last_lineno is not None and lineno < last_lineno:
                errors.append(
                    f"Entry on line {lineno} of {self.transactions_file!s}: "
                    f"{date} < {last_date}"
                )

            last_lineno = lineno
            last_date = date

        if errors:
            raise ValueError("\n".join(errors))

    def format_transactions(self, backup=True, **kwargs):
        from beancount.scripts.format import align_beancount

        original = self.transactions_file.read_text()
        new = align_beancount(original, **kwargs)

        if backup:
            self.transaction_backup_file.write_text(original)

        self.transactions_file.write_text(new)

    def ingest_transactions(self, path):
        """Ingest the transactions from the specified path."""
        from runpy import run_path
        from beancount.ingest.identify import find_imports
        from beancount.ingest.extract import extract_from_file

        # Run the config file and use its config setting to get the importer.
        mod = run_path(self.importers_config_path)
        _, importers = next(find_imports(mod["CONFIG"], path))

        if len(importers) != 1:
            raise ValueError(
                f"Don't know how to handle '{path}' that can be imported by multiple "
                f"importers"
            )

        return extract_from_file(path, importers.pop())

    def parse_date(self, datestr):
        settings = {"DATE_ORDER": "DMY"}
        # There is no default DATE_ORDER setting in English locales; in such cases
        # dateparser unfortunately defaults to MDY date order, which only applies to one
        # particular English locale (see
        # https://en.wikipedia.org/wiki/Date_format_by_country). We set the default to DMY,
        # and only revert to MDY if the locale is en_US.
        lang, _ = locale.getlocale()
        if lang == "en_US":
            settings = {"DATE_ORDER": "MDY"}

        try:
            return dateparser.parse(datestr, settings=settings)
        except ValueError:
            raise ValueError("invalid date")

    def valid_date(self, datestr):
        try:
            datestr = self.parse_date(datestr)
        except ValueError:
            return False
        else:
            return datestr is not None

    def valid_account(self, account):
        return account in self.accounts

    def parse_payment(self, payment, allow_empty=True):
        if payment == "" and allow_empty:
            return None, None

        try:
            value, currency = payment.split()
            value = float(value)
        except ValueError:
            raise ValueError("Invalid format; must be '<value> <currency>'.")

        return value, currency

    def valid_payment(self, payment, allow_empty=True):
        if payment is None or payment == "":
            return allow_empty

        try:
            self.parse_payment(payment)
        except ValueError:
            return False

        return True

    def parse_fraction(self, fraction):
        try:
            fraction = float(fraction)
        except (ValueError, TypeError):
            raise ValueError("Invalid fraction")

        if not -1 <= fraction <= 1:
            raise ValueError("Fraction must be between -1 and 1")

        return fraction

    def valid_fraction(self, fraction):
        try:
            self.parse_fraction(fraction)
        except ValueError:
            return False

        return True

    def parse_split(self, split, total, total_currency):
        try:
            return self.parse_fraction(split) * total
        except ValueError:
            try:
                amount, currency = self.parse_payment(split)
            except ValueError:
                raise ValueError("Invalid split")

            if currency != total_currency:
                raise ValueError(
                    f"Currency must be {repr(total_currency)} (got {repr(currency)})"
                )

            return amount

    def valid_split(self, split):
        return self.valid_fraction(split) or self.valid_payment(
            split, allow_empty=False
        )
