import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path

RUNTIME_DEFINES = ('APP_VERSION', 'REPO_OWNER', 'REPO_NAME')
DEFAULT_REPO_OWNER = 'Rstrict'
DEFAULT_REPO_NAME = 'zhenguojian'


def app_version(root):
    match = re.search(r'^version:\s*([\w.+-]+)\s*$',
                      (Path(root) / 'pubspec.yaml').read_text(encoding='utf-8'), re.MULTILINE)
    if not match:
        raise SystemExit('pubspec.yaml 缺少合法版本号。')
    return match.group(1)


def repository_identity(environment=None):
    environment = environment if environment is not None else os.environ
    return (environment.get('REPO_OWNER') or DEFAULT_REPO_OWNER,
            environment.get('REPO_NAME') or DEFAULT_REPO_NAME)


def runtime_defines(root, environment=None):
    owner, name = repository_identity(environment)
    return ['APP_VERSION=' + app_version(root), 'REPO_OWNER=' + owner, 'REPO_NAME=' + name]


@dataclass(frozen=True)
class BuildVariant:
    all_sources: bool = False
    version: str = '0.0.0'
    repo_owner: str = DEFAULT_REPO_OWNER
    repo_name: str = DEFAULT_REPO_NAME

    @classmethod
    def load(cls, all_sources=False, root=None, environment=None):
        root = root or Path(__file__).resolve().parents[1]
        owner, name = repository_identity(environment)
        return cls(bool(all_sources), app_version(root), owner, name)

    @property
    def name(self):
        return '真果鉴' if self.all_sources else '红果鉴'

    @property
    def slug(self):
        return 'zhenguojian' if self.all_sources else 'hongguojian'

    @property
    def arguments(self):
        return ['--all-sources'] if self.all_sources else []

    @property
    def flutter_arguments(self):
        return ['--dart-define=ALL_SOURCES=' + str(self.all_sources).lower()] + [
            '--dart-define=' + value for value in
            ['APP_VERSION=' + self.version, 'REPO_OWNER=' + self.repo_owner,
             'REPO_NAME=' + self.repo_name]]

    @property
    def linker_flags(self):
        return '-s -w -X duanjuapp/native/core.buildAllSources=' + str(self.all_sources).lower()

    @classmethod
    def from_dart_defines(cls, encoded):
        values = {}
        for item in encoded.split(','):
            if not item:
                continue
            key, separator, value = base64.b64decode(item, validate=True).decode('utf-8').partition('=')
            if separator:
                values[key] = value
        return cls(values.get('ALL_SOURCES') == 'true',
                   values.get('APP_VERSION', '0.0.0'),
                   values.get('REPO_OWNER', DEFAULT_REPO_OWNER),
                   values.get('REPO_NAME', DEFAULT_REPO_NAME))


def add_variant_argument(parser):
    parser.add_argument('--all-sources', action='store_true',
                        help='构建包含全部站源的真果鉴；默认构建仅红果的红果鉴')
