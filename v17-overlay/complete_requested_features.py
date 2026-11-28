#!/usr/bin/env python3
"""Complete the six requested V17 features without replacing custom cloud-sync or Insights code."""
from pathlib import Path
import re
import subprocess

ROOT = Path(".")
UPGRADE = "origin/Version-Upgrade"

def git_bytes(*args):
    return subprocess.check_output(["git", *args])

def upstream(path):
    return git_bytes("show", f"{UPGRADE}:{path}")

def replace_once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)

def copy_text(path):
    content = upstream(path).decode("utf-8")
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)

def copy_bytes(path):
    content = upstream(path)
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

# Settings search support is isolated in the reusable row/group components. The Settings screen
# itself is patched surgically below, so the working V17 cloud-sync rows remain untouched.
for path in (
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/SettingItem.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/SearchTextField.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/expect/AppIcon.kt",
    "composeApp/src/androidMain/kotlin/com/maxrave/simpmusic/expect/AppIcon.android.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/expect/AppIcon.jvm.kt",
):
    copy_text(path)

# Copy the official Android launcher-icon resources, including adaptive-icon XML and densities.
listed = git_bytes("ls-tree", "-r", "--name-only", UPGRADE, "--", "androidApp/src/main/res", "composeApp/src/commonMain/composeResources/drawable").decode().splitlines()
icon_paths = [
    p for p in listed
    if re.search(r"androidApp/src/main/res/(mipmap-[^/]+/ic_launcher_(old_school|minimalism_light|minimalism_dark|pixel)(?:_foreground)?\.(?:xml|webp)|drawable/ic_launcher_pixel_foreground\.xml)$", p)
    or re.search(r"composeApp/src/commonMain/composeResources/drawable/app_icon_option_.*\.png$", p)
    or p == "androidApp/src/main/res/values/app_icon_colors.xml"
]
if not any("ic_launcher_old_school" in p for p in icon_paths):
    raise SystemExit("Official selectable launcher icon resources were not found.")
for path in icon_paths:
    copy_bytes(path)

# Insert only the official activity-alias declarations. Preserve the V17 application, OAuth,
# permissions, services, providers and manifest metadata.
manifest_path = "androidApp/src/main/AndroidManifest.xml"
manifest = (ROOT / manifest_path).read_text()
official_manifest = upstream(manifest_path).decode("utf-8")
if "AppIconLiquidGlass" not in manifest:
    start = official_manifest.find("        <!-- Selectable app icons")
    end = official_manifest.find("        <provider", start)
    if start < 0 or end < 0:
        raise SystemExit("Could not isolate official app-icon activity aliases.")
    aliases = official_manifest[start:end]
    manifest = replace_once(manifest, "        <provider", aliases + "        <provider", "App icon manifest aliases")
    (ROOT / manifest_path).write_text(manifest)

# Import the small set of app-icon strings, plus the Settings search placeholder.
strings_path = "composeApp/src/commonMain/composeResources/values/strings.xml"
strings = (ROOT / strings_path).read_text()
official_strings = upstream(strings_path).decode("utf-8")
keys = (
    "search_settings", "app_icon_title", "app_icon_liquid_glass", "app_icon_old_school",
    "app_icon_minimalism_light", "app_icon_minimalism_dark", "app_icon_pixel",
    "app_icon_close_warning",
)
additions = []
for key in keys:
    matches = re.findall(r'<string\s+name="' + re.escape(key) + r'"[^>]*>.*?</string>', official_strings, re.DOTALL)
    if len(matches) != 1:
        raise SystemExit(f"Expected one official string resource for {key}, found {len(matches)}")
    if not re.search(r'<string\s+name="' + re.escape(key) + r'"(?:\s|>)', strings):
        additions.append("    " + matches[0].strip())
if additions:
    strings = replace_once(strings, "</resources>", "\n".join(additions) + "\n</resources>", "App icon and Settings search resources")
    (ROOT / strings_path).write_text(strings)

