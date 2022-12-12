# Pinto
![Pinto on PyPI](https://img.shields.io/pypi/v/pinto.svg "Pinto on PyPI")
![Python versions](https://img.shields.io/pypi/pyversions/pinto.svg "Python versions")
![Code style uses Black](https://img.shields.io/badge/code%20style-black-000000.svg "Code style uses Black")

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

## Expected account layout
Pinto expects your accounts directory to be arranged like this:

```
.
├── main.beancount
├── templates.yaml
└── transactions.beancount
```

The `main.beancount` file should use the `include` command to include the contents of
`transactions.beancount`.

The `templates.yaml` file is where you can specify templates for commonly used
transactions, useful for `pinto add`.

To avoid excessive typing, you should define an environment variable in your shell
called `PINTO_DIR` pointing to the directory containing your accounts.

## Examples

### Adding transactions
You can start the interactive transaction insertion tool from the command line:

```
$ pinto add
```

This will first prompt you for the date:
```
Enter transaction date [today]:
```

This tries to allow any sane way of defining a date, such as "2020-06-14", "yesterday",
"last week", "3 Mar 19", etc. (even future dates, like "in 3 weeks"). If you leave this
empty, it assumes the current date.

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
defined in a file called `templates.yaml` in the account directory. The contents of this
file should be in [YAML](https://yaml.org/) format.

Templates support `date`, `payee`, `narration`, and `lines` keys on the top level:

* `date`, `payee` and `narration` simply define the corresponding fields of the
  transaction. If they are not specified, the user is prompted for them when running
  `pinto add`.
* The `lines` key allows a list of lines to be defined, each optionally containing
  `account`, `splits` and `no_value` keys:
  * The `account` key defines the name of a single account, or a list of possible
    accounts. If a list is defined, the user is prompted to choose from the list of
    possible accounts during `pinto add`.
  * The `splits` key defines a list of possible split accounts. This provides the
    ability to define accounts to which the value from the *first* line of the
    transaction is split into. This might be useful if you share expenses with someone
    else and wish to split a fraction (e.g. half) of the expense into an asset account
    representing what that person owes you. This supports `account` and `value` keys:
      * `account` is the account to split the value with.
      * `value` is the fraction of the transaction value to split. The resulting value
        is rounded to the nearest two decimal places.
  * `no_value` can be set to `true` (it's `false` by default) to define that this line
    should not prompt the user for a value.

The above definitions are illustrated by the following example showing templates for
various German supermarkets, a pharmacy (DM) and a DIY shop (Bauhaus). See the notes
following the example for explanations for what is going on:

```yaml
denns:
  payee: &denns "Denn's Biomarkt"
  lines: &grocery-lines
    - account: &de-cash-accounts
      - "Assets:EU:Cash"
      - "Assets:DE:Deutsche-Bank:Current"
      splits: &de-partner-split
        - account: "Assets:DE:Reimbursements:Partner"
          value: -0.5
    - account: &de-groceries "Expenses:Food:Groceries"
      no_value: true
denns-partner:
  payee: *denns
  lines: &de-groceries-partner-liabilities
    - account: "Liabilities:DE:Partner"
    - account: "Expenses:Food:Groceries"
rewe:
  payee: &rewe "Rewe"
  lines: *grocery-lines
rewe-partner:
  payee: *rewe
  lines: *de-groceries-partner-liabilities
edeka:
  payee: &edeka "Edeka"
  lines: *grocery-lines
edeka-partner:
  payee: *edeka
  lines: *de-groceries-partner-liabilities
dm:
  payee: &dm "DM"
  lines:
    - account: *de-cash-accounts
      splits: *de-partner-split
    - account: &de-pharmacy-accounts
      - "Expenses:Toiletries"
      - "Expenses:Equipment:Kitchen"
      - "Expenses:Food:Groceries"
      - "Expenses:Household"
dm-partner:
  payee: *dm
  lines:
    - account: "Liabilities:DE:Partner"
    - account: *de-pharmacy-accounts
bauhaus:
  payee: &bauhaus "Bauhaus"
  lines:
    - account: *de-cash-accounts
      splits: *de-partner-split
    - account: &diy-accounts
      - "Expenses:Equipment"
      - "Expenses:Household"
bauhaus-partner:
  payee: *bauhaus
  lines:
    - account: "Liabilities:DE:Partner"
    - account: *diy-accounts
```

Some notes:

* The file uses [YAML anchors](https://learnxinyminutes.com/docs/yaml/) to save yet more
  typing and make future updates easier. These are optional.
* Each template has a corresponding `-partner` template which is used for when the
  user's partner spends money in those shops and wishes to split their expenses with
  you. When entering the transaction they made, you use the `-partner` template instead
  of the normal one which you would use if you had made the transaction. These
  `-partner` templates define the liability account to use the define the money that you
  owe them.
* Some shops such as the pharmacy DM sell goods that would go into many different
  accounts in the example user's setup. In this case, the accounts key defines a list
  of possible accounts, and the user is prompted to choose one for the particular line
  they enter.
* The `value` key in the `splits` section should in the case of liabilities be a
  negative number so that the split fraction of the *negative* expense becomes a
  *positive* asset.

Templates can be used by specifying either `-t` or `--template` followed by the name
of the template to use when running `pinto add`. For example:

```
$ pinto add -t bauhaus
Enter transaction date [today]:
Date will be 2020-06-14
Payee will be Bauhaus
Enter transaction narration []: Wood for side wall
Narration will be Wood for side wall
Adding line 1 of 2...
Choose account ([1] Assets:EU:Cash, [2] Assets:DE:Deutsche-Bank:Current, [3] Other): 1
Account will be Assets:EU:Cash
Enter value []: -10 EUR
Value will be -10.00 EUR
Adding line 2 of 2...
Choose account ([1] Expenses:Equipment, [2] Expenses:Household, [3] Other): 2
Account will be Expenses:Household
Enter value []:
Value will be empty
Draft transaction:
2020-06-14 * "Bauhaus" "Wood for side wall"
  Assets:EU:Cash      -10 EUR
  Expenses:Household

Commit? [y/N]: y
Committed!
```

Templates can be searched by name using `pinto search templates`.

## Installation
With Python 3 as the default Python interpreter, run:

```bash
pip install pinto
```

## Usage
From a terminal, run `pinto` for available options.

## Feature ideas
I would eventually like to:

* Automatically insert transactions imported from e.g. credit card statements into
  accounts.
* Allow scheduled transactions to be defined, such as monthly phone bills, which would
  be inserted automatically when running a special command.

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
