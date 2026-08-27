"""String utility functions."""

import re
import unicodedata


def slugify(text: str) -> str:
    """Convert a string into a URL-friendly slug.

    The input is lowercased, leading/trailing whitespace is stripped,
    non-alphanumeric runs are replaced with a single hyphen, and any
    leading/trailing hyphens are removed. Unicode characters are
    transliterated to ASCII when possible (e.g., accented letters) or
    dropped entirely when they have no ASCII equivalent.

    Examples:
        >>> slugify("Hello, World! 你好")
        'hello-world'
        >>> slugify("Foo Bar  Baz")
        'foo-bar-baz'
        >>> slugify("   ")
        ''
    """
    # Normalize unicode and drop any characters that have no ASCII form.
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    # Lowercase and strip surrounding whitespace.
    ascii_text = ascii_text.lower().strip()
    # Replace runs of non-alphanumeric characters with a single hyphen.
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    # Remove any leading or trailing hyphens.
    return slug.strip("-")
