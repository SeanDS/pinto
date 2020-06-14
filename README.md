# Pinto
Supercharged command line interface for [Beancount](http://furius.ca/beancount/).

While Beancount provides a few basic utilities for creating transactions via importers
(such as a bank statement importer), it does not provide a mechanism to automatically
insert them into your existing account. Instead, it writes these transactions to a
separate file and the intention is that the user must manually copy those transactions
into their own account file. This manual operation is necessary because Beancount does
not place constraints on how the account file might be organised. For example, the
account file might be a single flat file, or a master file with a hierarchy of
imported subfiles. Beancount cannot know for sure where these transactions should go,
so it leaves it to you.

Pinto constrains the way in which the Beancount account files must be organised and in
doing so provides the ability for reliable automatic transaction insertion. The main
feature of Pinto is to use this constrained account file organisation to provide some
tools to further automate your accounting.

The main new tool is `pinto add` which provides an interactive way to add new
transactions to your account. This is particularly useful for those who fully track cash
expenses, where the data cannot be scraped from a bank statement. The tool provides
flags to auto-populate transaction files like payees, accounts, tags and dates, and also
provides a YAML-based template mechanism to auto-populate entries involving
frequent payees.

Other tools added to the `pinto` command are:

* `search`, a way to search your transactions for previously used accounts, payees and
  templates;
* `format`, a way to format your account files without having to call `bean-format` with
  the path to the files (using instead the environment variable);
* `check`, a way to check the syntax of your files without having to call `bean-check`
  (using the environment variable the same way as `format`) and the date ordering of
  your transactions.

## Examples

### Adding transactions
You can start the interactive transaction insertion tool from the command line:

```bash
pinto add
```

This will first prompt you for the date:
```
Enter transaction date [today]:
```

This tries to allow any sane way of defining a date, such as "2020-06-14", "yesterday",
"last week", "3 Mar 19", etc. (even future dates, like "in 3 weeks"). It uses
[maya](https://github.com/timofurrer/maya) as a parser. If you leave this empty, it
assumes the current date.

Next up you're asked for the payee:
```
Enter transaction date [today]:
Date will be 2020-06-14
Enter transaction payee:
```

You can enter whatever you like here. Pinto will try to match this to a previously used
payee. If your specified payee matches closely to one and only one existing payee, that
payee is used. If it closely matches to other possible payees, Pinto offers up a ranked
list of those matches to choose from. You can either choose to use one of these matches,
or insist on using the exact string you entered. This way, Pinto tries to let you keep
your accounts consistent, with the same payees being reused in the same forms, and
allowing you to be lazy by entering lowercase or shorthand forms of your intended payees
and having Pinto match them to the originals.

```
Enter transaction date [today]:
Date will be 2020-06-14
Enter transaction payee: BA
Non-unique or invalid payee.
Enter transaction payee ([1] BA, [2] Bamberg Bridge, [3] Kamps Backstube, [4] Bamberg market, [5] Bar Rossi):
```

You next get asked for a narration. This is simply a text entry, and does no fancy
matching:

```
Enter transaction date [today]:
Date will be 2020-06-14
Enter transaction payee: BA
Non-unique or invalid payee.
Enter transaction payee ([1] BA, [2] Bamberg Bridge, [3] Kamps Backstube, [4] Bamberg market, [5] Bar Rossi): 1
Payee will be BA
Enter transaction narration []:
```

After this Pinto goes into line entry mode. This lets you add two or more transaction
lines with smart matching of account names:

```
Enter transaction date [today]:
Date will be 2020-06-14
Enter transaction payee: BA
Non-unique or invalid payee.
Enter transaction payee ([1] BA, [2] Bamberg market, [3] Kamps Backstube, [4] Bar Soba, [5] Bar Rossi): 1
Payee will be BA
Enter transaction narration []: Flights to UK
Narration will be Flights to UK
Adding line 1...
Choose account: credit
Non-unique or invalid account.
Choose account ([1] Liabilities:DE:Deutsche-Bank:Credit-Card, [2] Expenses:Recreation, [3] Expenses:Recreation:Football, [4] Expenses:Recreation:Swimming, [5] Assets:UK:Reimbursements, [6] Other): 1
Account will be Liabilities:DE:Deutsche-Bank:Credit-Card
Enter value []: 250 EUR
Value will be 250.00 EUR
Adding line 2...
Choose account: flights
Non-unique or invalid account.
Choose account ([1] Expenses:Transport:Flights, [2] Expenses:Utilities:Electricity, [3] Expenses:Utilities:Internet, [4] Expenses:Utilities:Phone, [5] Liabilities:UK:Student-Loan, [6] Other): 1
Account will be Expenses:Transport:Flights
Enter value []:
Value will be empty
Add another line? [y/N]:
```

You may add as many lines as you like. If you want to leave a value empty, so Beancount
calculates it for you, you can do so. Finally, you are shown the draft transaction:

```
Draft transaction:
2020-06-14 * "BA" "Flights to UK"
  Liabilities:DE:Deutsche-Bank:Credit-Card  250 EUR
  Expenses:Transport:Flights

Commit? [y/N]:
```

Entering `y` or `Y` or `yes` will save the transaction in the appropriate place of your
transaction file (in date order).

#### Using templates
Templates can be used to further automate the account entry process. These must be
defined in a file called `templates.yaml` in the account directory.

*Example coming soon...*

## Installation
With Python 3 as the default Python interpreter, run:

```bash
pip install pinto
```

## Usage
From a terminal, run `pinto` for available options.

## Development
The developer warmly encourages collaboration. Please submit feature requests, bug
reports, etc. on the [GitHub issue tracker](https://github.com/SeanDS/pinto/issues).
Pull requests are also welcome.

To set up your development environment, please run the following from the `pinto`
repository root directory:

```bash
pip install -e .[dev]
```

After installation, run `pre-commit install`. This sets up some linting and code
formatting pre-commit checks.
