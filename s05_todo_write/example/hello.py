"""Example module demonstrating greeting functionality."""


def greet(name: str) -> str:
    """Create a greeting message for the given name.

    Args:
        name: The name of the person to greet.

    Returns:
        A greeting message string.
    """
    message = "Hello, " + name
    print(message)
    return message


if __name__ == "__main__":
    greet("Claude")