settings_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/home/SettingScreen.kt"
settings = (ROOT / settings_path).read_text()
# Add imports without importing the official SettingsViewModel (which contains excluded AI settings).
import_anchor = "import androidx.compose.runtime.Composable\n"
imports = (
    "import androidx.compose.runtime.CompositionLocalProvider\n"
    "import com.maxrave.simpmusic.expect.AppIconStyle\n"
    "import com.maxrave.simpmusic.expect.currentAppIcon\n"
    "import com.maxrave.simpmusic.expect.setAppIcon\n"
    "import com.maxrave.simpmusic.ui.component.LocalSettingSearch\n"
    "import com.maxrave.simpmusic.ui.component.SearchTextField\n"
    "import com.maxrave.simpmusic.ui.component.SettingGroupShape\n"
    "import com.maxrave.simpmusic.ui.component.settingGroupBackground\n"
    "import com.maxrave.simpmusic.ui.component.searchKey\n"
    "import simpmusic.composeapp.generated.resources.search_settings\n"
    "import simpmusic.composeapp.generated.resources.app_icon_title\n"
    "import simpmusic.composeapp.generated.resources.app_icon_liquid_glass\n"
    "import simpmusic.composeapp.generated.resources.app_icon_old_school\n"
    "import simpmusic.composeapp.generated.resources.app_icon_minimalism_light\n"
    "import simpmusic.composeapp.generated.resources.app_icon_minimalism_dark\n"
    "import simpmusic.composeapp.generated.resources.app_icon_pixel\n"
    "import simpmusic.composeapp.generated.resources.app_icon_close_warning\n"
)
for line in imports.splitlines(True):
    if line.strip() not in settings:
        settings = replace_once(settings, import_anchor, import_anchor + line, "V17 Settings feature imports")

# Search is a screen-level query propagated to setting rows and groups. This retains every
# existing V17 row, including Google OAuth/Supabase controls, and filters rather than replacing it.
state_anchor = "    val settingListState = rememberLazyListState()\n"
state_add = (
    '    var searchQuery by rememberSaveable { mutableStateOf("") }\n'
    "    val searchText = remember(searchQuery) { searchKey(searchQuery.trim()) }\n"
)
if "var searchQuery by rememberSaveable" not in settings:
    settings = replace_once(settings, state_anchor, state_anchor + state_add, "Settings search state")
list_anchor = "    LazyColumn(\n        state = settingListState,"
if "CompositionLocalProvider(LocalSettingSearch provides searchText)" not in settings:
    settings = replace_once(settings, list_anchor, "    CompositionLocalProvider(LocalSettingSearch provides searchText) {\n" + list_anchor, "Settings search provider")
    close_anchor = "    // The pinned copy of the toolbar, frosted:"
    settings = replace_once(settings, close_anchor, "    }\n\n" + close_anchor, "Settings search provider closing")
search_anchor = "                // Above every section, and inside item 0 rather than an item of its own, for the glow reason above.\n"
search_ui = (
    "                SearchTextField(\n"
    "                    query = searchQuery,\n"
    "                    onQueryChange = { searchQuery = it },\n"
    "                    placeholder = stringResource(Res.string.search_settings),\n"
    "                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp),\n"
    "                    shape = SettingGroupShape,\n"
    "                    containerColor = settingGroupBackground(),\n"
    "                )\n"
)
if "placeholder = stringResource(Res.string.search_settings)" not in settings:
    settings = replace_once(settings, search_anchor, search_ui + search_anchor, "Settings search field")

