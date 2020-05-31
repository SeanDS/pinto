"""Transactions"""

from pathlib import Path
from enum import Enum, unique, auto
import datetime
from beancount.loader import load_file
from .format import align_beancount


@unique
class TransactionFlag(Enum):
    COMPLETE = auto()
    INCOMPLETE = auto()


class TransactionFile:
    FILEDATE_FORMAT = "%Y-%m"
    FILEPATH_TEMPLATE = FILEDATE_FORMAT + ".beancount"
    DATE_FORMAT = "%Y-%m-%d"

    def __init__(self, path):
        self._entries = None
        self._errors = None
        self._options = None
        self._file_date = None

        self.path = Path(path)

    @property
    def basename(self):
        return self.path.name

    @property
    def _filename_noext(self):
        return self.path.stem

    @property
    def file_date(self):
        if self._file_date is None:
            self._file_date = datetime.datetime.strptime(
                self._filename_noext, self.FILEDATE_FORMAT
            )
        return self._file_date

    @property
    def transactions(self):
        return self._entries

    def load(self):
        self._entries, self._errors, self._options = load_file(self.path)

    def date_compatible(self, date):
        """Check if the specified date is compatible with this file."""
        return self.file_date.year == date.year and self.file_date.month == date.month

    def check_date_order(self):
        last_lineno = self._entries[0].meta["lineno"]
        last_date = self._entries[0].date
        for entry in self._entries:
            lineno = entry.meta["lineno"]
            date = entry.date
            if lineno < last_lineno:
                print(
                    f"Entry on line {lineno} of {self.basename}: {date} < {last_date}"
                )
            if not self.date_compatible(date):
                wrongdate = date.strftime(self.FILEDATE_FORMAT)
                print(
                    f"Entry on line {lineno} of {self.basename}: {wrongdate} != {self.file_date}"
                )
            last_lineno = lineno
            last_date = date

    def file_contents(self):
        with open(self.path, "r") as fobj:
            contents = fobj.read()
        return contents

    def file_lines(self):
        with open(self.path, "r") as fobj:
            contents = fobj.readlines()
        return contents

    def _write_file_contents(self, contents, path=None):
        if path is None:
            path = self.path
        with open(path, "w") as fobj:
            fobj.write(contents)

    def _parse_date_from_line(self, line):
        datestr = line.split()[0]
        return datetime.datetime.strptime(datestr, self.DATE_FORMAT)

    def backup(self, destination):
        destination = Path(destination)
        if destination.resolve() == self.path.resolve():
            raise ValueError(
                "Backup destination cannot be same as the transaction file path."
            )
        contents = self.file_contents()
        self._write_file_contents(contents, path=destination)

    def align(self, **kwargs):
        contents = self.file_contents()
        out = align_beancount(contents, **kwargs)
        self._write_file_contents(out)

    def add(self, transaction):
        lines = self.file_lines()
        insert_lineno = None
        tdate = transaction.date.replace(tzinfo=None)
        for lineno, line in enumerate(lines):
            try:
                date = self._parse_date_from_line(line)
            except ValueError:
                # Not a date line.
                continue
            if date > tdate:
                # We've reached the first line with date after the transaction's.
                insert_lineno = lineno
                break
        if insert_lineno is None:
            # The end of the file was reached.
            insert_lineno = len(lines) + 1
        # Splice transaction lines into file lines.
        lines[insert_lineno:insert_lineno] = transaction.posting_lines
        contents = "".join(lines)
        self._write_file_contents(contents)

    @classmethod
    def create_from_date(cls, date, transaction_dir):
        path = Path(transaction_dir) / date.strftime(cls.FILEPATH_TEMPLATE)
        path.touch(exist_ok=False)
        return cls(path)


class Transaction:
    DATE_FORMAT = "%Y-%m-%d"

    def __init__(
        self,
        date,
        narration,
        lines=None,
        payee=None,
        tag=None,
        flag=TransactionFlag.COMPLETE,
    ):
        if lines is None:
            lines = []
        self.date = date
        self.narration = narration
        self.lines = lines
        self.payee = payee
        self.tag = tag
        self.flag = flag

    def add_line(self, **kwargs):
        self.lines.append(TransactionLine(**kwargs))

    @property
    def posting_date(self):
        return self.date.strftime(self.DATE_FORMAT)

    @property
    def posting_flag(self):
        return "*" if self.flag == TransactionFlag.COMPLETE else "!"

    @property
    def posting_description(self):
        description = f'"{self.narration}"'
        if self.payee is not None:
            description = f'"{self.payee}" {description}'
        if self.tag is not None:
            description = f"{description} #{self.tag}"
        return description

    @property
    def posting_lines(self):
        lines = [
            f"{self.posting_date} {self.posting_flag} {self.posting_description}\n"
        ]
        for line in self.lines:
            lines.append(f"\t{line.posting}\n")
        return lines

    @property
    def posting(self):
        posting = "".join(self.posting_lines)
        return align_beancount(posting)


class TransactionLine:
    def __init__(self, account, value=None, currency=None, currency_column=90):
        self.account = account
        self.value = value
        self.currency = currency
        self.currency_column = currency_column

    @property
    def posting_value(self):
        return f"{round(self.value, 2):.2f} {self.currency}"

    @property
    def posting_separation(self):
        tabs = 4
        count = (
            self.currency_column - tabs - len(str(self.account)) - len(str(self.value))
        )
        return " " * count

    @property
    def has_value(self):
        return self.value is not None

    @property
    def posting(self):
        line = self.account
        if self.has_value:
            line += f"{self.posting_separation}{self.posting_value}"
        return line
