import json, yaml
from pathlib import Path
from jinja2 import Template
from .utils import log_info, log_error

TEMPLATE_PATH = Path(__file__).parent / "templates" / "viewer.html"

def generate_html_from_stack(stack_data, html_out):
    tpl = Template(TEMPLATE_PATH.read_text())
    Path(html_out).write_text(tpl.render(data=json.dumps(stack_data)))
    log_info(f"Viewer written to {html_out}")

def generate_html_from_yaml(yaml_path, html_out):
    file_info = Path(yaml_path)
    if not file_info.exists():
        log_error(f"YAML file {yaml_path} not found, cannot refresh HTML")
        return
    data = yaml.safe_load(file_info.read_text())
    generate_html_from_stack(data, html_out)
