# Pinto
Command line interface for manual [Beancount](http://furius.ca/beancount/) transaction
entry.

Pinto provides interactive transaction insertion capabilities for Beancount. Specified
payees and accounts are searched to try to match against those previously used. Dates
can be written in human form, like "yesterday" or "last week" and are parsed into the
correct Beancount form. There is also a system for common transaction templates to be
defined which pre-populate or provide choices for certain fields of transactions during
the entry process.

Why not call this `bean-add` or `bean-transact`? Well, Pinto behaves in a somewhat more
opinionated way than the `bean-` namespaced commands. You might think of Pinto as a
higher order interface to those commands. Underneath, many of the functions and objects
used by those commands are used also by Pinto.

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
