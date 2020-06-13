"""Formatting tools.

Based on core Beancount tools, with small modifications.
"""

import io
import re

from beancount.core import amount, account


def align_beancount(
    contents, prefix_width=4, num_width=None, currency_column=90, indent_width=4
):
    """Reformat Beancount input to align all the numbers at the same column.

    Args:
      contents: A string, Beancount input syntax to reformat.
      prefix_width: An integer, the width in characters to render the account
        name to. If this is not specified, a good value is selected
        automatically from the contents of the file.
      num_width: An integer, the width to render each number. If this is not
        specified, a good value is selected automatically from the contents of
        the file.
      currency_column: An integer, the column at which to align the currencies.
        If given, this overrides the other options.
      indent_width: An intenger, the number of spaces to use for indentation.
    Returns:
      A string, reformatted Beancount input with all the number aligned.
      No other changes than whitespace changes should be present between that
      return value and the input contents.

    """
    # Find all lines that have a number in them and calculate the maximum length
    # of the stripped prefix and the number.
    match_pairs = []
    for line in contents.splitlines():
        match = re.match(
            r'([^";]*?)\s+([-+]?\s*[\d,]+(?:\.\d*)?)\s+({}\b.*)'.format(
                amount.CURRENCY_RE
            ),
            line,
        )
        if match:
            prefix, number, rest = match.groups()
            match_pairs.append((prefix, number, rest))
        else:
            match_pairs.append((line, None, None))

    # Normalize whitespace before lines that has some indent and an account
    # name.
    norm_match_pairs = normalize_indent_whitespace(
        match_pairs, indent_width=indent_width
    )

    if currency_column:
        output = io.StringIO()
        for prefix, number, rest in norm_match_pairs:
            if number is None:
                output.write(prefix)
            else:
                num_of_spaces = currency_column - len(prefix) - len(number) - 4
                spaces = " " * num_of_spaces
                output.write(prefix + spaces + "  " + number + " " + rest)
            output.write("\n")
        return output.getvalue()

    # Compute the maximum widths.
    filtered_pairs = [
        (prefix, number) for prefix, number, _ in match_pairs if number is not None
    ]

    if filtered_pairs:
        max_prefix_width = max(len(prefix) for prefix, _ in filtered_pairs)
        max_num_width = max(len(number) for _, number in filtered_pairs)
    else:
        max_prefix_width = 0
        max_num_width = 0

    # Use user-supplied overrides, if available
    if prefix_width:
        max_prefix_width = prefix_width
    if num_width:
        max_num_width = num_width

    # Create a format that will admit the maximum width of all prefixes equally.
    line_format = "{{:<{prefix_width}}}  {{:>{num_width}}} {{}}".format(
        prefix_width=max_prefix_width, num_width=max_num_width
    )

    # Process each line to an output buffer.
    output = io.StringIO()
    for prefix, number, rest in norm_match_pairs:
        if number is None:
            output.write(prefix)
        else:
            output.write(line_format.format(prefix.rstrip(), number, rest))
        output.write("\n")
    formatted_contents = output.getvalue()

    # Ensure that the file before and after have only whitespace differences.
    # This is a sanity check, to make really sure we never change anything but whitespace,
    # so it's safe.
    # open('/tmp/before', 'w').write(re.sub(r'[ \t]+', ' ', contents))
    # open('/tmp/after', 'w').write(re.sub(r'[ \t]+', ' ', formatted_contents))
    old_stripped = re.sub(r"[ \t\n]+", " ", contents.rstrip())
    new_stripped = re.sub(r"[ \t\n]+", " ", formatted_contents.rstrip())
    assert old_stripped == new_stripped, (old_stripped, new_stripped)

    return formatted_contents


def normalize_indent_whitespace(match_pairs, indent_width=4):
    """Normalize whitespace before lines that has some indent and an account name.

    Args:
      match_pairs: A list of (prefix, number, rest) tuples.
      indent_width: The number of spaces to use for indentation.
    Returns:
      Another list of (prefix, number, rest) tuples, where prefix may have been
      adjusted with a different whitespace prefi.
    """
    # Compute most frequent account name prefix.
    match_posting = re.compile(r"([ \t]+)({}.*)".format(account.ACCOUNT_RE)).match
    norm_format = " " * indent_width + "{}"

    # Make the necessary adjustments.
    adjusted_pairs = []
    for tup in match_pairs:
        prefix, number, rest = tup
        match = match_posting(prefix)
        if match is not None:
            tup = (norm_format.format(match.group(2)), number, rest)
        adjusted_pairs.append(tup)
    return adjusted_pairs
