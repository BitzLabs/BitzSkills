"""初回カナリア専用の一覧1・選択SKILL本文1に限定した読取りホスト。"""
import argparse
import importlib.util
from pathlib import Path

import production_cli_probe as cli

HOST_SPEC = importlib.util.spec_from_file_location('production_canary_readonly_host', Path(__file__).with_name('host.py'))
host = importlib.util.module_from_spec(HOST_SPEC)
HOST_SPEC.loader.exec_module(host)


class CanaryHost(host.Host):
    def __init__(self, snapshot, manifest_sha256, log):
        self.stop_marker = log.parent / 'host-stop.json'
        super().__init__(snapshot, manifest_sha256, log)

    def execute(self, name, arguments):
        if self.sequence == 1 and name == 'list_resources' and arguments == {}:
            return super().execute(name, arguments)
        if self.sequence == 2 and name == 'read_resource' and isinstance(arguments, dict) and set(arguments) == {'path'}:
            if isinstance(arguments['path'], str) and arguments['path'] in {s['path'] for s in self.manifest['skills']}:
                return super().execute(name, arguments)
        marker = self.stop_marker
        if not marker.exists():
            cli.exclusive(marker, cli.encoded({'reason': 'bounded-host-policy', 'sequence': self.sequence}))
        raise ValueError('only one listing followed by one selected skill read allowed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    value = CanaryHost(args.snapshot, args.manifest_sha256, args.log)
    try:
        host.serve(value)
    finally:
        value.close()
