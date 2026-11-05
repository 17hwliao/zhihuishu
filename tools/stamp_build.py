"""Give the local userscript an identifier derived from its content, independent of release versions."""
import argparse
import hashlib
import re
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--release', action='store_true', help='Prefix build identity with the public release version.')
args = parser.parse_args()
path = Path(__file__).resolve().parents[1] / 'zhihuishu-mastery.user.js'
source = path.read_text(encoding='utf-8')
normalized, count = re.subn(r"const BUILD = '[\w-]+';", "const BUILD = 'dev-unstamped';", source)
assert count == 1
prefix = 'dev-'
if args.release:
    version = re.search(r"const RELEASE_VERSION = '(\d+\.\d+\.\d+)'", source)[1]
    prefix = 'v' + version.replace('.', '-') + '-'
build = prefix + hashlib.sha256(normalized.encode()).hexdigest()[:12]
path.write_text(normalized.replace("const BUILD = 'dev-unstamped';", f"const BUILD = '{build}';"), encoding='utf-8', newline='\n')
print(build)
