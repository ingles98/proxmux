"""HTML generation helpers for the Proxmux viewer.

Provide small utilities to render the bundled Jinja2 viewer
template with stack data (Python structures or YAML files).
"""

import json
from pathlib import Path
from typing import Any
import yaml
from jinja2 import Template, TemplateError
from utils import log_info, log_error

TEMPLATE_PATH = Path(__file__).parent / "templates" / "viewer.html"


def generate_html_from_stack(stack_data: Any, html_out: str) -> None:
    """Render the viewer template with `stack_data` and write to `html_out`.

    `stack_data` is converted to JSON and passed into the template as
    the `data` variable. Errors while reading the template or writing the
    output are logged as errors.
    """
    try:
        tpl = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, TemplateError) as e:
        log_error(f"Failed to read template {TEMPLATE_PATH}: {e}")
        return

    try:
        rendered = tpl.render(data=json.dumps(stack_data))
        Path(html_out).write_text(rendered, encoding="utf-8")
        log_info(f"Viewer written to {html_out}")
    except (OSError, UnicodeEncodeError, TemplateError) as e:
        log_error(f"Failed to render or write viewer to {html_out}: {e}")


def generate_html_from_yaml(yaml_path: str, html_out: str) -> None:
    """Load YAML from `yaml_path` and generate an HTML viewer at `html_out`.

    If the YAML file does not exist the function logs an error and
    returns without raising.
    """
    file_info = Path(yaml_path)
    if not file_info.exists():
        log_error(f"YAML file {yaml_path} not found, cannot refresh HTML")
        return

    try:
        data = yaml.safe_load(file_info.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        log_error(f"Failed to parse YAML file {yaml_path}: {e}")
        return

    generate_html_from_stack(data, html_out)
