import argparse
from pathlib import Path
from .discover import discover_stack
from .htmlgen import generate_html_from_yaml, generate_html_from_stack
from .updates import run_update_check

def main():
    p=argparse.ArgumentParser(prog="proxmux")
    s=p.add_subparsers(dest="cmd")

    d=s.add_parser("discover")
    d.add_argument("-i",default="prox_stack.yml")
    d.add_argument("-o",default="stack_view.html")
    d.add_argument("-r", "--render", action="store_true")

    h=s.add_parser("html", description="Generates an HTML file to visualize your stack.")
    h.add_argument("-i",default="prox_stack.yml")
    h.add_argument("-o",default="stack_view.html")

    u=s.add_parser("updates")
    u.add_argument("-i",default="prox_stack.yml")
    u.add_argument("-l","--list",action="store_true")

    a=p.parse_args()

    if a.cmd=="discover":
        stack=discover_stack(a.i)
        if a.render:
            generate_html_from_stack(stack,a.o)
    elif a.cmd=="html":
        if not Path(a.i).exists():
            p.print_help()
            return
        generate_html_from_yaml(a.i,a.o)
    elif a.cmd=="updates":
        run_update_check(a.i,a.list)
    else:
        p.print_help()
