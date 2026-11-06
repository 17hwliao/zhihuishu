"""Loopback-only receiver with bounded operational logs and structural diagnostics."""
import hashlib
import argparse
import json
import os
import re
import secrets
import time
import uuid
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

SENSITIVE = re.compile(r'token|cookie|password|secret|authorization|credential|api.?key|ticket|session', re.I)
QUERY_FIELDS = {'point', 'pointId', 'classId', 'courseId', 'paperId', 'examPaperId', 'catalogActiveTab'}
EVENT_FIELDS = {'version', 'build', 'kind', 'task', 'id', 'phase', 'point', 'round', 'rounds', 'source', 'question',
                'fingerprint', 'verdict', 'reason', 'attempt', 'attempts', 'count', 'confirmed', 'total', 'status',
                'ok', 'result', 'model', 'transport', 'method', 'mode', 'active', 'paused', 'course', 'cls',
                'index', 'limit', 'duplicate', 'conflicts', 'elements', 'dropped', 'actions', 'page'}


def operational_event(event):
    clean = {k: sanitize(v) for k, v in event.items() if k in
             ('time', 'seq', 'event', 'level', 'documentId', 'page', 'version', 'receivedAt', 'task', 'point', 'round')}
    clean['data'] = {k: sanitize(v)[:160] if isinstance(v, str) else v
                     for k, v in (event.get('data') or {}).items()
                     if k in EVENT_FIELDS and type(v) in (str, int, float, bool)}
    return clean


def clean_url(value):
    try:
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https'):
            return '[URL removed]'
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k in QUERY_FIELDS and re.fullmatch(r'[\w.-]{1,60}', v)])
        netloc = parts.hostname or ''
        if parts.port:
            netloc += f':{parts.port}'
        return urlunsplit((parts.scheme, netloc, parts.path, query, ''))
    except ValueError:
        return '[invalid URL]'


def sanitize(value, depth=0):
    if depth > 10:
        return '[depth limit]'
    if isinstance(value, dict):
        return {str(k)[:100]: '[REDACTED]' if SENSITIVE.search(str(k)) else sanitize(v, depth + 1)
                for k, v in list(value.items())[:80]}
    if isinstance(value, list):
        return [sanitize(v, depth + 1) for v in value[:128]]
    if isinstance(value, str):
        value = re.sub(r'https?://[^\s<>"\']+', lambda match: clean_url(match[0]), value)
        value = re.sub(r'Bearer\s+[^\s"\']+', 'Bearer [REDACTED]', value, flags=re.I)
        value = re.sub(r'\bsk-[\w-]+', '[REDACTED]', value)
        value = re.sub(r'((?:api[_-]?key|(?:access[_-]?)?token|authorization|cookie|password|secret|ticket)\s*[:=]\s*)[^\s,;]+',
                       r'\1[REDACTED]', value, flags=re.I)
        return value[:4000]
    return value


