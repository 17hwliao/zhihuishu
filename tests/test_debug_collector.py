"""Validate log acknowledgement, deduplication and credential removal over HTTP."""
import http.client
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('debug_collector', Path(__file__).resolve().parents[1] / 'tools' / 'debug_collector.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class CollectorTest(unittest.TestCase):
    def test_rotation_snapshot_limits_and_content_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'events.jsonl'
            unrelated = Path(tmp) / 'events.jsonl.keep'
            unrelated.write_text('unrelated', encoding='utf-8')
            server = collector.Collector(output, 0, log_bytes=900, log_files=3,
                                         snapshot_bytes=1800, snapshot_total_bytes=3000, snapshot_count=2)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def post(path, payload):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                connection.request('POST', '/zhihuishu-debug/v1/' + path, body=json.dumps(payload),
                                   headers={'Content-Type': 'application/json', 'X-Zhihuishu-Debug': '1'})
                response = connection.getresponse(); status = response.status; response.read(); connection.close()
                return status

            try:
                for index in range(1, 25):
                    self.assertEqual(post('logs', {'documentId': 'bounded', 'events': [
                        {'seq': index, 'event': 'answer.saved', 'data': {'source': 'ai', 'reason': 'x' * 120,
                         'stem': 'FULL_QUESTION', 'answers': ['FULL_ANSWER'], 'response': 'FULL_AI_RESPONSE'}}]}), 204)
                managed = [p for p in Path(tmp).glob('events.jsonl*') if p != unrelated]
                self.assertLessEqual(len(managed), 3)
                self.assertLessEqual(sum(p.stat().st_size for p in managed), 2700)
                self.assertTrue(all(p.stat().st_size <= 900 for p in managed))
                self.assertTrue(server.pruned_bytes > 0)
                for file in managed:
                    data = file.read_text(encoding='utf-8')
                    self.assertNotIn('FULL_QUESTION', data)
                    self.assertNotIn('FULL_ANSWER', data)
                    self.assertNotIn('FULL_AI_RESPONSE', data)
                snap = {'documentId': 'bounded', 'snapshot': {'page': 'https://example.com/page', 'time': 'one',
                        'elements': [{'tag': 'div', 'id': 'one', 'text': 'FULL_QUESTION',
                                      'attributes': {'role': 'group', 'title': 'FULL_ANSWER'}}]}}
                self.assertEqual(post('snapshot', snap), 204)
                snap['snapshot']['time'] = 'two'
                self.assertEqual(post('snapshot', snap), 204)
                self.assertEqual(len(list((Path(tmp) / 'snapshots').glob('*.json'))), 1)
                for index in range(4):
                    snap['snapshot']['elements'][0]['id'] = str(index)
                    self.assertEqual(post('snapshot', snap), 204)
                snapshots = list((Path(tmp) / 'snapshots').glob('*.json'))
                self.assertLessEqual(len(snapshots), 2)
                self.assertLessEqual(sum(p.stat().st_size for p in snapshots), 3000)
                self.assertTrue(all('FULL_QUESTION' not in p.read_text(encoding='utf-8') and 'FULL_ANSWER' not in p.read_text(encoding='utf-8') for p in snapshots))
                snap['snapshot']['elements'] = [{'tag': 'div', 'classes': 'x' * 200} for _ in range(100)]
                self.assertEqual(post('snapshot', snap), 413)
                self.assertEqual(unrelated.read_text(encoding='utf-8'), 'unrelated')
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_restricted_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = collector.Collector(Path(tmp) / 'events.jsonl', 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(path, data=None, headers=None):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                connection.request('GET' if data is None else 'POST', path,
                                   body=None if data is None else json.dumps(data), headers=headers or {})
                response = connection.getresponse()
                result = response.status, json.loads(response.read() or '{}')
                connection.close()
                return result

            try:
                client = {'X-Zhihuishu-Debug': '1', 'X-Zhihuishu-Client': 'x' * 72,
                          'Origin': 'https://ai-smart-course-student-pro.zhihuishu.com'}
                control = {'X-Zhihuishu-Control': server.control_secret}
                poll = {'documentId': 'fixture-client', 'version': 'test', 'build': 'test',
                        'route': {'course': '123', 'cls': '456'}, 'keyConfigured': True}
                self.assertEqual(request('/control/clients')[0], 403)
                self.assertEqual(request('/client/poll', poll, client)[0], 200)
                clients = request('/control/clients', headers=control)[1]['clients']
                self.assertNotIn('client_secret', clients[0])
                self.assertTrue(clients[0]['keyConfigured'])
                command = {'documentId': 'fixture-client', 'course': '123', 'cls': '456', 'action': 'start', 'stopAfter': 1}
                self.assertEqual(request('/control/commands', command, {**control, 'Origin': 'https://example.com'})[0], 403)
                self.assertEqual(request('/control/commands', {**command, 'course': '999'}, control)[0], 400)
                self.assertEqual(request('/control/commands', {**command, 'action': 'eval', 'code': 'alert(1)'}, control)[0], 400)
                self.assertEqual(request('/control/commands', {**command, 'stopAfter': 0}, control)[0], 400)
                code, accepted = request('/control/commands', command, control)
                self.assertEqual(code, 200)
                received = request('/client/poll', poll, client)[1]['command']
                self.assertEqual(received['id'], accepted['id'])
                self.assertIsNone(request('/client/poll', poll, client)[1]['command'])
                ack = {'documentId': 'fixture-client', 'id': received['id'], 'outcome': 'ok'}
                self.assertEqual(request('/client/ack', ack, {**client, 'X-Zhihuishu-Client': 'y' * 72})[0], 403)
                self.assertEqual(request('/client/ack', ack, client)[0], 200)
                self.assertEqual(request('/control/clients', headers=control)[1]['commands'][0]['state'], 'acknowledged')
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_redaction_and_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'events.jsonl'
            server = collector.Collector(output, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def post(payload, origin='https://onlineweb.zhihuishu.com', marker='1'):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                connection.request('POST', '/zhihuishu-debug/v1/logs', body=json.dumps(payload),
                                   headers={'Origin': origin, 'Content-Type': 'application/json', 'X-Zhihuishu-Debug': marker})
                response = connection.getresponse()
                status = response.status
                response.read()
                connection.close()
                return status

            try:
                payload = {'documentId': 'fixture-doc', 'version': 'test', 'events': [
                    {'seq': 1, 'event': 'fixture', 'data': {'authorization': 'Bearer dont-persist',
                     'note': 'token=dont-persist sk-fixture-secret',
                     'page': 'https://example.com/page?token=dont-persist&classId=2'}}]}
                self.assertEqual(post(payload), 204)
                self.assertEqual(post(payload), 204)
                lines = output.read_text(encoding='utf-8').splitlines()
                self.assertEqual(len(lines), 1)
                self.assertNotIn('dont-persist', lines[0])
                self.assertNotIn('sk-fixture-secret', lines[0])
                self.assertIn('classId=2', lines[0])
                self.assertEqual(server.count, 1)
                self.assertEqual(post(payload, origin='https://unrelated.invalid'), 403)
                self.assertEqual(post(payload, marker=''), 403)
                self.assertEqual(post({'documentId': 'fixture-doc', 'events': [{}]}), 400)
                self.assertEqual(server.count, 1)
                # A failed write must not mark the event as delivered before retry.
                server.output = Path(tmp) / 'missing' / 'events.jsonl'
                payload['events'][0]['seq'] = 2
                self.assertEqual(post(payload), 507)
                server.output = output
                self.assertEqual(post(payload), 204)
                self.assertEqual(server.count, 2)
                original_write = server.write_events
                attempted = []

                def partial_failure(lines):
                    attempted.append(1)
                    if len(attempted) == 2:
                        raise OSError('fixture failure after one durable event')
                    original_write(lines)

                server.write_events = partial_failure
                payload['events'] = [{'seq': 3, 'event': 'task.state'}, {'seq': 4, 'event': 'task.state'}]
                self.assertEqual(post(payload), 507)
                self.assertEqual(server.count, 3)
                server.write_events = original_write
                self.assertEqual(post(payload), 204)
                written = [json.loads(line)['seq'] for line in output.read_text(encoding='utf-8').splitlines()]
                self.assertEqual(written.count(3), 1)
                self.assertEqual(written.count(4), 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
