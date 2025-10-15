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
    """Prints the clickhouse.build ASCII art logo in yellow as a header."""
    # Clear screen and move cursor to top
    print("\033[2J\033[H", end="")
    print("\n\n\033[33m" + get_logo() + "\033[0m")
    print("Version: 0.1.0")
    print("\033[33m" + "-" * 14 + "\033[0m")
