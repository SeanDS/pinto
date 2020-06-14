"""Script tools."""

from pathlib import Path
from tempfile import NamedTemporaryFile
import yaml
from fuzzywuzzy import process
from beancount.loader import load_file
from beancount.core import data
from beancount.parser import printer

ACCOUNT_DIR_ENVVAR = "PINTO_DIR"
TRANSACTION_DATE_FORMAT = "%Y-%m-%d"


def _fuzzy_match(candidates, search_term=None, limit=None):
    if search_term is None:
        return [(candidate, 1) for candidate in list(candidates)[:limit]]

    return process.extract(search_term, candidates, limit=limit)


def serialise_entry(entry):
    return printer.format_entry(entry)


class TemplateFileNotSet(ValueError):
    """Template file not set."""


class TemplateNotFoundError(ValueError):
    """Template name not found."""


class DegenerateChoiceException(ValueError):
    def __init__(self, *args, search=None, matches=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.search = search
        self.matches = matches

    def closest_matches(self, count=5):
        return [match for match, _ in self.matches[:count]]


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
    def transactions(self):
        """All transactions found at the account path."""
        entries, _, _ = load_file(self.accounts_file)
        yield from data.filter_txns(entries)

    @property
    def templates(self):
        if self.template_path is None:
            raise TemplateFileNotSet

        with self.template_path.open() as templatefile:
            templates = yaml.safe_load(templatefile)

        return templates

    def search_templates(self, search_term=None, templates=None, **kwargs):
        if templates is None:
            templates = self.templates.keys()

        return _fuzzy_match(templates, search_term=search_term, **kwargs)

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

    def search_payees(self, search_term=None, payees=None, **kwargs):
        if payees is None:
            payees = set(
                [
                    transaction.payee
                    for transaction in self.transactions
                    if transaction.payee
                ]
            )

        return _fuzzy_match(payees, search_term=search_term, **kwargs)

    def unique_payee(self, search, **kwargs):
        matches = list(self.search_payees(search, **kwargs))

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

    @property
    def accounts(self):
        entries, _, _ = load_file(str(self.accounts_file))

        for entry in entries:
            if not isinstance(entry, data.Open):
                continue

            yield entry

    def search_accounts(self, search_term=None, accounts=None, **kwargs):
        if accounts is None:
            accounts = [account.account for account in self.accounts]

        return _fuzzy_match(accounts, search_term=search_term, **kwargs)

    def unique_account(self, search, **kwargs):
        matches = list(self.search_accounts(search, **kwargs))

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
