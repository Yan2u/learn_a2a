import json
from pathlib import Path

CWD = Path(__file__).parent

configs = CWD.glob('*.json')

port_mapping = {
    'Tools': 8100,
    'Scholar': 8200,
    'Medical Experts': 8300,
    'Hospital System': 8400,
    'Debug': 8500,
}


def allocate_ports(config: Path):
    obj = json.load(open(str(config), 'r', encoding='utf-8'))
    category = obj['category']
    port = port_mapping[category]
    name = obj['agent_card']['name']
    port_mapping[category] = port + 1

    obj['port'] = port
    if 'url' in obj['agent_card']:
        del obj['agent_card']['url']
    print(
        f"Agent(file={config.stem}, name={name}, category={category}, port={port})")
    json.dump(obj, open(str(config), 'w', encoding='utf-8'), indent=2)


def main():
    for config in configs:
        allocate_ports(config)


if __name__ == '__main__':
    main()
