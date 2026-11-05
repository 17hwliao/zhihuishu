"""Inspect connected mastery scripts or issue one narrowly scoped local command."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['status', 'inspect', 'scan', 'start', 'pause', 'resume'])
parser.add_argument('--document')
parser.add_argument('--course')
parser.add_argument('--cls')
parser.add_argument('--point')
parser.add_argument('--stop-after', type=int)
parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[1] / '.local' / 'debug-control.json')
args = parser.parse_args()
config = json.loads(args.config.read_text(encoding='utf-8'))
base = f'http://127.0.0.1:{config["port"]}'
headers = {'X-Zhihuishu-Control': config['secret'], 'Content-Type': 'application/json'}
data = None
if args.action != 'status':
    if not all((args.document, args.course, args.cls)):
        parser.error('指令必须指定 --document、--course、--cls，防止发送到另一页面')
    data = json.dumps({k: v for k, v in dict(documentId=args.document, action=args.action, course=args.course,
                                          cls=args.cls, point=args.point, stopAfter=args.stop_after).items() if v is not None}).encode()
request = Request(base + ('/control/clients' if data is None else '/control/commands'), data=data, headers=headers)
with urlopen(request, timeout=5) as response:
    print(json.dumps(json.load(response), ensure_ascii=False, indent=2))
