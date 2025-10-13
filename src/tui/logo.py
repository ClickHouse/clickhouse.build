"""TUI logo utilities for clickhouse.build"""


def get_logo() -> str:
    """
    Returns the clickhouse.build ASCII art logo.

    Returns:
        str: The ASCII art logo as a string
    """
    return """        __      __          _ __    __
  _____/ /_    / /_  __  __(_) /___/ /
 / ___/ __ \\  / __ \\/ / / / / / __  /
/ /__/ / / / / /_/ / /_/ / / / /_/ /
\\___/_/ /_(_)_.___/\\__,_/_/_/\\__,_/
                                      """


def print_logo() -> None:
    """Prints the clickhouse.build ASCII art logo in yellow."""
    print("\033[33m" + get_logo() + "\033[0m")
    print()