# App icon chooser: use the existing V17 alert state without the newer optional icon-preview
# field, which is intentionally not imported from the official AI/Settings model.
icon_anchor = "                    // Hidden outright below Android 12"
icon_ui = """                    val appIcon = remember { currentAppIcon() }
                    appIcon?.let { current ->
                        val options = listOf(
                            AppIconStyle.LIQUID_GLASS to stringResource(Res.string.app_icon_liquid_glass),
                            AppIconStyle.OLD_SCHOOL to stringResource(Res.string.app_icon_old_school),
                            AppIconStyle.MINIMALISM_LIGHT to stringResource(Res.string.app_icon_minimalism_light),
                            AppIconStyle.MINIMALISM_DARK to stringResource(Res.string.app_icon_minimalism_dark),
                            AppIconStyle.PIXEL to stringResource(Res.string.app_icon_pixel),
                        )
                        SettingItem(
                            title = stringResource(Res.string.app_icon_title),
                            subtitle = options.firstOrNull { it.first == current }?.second ?: "",
                            onClick = {
                                viewModel.setAlertData(
                                    SettingAlertState(
                                        title = runBlocking { getString(Res.string.app_icon_title) },
                                        selectOne = SettingAlertState.SelectData(
                                            listSelect = options.map { (it.first == current) to it.second },
                                        ),
                                        confirm = runBlocking { getString(Res.string.change) } to { state ->
                                            options.firstOrNull { it.second == state.selectOne?.getSelected() }?.first?.let { style ->
                                                if (style != current) {
                                                    viewModel.setBasicAlertData(
                                                        SettingBasicAlertState(
                                                            title = runBlocking { getString(Res.string.warning) },
                                                            message = runBlocking { getString(Res.string.app_icon_close_warning) },
                                                            confirm = runBlocking { getString(Res.string.change) } to {
                                                                viewModel.setBasicAlertData(null)
                                                                setAppIcon(style)
                                                            },
                                                            dismiss = runBlocking { getString(Res.string.cancel) },
                                                        ),
                                                    )
                                                }
                                            }
                                        },
                                        dismiss = runBlocking { getString(Res.string.cancel) },
                                    ),
                                )
                            },
                        )
                    }
"""
if "val appIcon = remember { currentAppIcon() }" not in settings:
    settings = replace_once(settings, icon_anchor, icon_ui + icon_anchor, "App icon chooser row")

(ROOT / settings_path).write_text(settings)

# Replay Mix was present in source but hidden whenever the separate legacy local-tracking switch
# was false. V17's custom Insights records listening independently, so expose the card and refresh
# its preview whenever the Library screen is opened.
library_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/library/LibraryScreen.kt"
library = (ROOT / library_path).read_text()
old_refresh = """    LaunchedEffect(localTrackingEnabled) {
        if (localTrackingEnabled) viewModel.refreshReplayMixPreview()
    }"""
new_refresh = """    LaunchedEffect(Unit) { viewModel.refreshReplayMixPreview() }"""
if old_refresh in library:
    library = replace_once(library, old_refresh, new_refresh, "Replay Mix preview refresh")
if "showReplayMix = localTrackingEnabled" in library:
    library = replace_once(library, "showReplayMix = localTrackingEnabled", "showReplayMix = true", "Always-visible Replay Mix card")
(ROOT / library_path).write_text(library)

# Guard against silently shipping a partial implementation.
checks = {
    settings_path: ("SearchTextField(", "CompositionLocalProvider(LocalSettingSearch provides searchText)", "currentAppIcon()", "setAppIcon(style)"),
    library_path: ("showReplayMix = true", "refreshReplayMixPreview()"),
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/LibraryTilingBox.kt": ("if (showReplayMix)", "LibraryDynamicPlaylistType.ReplayMix"),
    "composeApp/src/androidMain/kotlin/com/maxrave/simpmusic/expect/AppIcon.android.kt": ("setComponentEnabledSetting", "AppIconPixel"),
    manifest_path: ("AppIconLiquidGlass", "AppIconPixel"),
}
for path, markers in checks.items():
    content = (ROOT / path).read_text()
    for marker in markers:
        if marker not in content:
            raise SystemExit(f"Requested V17 feature wiring missing from {path}: {marker}")

print("V17 requested-feature integration: Settings search, Android app icon chooser, and always-visible Replay Mix wired.")
