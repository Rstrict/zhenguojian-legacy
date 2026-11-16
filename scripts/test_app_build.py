import base64
import os
from pathlib import Path
import plistlib
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from app_build import BuildVariant, repository_identity, runtime_defines
from configure_ios_branding import configure


def dart_defines(*values):
    return ','.join(base64.b64encode(value.encode()).decode() for value in values)


class AppBuildTests(unittest.TestCase):
    def test_omitted_or_false_flag_keeps_hongguo_only(self):
        for encoded in ['', dart_defines('ALL_SOURCES=false'), dart_defines('OTHER=true')]:
            variant = BuildVariant.from_dart_defines(encoded)
            self.assertFalse(variant.all_sources)
            self.assertEqual(variant.name, '红果鉴')
            self.assertEqual(variant.slug, 'hongguojian')

    def test_full_edition_decodes_among_other_flutter_defines(self):
        variant = BuildVariant.from_dart_defines(dart_defines(
            'OTHER=中文', 'ALL_SOURCES=true', 'VALUE=a=b'))
        self.assertTrue(variant.all_sources)
        self.assertEqual(variant.name, '真果鉴')
        self.assertEqual(variant.slug, 'zhenguojian')

    def test_runtime_defines_carry_release_identity_and_version(self):
        root = Path(__file__).resolve().parents[1]
        defines = runtime_defines(root, {'REPO_OWNER': 'Fork Owner', 'REPO_NAME': 'forked'})
        published = (root / 'pubspec.yaml').read_text(encoding='utf-8')
        version = re.search(r'^version:\s*([\w.+-]+)\s*$', published, re.MULTILINE).group(1)
        self.assertIn('APP_VERSION=' + version, defines)
        self.assertIn('REPO_OWNER=Fork Owner', defines)
        self.assertIn('REPO_NAME=forked', defines)

    def test_version_comes_from_pubspec_not_a_hardcoded_constant(self):
        root = Path(__file__).resolve().parents[1]
        published = re.search(r'^version:\s*([\w.+-]+)\s*$',
                              (root / 'pubspec.yaml').read_text(encoding='utf-8'),
                              re.MULTILINE).group(1)
        for enabled in [False, True]:
            variant = BuildVariant.load(enabled, root)
            self.assertEqual(variant.version, published)
            self.assertIn('--dart-define=APP_VERSION=' + published, variant.flutter_arguments)
        layout = (root / 'lib/app_layout.dart').read_text(encoding='utf-8')
        self.assertNotIn("const appVersion =", layout)
        build = (root / 'lib/app_build.dart').read_text(encoding='utf-8')
        self.assertIn("String.fromEnvironment(\n  'APP_VERSION'", build)

    def test_default_repository_identity_points_at_this_fork(self):
        self.assertEqual(repository_identity({}), ('Rstrict', 'zhenguojian'))

    def test_ios_branding_can_switch_editions_without_replacing_bundle_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'Info.plist'
            original = {'CFBundleIdentifier': 'com.duanju.duanjuApp', 'CFBundleVersion': '9'}
            path.write_bytes(plistlib.dumps(original))
            for enabled in [True, False]:
                configure(path, dart_defines('ALL_SOURCES=' + str(enabled).lower()))
                actual = plistlib.loads(path.read_bytes())
                self.assertEqual(actual['CFBundleDisplayName'], '真果鉴' if enabled else '红果鉴')
                self.assertEqual(actual['CFBundleName'], 'zhenguojian' if enabled else 'hongguojian')
                for key, value in original.items():
                    self.assertEqual(actual[key], value)

    @unittest.skipUnless(shutil.which('cmake'), 'CMake is unavailable')
    def test_windows_reads_defines_from_flutter_tool_environment(self):
        branding = Path(__file__).resolve().parents[1] / 'windows/runner/app_branding.cmake'
        for flags, expected in [
            ([], '红果鉴'),
            (['ALL_SOURCES=true'], '真果鉴'),
            (['OTHER=true', 'ALL_SOURCES=false'], '红果鉴'),
            (['ALL_SOURCES=true', 'ALL_SOURCES=false'], '红果鉴'),
        ]:
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as temporary:
                script = Path(temporary) / 'check.cmake'
                result = Path(temporary) / 'name.txt'
                script.write_text(
                    'list(APPEND FLUTTER_TOOL_ENVIRONMENT "OTHER=1" "DART_DEFINES=' + dart_defines(*flags) + '")\n'
                    'include("' + branding.as_posix() + '")\n'
                    'file(WRITE "' + result.as_posix() + '" "${APP_DISPLAY_NAME}")\n',
                    encoding='utf-8',
                )
                subprocess.run(['cmake', '-P', str(script)], check=True, capture_output=True)
                self.assertEqual(result.read_text(encoding='utf-8'), expected)

    def test_android_and_windows_propagate_one_edition_to_core_flutter_and_package(self):
        root = Path(__file__).resolve().parent
        for target in ['android', 'windows']:
            for enabled in [False, True]:
                with self.subTest(target=target, all_sources=enabled):
                    script = root / f'build_{target}.py'
                    arguments = [str(script)] + (['--all-sources'] if enabled else [])
                    # 固定 host 平台：构建脚本里的 `platform.system()` 分支在
                    # 清空环境变量的 Windows 上会去跑 `ver` 命令而崩溃，
                    # 这里显式给出平台，测试只关心参数透传。
                    with mock.patch.object(sys, 'argv', arguments), \
                            mock.patch.dict(os.environ, {'PATH': '/tools'}, clear=True), \
                            mock.patch('platform.system', return_value='Linux'), \
                            mock.patch('shutil.which', return_value='/tools/flutter'), \
                            mock.patch('subprocess.run') as run:
                        runpy.run_path(str(script), run_name='__main__')
                    calls = [call.args[0] for call in run.call_args_list]
                    native = next(call for call in calls if any(str(arg).endswith('build_native.py') for arg in call))
                    flutter = next(call for call in calls if 'build' in call)
                    package = next(call for call in calls if any(str(arg).endswith('package_release.py') for arg in call))
                    self.assertEqual('--all-sources' in native, enabled)
                    self.assertEqual('--all-sources' in package, enabled)
                    self.assertIn('--dart-define=ALL_SOURCES=' + str(enabled).lower(), flutter)
                    published = re.search(r'^version:\s*([\w.+-]+)\s*$',
                                          (root.parent / 'pubspec.yaml').read_text(encoding='utf-8'),
                                          re.MULTILINE).group(1)
                    self.assertIn('--dart-define=APP_VERSION=' + published, flutter)
                    self.assertIn('core.buildAllSources=' + str(enabled).lower(), BuildVariant(enabled).linker_flags)


if __name__ == '__main__':
    unittest.main()
