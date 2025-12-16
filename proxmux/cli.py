"""proxmux CLI: discover stacks, generate HTML views, and check for updates."""

import argparse
from pathlib import Path
import logging

from .utils import log_error
from .discover import discover_stack
from .htmlgen import generate_html_from_yaml, generate_html_from_stack
from .updates import run_update_check


def main():
    """CLI entrypoint: parse arguments and dispatch discover, html, or updates commands."""
    p = argparse.ArgumentParser(prog="proxmux")
    p.add_argument("-v", "--debug", action="store_true", help="Enable debug logging")
    s = p.add_subparsers(dest="cmd")

    d = s.add_parser("discover")
    d.add_argument("-i", default="prox_stack.yml")
    d.add_argument("-o", default="stack_view.html")
    d.add_argument("-r", "--render", action="store_true")

    h = s.add_parser(
        "html", description="Generates an HTML file to visualize your stack."
    )
    h.add_argument("-i", default="prox_stack.yml")
    h.add_argument("-o", default="stack_view.html")

    u = s.add_parser("updates")
    u.add_argument("-i", default="prox_stack.yml")
    u.add_argument("-l", "--list", action="store_true")

    a = p.parse_args()

    if a.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if a.cmd == "discover":
        stack = discover_stack(a.i)
        if a.render:
            generate_html_from_stack(stack, a.o)
    elif a.cmd == "html":
        if not Path(a.i).exists():
            log_error(
                (
                    f"Input YAML file {a.i} does not exist. "
                    "Generate one with 'proxmux discover' or rerun the command and "
                    "provide the path to the stack file with "
                    "'proxmux html -i /path/to/stack.yml'."
                )
            )
            p.print_help()
            return
        generate_html_from_yaml(a.i, a.o)
    elif a.cmd == "updates":
        run_update_check(a.i, a.list)
    else:
        p.print_help()