class Collector(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, output, port, *, log_bytes=1048576, log_files=4,
                 snapshot_bytes=2097152, snapshot_total_bytes=8388608, snapshot_count=6):
        if log_bytes < 512 or log_files < 2 or min(snapshot_bytes, snapshot_total_bytes, snapshot_count) <= 0:
            raise ValueError('invalid retention limits')
        self.output = Path(output).resolve()
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.seen = OrderedDict()
        self.count = 0
        self.log_bytes, self.log_files = log_bytes, log_files
        self.snapshot_bytes, self.snapshot_total_bytes, self.snapshot_count = snapshot_bytes, snapshot_total_bytes, snapshot_count
        self.pruned_bytes = 0
        self.clients = {}
        self.commands = {}
        self.control_secret = secrets.token_urlsafe(32)
        self.control_file = self.output.parent / 'debug-control.json'
        super().__init__(('127.0.0.1', port), Handler)
        self.control_file.write_text(json.dumps({'port': self.server_port, 'secret': self.control_secret}), encoding='utf-8')
        if self.output.exists() and self.output.stat().st_size > self.log_bytes:
            self.rotate_logs()
        self.prune_logs()
        self.prune_snapshots()

    def rotate_logs(self):
        # Only this receiver's exact archive names are managed; no recursive file operations.
        last = self.output.with_name(self.output.name + f'.{self.log_files - 1}')
        if last.exists():
            self.pruned_bytes += last.stat().st_size
            last.unlink()
        for index in range(self.log_files - 2, 0, -1):
            source = self.output.with_name(self.output.name + f'.{index}')
            if source.exists():
                source.replace(self.output.with_name(self.output.name + f'.{index + 1}'))
        if self.output.exists():
            self.output.replace(self.output.with_name(self.output.name + '.1'))
        self.prune_logs()

    def prune_logs(self):
        for path in self.output.parent.glob(self.output.name + '.*'):
            suffix = path.name[len(self.output.name) + 1:]
            if suffix.isdigit() and path.resolve().parent == self.output.parent and (int(suffix) >= self.log_files or path.stat().st_size > self.log_bytes):
                self.pruned_bytes += path.stat().st_size
                path.unlink()

    def write_events(self, lines):
        for line in lines:
            data = line.encode('utf-8')
            if len(data) > self.log_bytes:
                raise ValueError('event exceeds log file capacity')
            if self.output.exists() and self.output.stat().st_size + len(data) > self.log_bytes:
                self.rotate_logs()
            with self.output.open('ab') as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())

    def prune_snapshots(self, reserve_bytes=0, reserve_count=0):
        folder = self.output.parent / 'snapshots'
        if not folder.exists():
            return
        managed = [p for p in folder.glob('*.json') if p.resolve().parent == folder.resolve()
                   and re.fullmatch(r'(?:diag-[a-f0-9]{64}|\d{8}T\d{12}-[\w-]+)\.json', p.name)]
        managed.sort(key=lambda p: p.stat().st_mtime_ns, reverse=True)
        total = 0
        for index, path in enumerate(managed):
            size = path.stat().st_size
            if index >= self.snapshot_count - reserve_count or size > self.snapshot_bytes or total + size > self.snapshot_total_bytes - reserve_bytes:
                self.pruned_bytes += size
                path.unlink()
            else:
                total += size


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def allowed_origin(self):
        origin = self.headers.get('Origin')
        if not origin or origin == 'null':
            return True
        parts = urlsplit(origin)
        return ((parts.scheme == 'https' and (parts.hostname or '').endswith('.zhihuishu.com'))
                or parts.scheme in ('chrome-extension', 'moz-extension'))

    def reply(self, status, body=None):
        data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else b''
        self.send_response(status)
        if self.allowed_origin() and self.headers.get('Origin'):
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Zhihuishu-Debug, X-Zhihuishu-Client')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    def do_OPTIONS(self):
        self.reply(204 if self.allowed_origin() else 403)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/control/clients':
            if not self.controller_allowed():
                self.reply(403)
                return
            with self.server.lock:
                clients = [{k: v for k, v in client.items() if k != 'client_secret'}
                           for client in self.server.clients.values()]
                commands = list(self.server.commands.values())
            self.reply(200, {'clients': clients, 'commands': commands[-30:]})
            return
        if path in ('/', '/install'):
            source = (Path(__file__).resolve().parents[1] / 'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
            version = re.search(r"const VERSION = '([\w.]+)'", source)[1]
            build = re.search(r"const BUILD = '([\w-]+)'", source)[1]
            html = '''<!doctype html><meta charset="utf-8"><title>掌握度脚本本地安装</title>
<style>body{max-width:760px;margin:60px auto;padding:24px;font:17px/1.7 system-ui;color:#171717}a{color:inherit}button{padding:10px;font:inherit}</style>
<h1>智慧树掌握度助手</h1><p>本地源码 VERSION · 构建 BUILD</p>
<p>在安装了 Tampermonkey 的 Edge 或 Chrome 中打开此页面。</p>
<p><a href="/zhihuishu-mastery.user.js">安装 / 更新掌握度脚本</a></p>
<ol><li>点击上方链接，在油猴安装页面确认更新。仅看到源码不表示已经安装。</li>
<li>刷新智慧树课程页面，面板中应显示 VERSION 和构建 BUILD。</li>
<li>在面板保存 API Key；需要本机调试时勾选“实时写入本机日志”和“允许本机调试”，保存设置。</li>
<li>点击“开启进入课程自动启动”，进入目标课程。脚本只处理该课掌握度。</li></ol>
<p>调试不读取 API Key，不提供任意代码执行。关闭本机服务后，日常掌握度任务仍可运行。</p>
<p><a href="/health">查看本机服务状态</a></p>'''.replace('VERSION', version).replace('BUILD', build)
            data = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
            return
        if path == '/zhihuishu-mastery.user.js' and self.allowed_origin():
            source = Path(__file__).resolve().parents[1] / 'zhihuishu-mastery.user.js'
            data = source.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
            return
        if path != '/health' or not self.allowed_origin():
            self.reply(404)
            return
        self.reply(200, {'service': 'zhihuishu-local-debug', 'pid': os.getpid(), 'events': self.server.count,
                         'file': self.server.output.name, 'connectedClients': len(self.server.clients),
                         'limits': {'logFileBytes': self.server.log_bytes, 'logFiles': self.server.log_files,
                                    'snapshotCount': self.server.snapshot_count, 'snapshotTotalBytes': self.server.snapshot_total_bytes},
                         'prunedBytes': self.server.pruned_bytes})

    def controller_allowed(self):
        return not self.headers.get('Origin') and secrets.compare_digest(
            self.headers.get('X-Zhihuishu-Control', ''), self.server.control_secret)

    def control_post(self):
        controller = self.path == '/control/commands'
        if controller:
            if not self.controller_allowed():
                self.reply(403)
                return
        elif not self.allowed_origin() or self.headers.get('X-Zhihuishu-Debug') != '1':
            self.reply(403)
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 262144:
                self.reply(413)
                return
            data = json.loads(self.rfile.read(length))
            document = data['documentId']
            if not re.fullmatch(r'[\w-]{1,80}', document):
                raise ValueError('documentId')
            with self.server.lock:
                if controller:
                    allowed = {'documentId', 'action', 'course', 'cls', 'point', 'stopAfter'}
                    if set(data) - allowed or data['action'] not in ('inspect', 'scan', 'start', 'pause', 'resume'):
                        raise ValueError('action')
                    client = self.server.clients.get(document)
                    if not client or time.time() - client['seenAt'] > 15:
                        self.reply(409, {'error': '目标脚本未在线，先更新并开启本机调试'})
                        return
                    route = client.get('route') or {}
                    if any(not re.fullmatch(r'\d{1,30}', str(data.get(k, ''))) or data[k] != route.get(k) for k in ('course', 'cls')):
                        raise ValueError('course')
                    if data.get('point') is not None and not re.fullmatch(r'\d{1,30}', data['point']):
                        raise ValueError('point')
                    if data.get('stopAfter') is not None and (type(data['stopAfter']) is not int or not 1 <= data['stopAfter'] <= 1000):
                        raise ValueError('stopAfter')
                    if any(c['documentId'] == document and c['state'] == 'queued' for c in self.server.commands.values()):
                        self.reply(409, {'error': '已有待执行指令'})
                        return
                    command = {**data, 'id': uuid.uuid4().hex, 'state': 'queued', 'createdAt': time.time()}
                    self.server.commands[command['id']] = command
                    while len(self.server.commands) > 100:
                        self.server.commands.pop(next(iter(self.server.commands)))
                    self.reply(200, command)
                    return
                client_secret = self.headers.get('X-Zhihuishu-Client', '')
                if not re.fullmatch(r'[\w-]{64,100}', client_secret):
                    raise ValueError('client header')
                client = self.server.clients.get(document)
                if client and not secrets.compare_digest(client_secret, client['client_secret']):
                    self.reply(403)
                    return
                if self.path == '/client/poll':
                    fields = ('version', 'build', 'page', 'route', 'keyConfigured', 'api', 'automatic', 'task', 'plan')
                    clean = {k: sanitize(data.get(k)) for k in fields}
                    clean.update(documentId=document, client_secret=client_secret, seenAt=time.time())
                    # keyConfigured is a boolean, never a model credential.
                    clean['keyConfigured'] = data.get('keyConfigured') is True
                    self.server.clients[document] = clean
                    for stale in [k for k, v in self.server.clients.items() if time.time() - v['seenAt'] > 180]:
                        del self.server.clients[stale]
                    command = next((c for c in self.server.commands.values() if c['documentId'] == document and c['state'] == 'queued'), None)
                    if command:
                        command['state'] = 'dispatched' if time.time() - command['createdAt'] < 15 else 'expired'
                        if command['state'] == 'expired':
                            command = None
                    self.reply(200, {'command': command})
                    return
                command = self.server.commands.get(data.get('id'))
                if not client or not command or command['documentId'] != document or command['state'] != 'dispatched':
                    self.reply(409)
                    return
                command.update(state='acknowledged', outcome=sanitize(str(data.get('outcome', ''))), acknowledgedAt=time.time())
                self.reply(200, {'ok': True})
        except (ValueError, TypeError, KeyError, AttributeError):
            self.reply(400)

    def do_POST(self):
        if self.path in ('/client/poll', '/client/ack', '/control/commands'):
            self.control_post()
            return
        if self.path not in ('/zhihuishu-debug/v1/logs', '/zhihuishu-debug/v1/snapshot') or not self.allowed_origin() or self.headers.get('X-Zhihuishu-Debug') != '1':
            self.reply(403)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= (8388608 if self.path.endswith('/snapshot') else 262144):
                self.reply(413)
                return
            data = json.loads(self.rfile.read(length))
            document = data.get('documentId', '')
            if not isinstance(document, str) or not re.fullmatch(r'[\w-]{1,80}', document):
                self.reply(400)
                return
            if self.path.endswith('/snapshot'):
                snapshot = data.get('snapshot')
                if not isinstance(snapshot, dict) or not isinstance(snapshot.get('elements'), list) or len(snapshot['elements']) > 3000:
                    self.reply(400)
                    return
                # Sanitize each element separately; do not truncate the DOM array to the log-array limit.
                clean = sanitize({k: v for k, v in snapshot.items() if k != 'elements'})
                clean['elements'] = []
                for node in snapshot['elements']:
                    if not isinstance(node, dict):
                        self.reply(400)
                        return
                    allowed = {k: v for k, v in node.items() if k in ('parent', 'tag', 'id', 'classes', 'visible', 'bounds', 'attributes', 'url')}
                    if allowed.get('tag') in ('input', 'textarea'):
                        allowed.pop('text', None)
                    allowed['attributes'] = {k: v for k, v in (allowed.get('attributes') or {}).items()
                                             if k in ('role', 'type', 'name', 'aria-disabled', 'aria-checked')}
                    clean['elements'].append(sanitize(allowed))
                clean.pop('title', None)
                clean['structureOnly'] = True
                identity = json.dumps({'page': clean.get('page'), 'elements': clean['elements']}, ensure_ascii=False, sort_keys=True)
                digest = hashlib.sha256(identity.encode('utf-8')).hexdigest()
                content = json.dumps({'documentId': document, 'version': str(data.get('version', ''))[:30],
                                      'snapshot': clean}, ensure_ascii=False).encode('utf-8')
                if len(content) > min(self.server.snapshot_bytes, self.server.snapshot_total_bytes):
                    self.reply(413)
                    return
                with self.server.lock:
                    snapshots = self.server.output.parent / 'snapshots'
                    snapshots.mkdir(exist_ok=True)
                    target = snapshots / f'diag-{digest}.json'
                    if not target.exists():
                        self.server.prune_snapshots(reserve_bytes=len(content), reserve_count=1)
                        temporary = snapshots / '.incoming.tmp'
                        try:
                            with temporary.open('wb') as file:
                                file.write(content); file.flush(); os.fsync(file.fileno())
                            temporary.replace(target)
                        finally:
                            if temporary.exists():
                                temporary.unlink()
                    self.server.prune_snapshots()
                self.reply(204)
                return
            events = data.get('events')
            if not isinstance(events, list) or len(events) > 128:
                self.reply(400)
                return
            valid = []
            for event in events:
                if not isinstance(event, dict) or not isinstance(event.get('seq'), int) or not isinstance(event.get('event'), str):
                    self.reply(400)
                    return
                valid.append(operational_event({**event, 'documentId': document, 'version': str(data.get('version', ''))[:30],
                                       'receivedAt': datetime.now(timezone.utc).isoformat()}))
            with self.server.lock:
                lines, keys = [], []
                for event in valid:
                    key = (document, event['seq'])
                    if key in self.server.seen or key in keys:
                        continue
                    keys.append(key)
                    lines.append(json.dumps(event, ensure_ascii=False) + '\n')
                if lines:
                    for key, line in zip(keys, lines):
                        self.server.write_events([line])
                        self.server.seen[key] = True
                        self.server.count += 1
                while len(self.server.seen) > 20000:
                    self.server.seen.popitem(last=False)
        except (ValueError, TypeError, AttributeError):
            self.reply(400)
            return
        except OSError:
            self.reply(507)
            return
        self.reply(204)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8790)
    parser.add_argument('--output', default=str(Path(__file__).resolve().parents[1] / '.local' / 'runtime.jsonl'))
    args = parser.parse_args()
    server = Collector(args.output, args.port)
    print(f'Local debug collector listening on 127.0.0.1:{server.server_port}; log: {server.output}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
