"""Build and verify public release assets without local settings or runtime data."""
import hashlib
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = 'zhihuishu-mastery.user.js'
LATEST = 'https://github.com/17hwliao/zhihuishu/releases/latest/download/' + SCRIPT


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build():
    raw = (ROOT / SCRIPT).read_bytes()
    source = raw.decode('utf-8')
    release = re.search(r"const RELEASE_VERSION = '(\d+\.\d+\.\d+)'", source)[1]
    version = re.search(r"const VERSION = '(\d+\.\d+\.\d+)'", source)[1]
    assert re.search(r'^// @version\s+(\S+)', source, re.M)[1] == version
    for field in ('updateURL', 'downloadURL'):
        assert re.search(r'^// @' + field + r'\s+(\S+)', source, re.M)[1] == LATEST
    normalized, count = re.subn(r"const BUILD = '[\w-]+';", "const BUILD = 'dev-unstamped';", source)
    assert count == 1
    identity = 'v' + release.replace('.', '-') + '-' + digest(normalized.encode())[:12]
    assert f"const BUILD = '{identity}';" in source, 'Run stamp_build.py --release first'
    assert not re.search(r'\bsk-[A-Za-z0-9_-]{25,}', source), 'Potential credential in script'

    folder = 'zhihuishu-mastery-v' + release
    paths = [SCRIPT, 'README.md', 'LICENSE', 'docs/configuration.md', f'docs/releases/v{release}.md']
    files = {name: (ROOT / name).read_bytes() for name in paths}
    for name, data in files.items():
        assert not re.search(rb'\bsk-[A-Za-z0-9_-]{25,}', data), f'Potential credential in {name}'
    files['SHA256SUMS.txt'] = ''.join(f'{digest(data)}  {name}\n' for name, data in files.items()).encode()
    output = ROOT / '.local' / 'releases' / ('v' + release)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'publish-receipt.json').exists():
        raise RuntimeError('Publication receipt exists; keep published artifacts immutable')
    (output / SCRIPT).write_bytes(raw)
    (output / 'configuration.md').write_bytes(files['docs/configuration.md'])
    archive = output / (folder + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(folder + '/' + name, date_time=(2026, 11, 5, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zip_file.writestr(info, data)
    with zipfile.ZipFile(archive) as zip_file:
        assert zip_file.testzip() is None
        assert set(zip_file.namelist()) == {folder + '/' + name for name in files}
        for name, data in files.items():
            assert zip_file.read(folder + '/' + name) == data
    assets = [SCRIPT, 'configuration.md', archive.name]
    (output / 'SHA256SUMS.txt').write_text(
        ''.join(f'{digest((output / name).read_bytes())}  {name}\n' for name in assets),
        encoding='utf-8', newline='\n')
    assets.append('SHA256SUMS.txt')
    print(json.dumps({'release': release, 'userscriptVersion': version, 'build': identity,
                      'output': str(output), 'assets': [
                          {'name': name, 'size': (output / name).stat().st_size,
                           'sha256': digest((output / name).read_bytes())} for name in assets]}, indent=2))


if __name__ == '__main__':
    build()
