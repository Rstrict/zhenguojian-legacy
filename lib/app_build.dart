const allSourcesEnabled = bool.fromEnvironment('ALL_SOURCES');
const appName = allSourcesEnabled ? '真果鉴' : '红果鉴';
const appSlug = allSourcesEnabled ? 'zhenguojian' : 'hongguojian';

/// 版本号由构建脚本从 pubspec.yaml 注入（`scripts/app_build.py`）。
///
/// 直接写死常量会在改版本号时漏改：App 内更新检查读的就是这个值，
/// 一旦与 pubspec 不一致，就会把已是最新的安装包判成"有新版本"每天弹窗。
const appVersion = String.fromEnvironment(
  'APP_VERSION',
  defaultValue: '0.0.0',
);

/// 发布仓库身份：应用内更新、远程参数下发、关于页都从这里取。
///
/// 单一来源，改 fork 只改这三行，不要再往业务代码里散落 `owner/repo` 字面量。
const appRepoOwner = String.fromEnvironment(
  'REPO_OWNER',
  defaultValue: 'Rstrict',
);
const appRepoName = String.fromEnvironment(
  'REPO_NAME',
  defaultValue: 'zhenguojian',
);
const appRepoSlug = '$appRepoOwner/$appRepoName';
const appRepoUrl = 'https://github.com/$appRepoSlug';
const appUpstreamUrl = 'https://github.com/Topkill/guoapp3';
