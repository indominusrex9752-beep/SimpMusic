#!/usr/bin/env python3
"""Port the selected, non-Analytics SimpMusic 2.7 features onto the Cloud-Sync source tree."""
from pathlib import Path
import re
import subprocess
import sys

BASE = "origin/Cloud-Sync"
UPGRADE = "origin/Version-Upgrade"
ROOT = Path(".")

FEATURE_PATHS = [
    "gradle/libs.versions.toml",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/di/ViewModelModule.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/navigation/graph/HomeScreenGraph.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/navigation/destination/home/RadioBuilderDestination.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/CreateSheet.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/other/RadioBuilderScreen.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/RadioBuilderViewModel.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/library/LibraryDynamicPlaylistScreen.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/library/LibraryScreen.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/library/LocalPlaylistScreen.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/LibraryTilingBox.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/LibraryItem.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/GridLibraryPlaylist.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/FullWidthItems.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/AdapterItems.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/selection/SelectedSongsBottomSheet.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/LibraryViewModel.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/LibraryDynamicPlaylistViewModel.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/LocalPlaylistViewModel.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/SongSelectionViewModel.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/ValueSlider.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/LiquidGlassContainer.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/expect/ui/LiquidGlass.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/expect/ui/DisplayCorner.kt",
    "composeApp/src/androidMain/kotlin/com/maxrave/simpmusic/expect/ui/DisplayCorner.android.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/expect/ui/DisplayCorner.jvm.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/home/EqualizerSection.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/ModalBottomSheet.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/FullscreenLyricsContent.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/LyricsFlowBackground.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/NowPlayingScreen.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/MiniPlayer.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/FullscreenPlayer.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/content/NowPlayingContentAppleMusic.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/content/NowPlayingContentM3Expressive.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/content/NowPlayingContentSpotify.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/content/NowPlayingExpressiveCards.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/content/applemusic/AppleMusicLyricStrip.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/content/applemusic/AppleMusicOutputSheet.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/content/applemusic/AppleMusicShared.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/theme/Theme.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/theme/Color.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/extension/UIExt.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/extension/UIExt.jvm.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/DesktopApp.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/DesktopDeepLinkHandler.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/WindowsProtocolRegistrar.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/expect/DesktopFullscreen.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/ui/component/MacAppearance.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/ui/mini_player/MiniPlayerLayout.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/ui/mini_player/MiniPlayerWindow.kt",
    "desktopApp/build.gradle.kts",
]

def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)

def edit(path: str, transform) -> None:
    target = ROOT / path
    if not target.is_file():
        raise SystemExit(f"Missing selected-feature target: {path}")
    original = target.read_text()
    updated = transform(original)
    if updated == original:
        raise SystemExit(f"No selected-feature change was made to {path}")
    target.write_text(updated)

# Refuse to run against a different base or silently omit a selected feature.
if any("analytics" in path.lower() or "insights" in path.lower() for path in FEATURE_PATHS):
    raise SystemExit("Analytics/Insights source files must never be imported from 2.7.")
run(["git", "cat-file", "-e", f"{BASE}^{{commit}}"])
run(["git", "cat-file", "-e", f"{UPGRADE}^{{commit}}"])
diff = run(
    ["git", "diff", "--binary", "--no-ext-diff", BASE, UPGRADE, "--", *FEATURE_PATHS],
    stdout=subprocess.PIPE,
).stdout
if not diff:
    raise SystemExit("No selected 2.7 feature changes were found between the custom and upgrade branches.")
run(["git", "apply", "--check"], input=diff)
run(["git", "apply"], input=diff)

# These screens and their support APIs must move together. Copy them explicitly so missing
# diff entries cannot leave the custom base with an older component contract.
for support_path in (
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/ValueSlider.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/LiquidGlassContainer.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/expect/ui/LiquidGlass.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/expect/ui/DisplayCorner.kt",
    "composeApp/src/androidMain/kotlin/com/maxrave/simpmusic/expect/ui/DisplayCorner.android.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/expect/ui/DisplayCorner.jvm.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/SongSelectionViewModel.kt",
):
    content = run(["git", "show", f"{UPGRADE}:{support_path}"], text=True, stdout=subprocess.PIPE).stdout
    target = ROOT / support_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)

# The carousel API in the selected dependency set renamed this argument.
home_styles = ROOT / "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/HomeSectionStyles.kt"
if home_styles.is_file():
    source = home_styles.read_text()
    source = source.replace("maxItemWidth = heroWidth,", "preferredItemWidth = heroWidth,")
    home_styles.write_text(source)

# Make the newly ported Radio Builder discoverable without relying on the
# secondary Create sheet. The route and screen were copied above, but an unreachable
# destination is not a user-facing feature.
LIBRARY_SCREEN = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/library/LibraryScreen.kt"
def expose_radio_builder(source: str) -> str:
    import_anchor = "import androidx.compose.material3.Text\n"
    if "import androidx.compose.material3.TextButton\n" not in source:
        source = replace_once(source, import_anchor, import_anchor + "import androidx.compose.material3.TextButton\n", "Radio Builder button import")
    destination_anchor = "import com.maxrave.simpmusic.ui.navigation.destination.home.ListenTogetherDestination\n"
    if "import com.maxrave.simpmusic.ui.navigation.destination.home.RadioBuilderDestination\n" not in source:
        source = replace_once(source, destination_anchor, destination_anchor + "import com.maxrave.simpmusic.ui.navigation.destination.home.RadioBuilderDestination\n", "Radio Builder destination import")
    action_anchor = "                ListenTogetherIconButton { navController.navigate(ListenTogetherDestination) }\n"
    radio_action = action_anchor + "                TextButton(onClick = { navController.navigate(RadioBuilderDestination) }) { Text(\"Radio Builder\") }\n"
    if "navController.navigate(RadioBuilderDestination)" not in source:
        source = replace_once(source, action_anchor, radio_action, "Visible Radio Builder library action")
    return source
edit(LIBRARY_SCREEN, expose_radio_builder)


# Replay Mix is explicitly excluded from V17. Remove its UI, state, routing and
# data-loader branches from the selected 2.7 files while preserving unrelated library work.
def remove_kotlin_block(source: str, start_pattern: str, label: str) -> str:
    match = re.search(start_pattern, source, re.MULTILINE)
    if not match:
        return source
    opening = source.find("{", match.end())
    if opening < 0:
        raise SystemExit(f"{label}: opening brace not found")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                finish = index + 1
                if finish < len(source) and source[finish] == "\n":
                    finish += 1
                return source[:match.start()] + source[finish:]
    raise SystemExit(f"{label}: unterminated Kotlin block")

def remove_when_branch(source: str, marker: str, label: str) -> str:
    lines = source.splitlines(keepends=True)
    index = 0
    removed = 0
    while index < len(lines):
        line = lines[index]
        if marker not in line or "->" not in line:
            index += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        branch = [line]
        # Braced branches are removed by balanced-brace depth.
        if "{" in line:
            depth = line.count("{") - line.count("}")
            index += 1
            while depth > 0 and index < len(lines):
                depth += lines[index].count("{") - lines[index].count("}")
                branch.append(lines[index])
                index += 1
            if depth != 0:
                raise SystemExit(f"{label}: unterminated braced branch")
        else:
            index += 1
            # Expression branches can continue over multiple lines. Stop at the next
            # sibling case or the closing brace of the surrounding when expression.
            while index < len(lines):
                candidate = lines[index]
                stripped = candidate.lstrip(" ")
                candidate_indent = len(candidate) - len(stripped)
                if candidate.strip() == "}":
                    break
                if candidate_indent == indent and "->" in candidate:
                    break
                branch.append(candidate)
                index += 1
        removed += 1
        lines[index:index] = []
        # Continue at the same index because the next branch shifted into place.
    if removed == 0:
        return source
    return "".join(lines)

def remove_doc_and_declaration(source: str, doc_marker: str, declaration_pattern: str, label: str) -> str:
    doc_start = source.find(doc_marker)
    declaration = re.search(declaration_pattern, source, re.MULTILINE)
    if declaration is None:
        return source
    if doc_start >= 0 and doc_start < declaration.start():
        return source[:doc_start] + source[declaration.end():]
    return source[:declaration.start()] + source[declaration.end():]

def strip_replay_mix():
    tiling_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/LibraryTilingBox.kt"
    tiling = (ROOT / tiling_path).read_text()
    tiling = "\n".join(
        line for line in tiling.split("\n")
        if "generated.resources.replay_mix" not in line
        and "replayMix: LibraryCollectionPreview?" not in line
        and "showReplayMix: Boolean" not in line
    )
    tiling = re.sub(
        r"/\*\*\n \* The collections at the top of the Your library tab:.*?\n \*/",
        "/** The collections at the top of the Your library tab. */",
        tiling,
        count=1,
        flags=re.DOTALL,
    )
    tiling = remove_kotlin_block(tiling, r"^[ \t]*if \(showReplayMix\) \{", "Replay Mix library card")
    if re.search(r"ReplayMix|replayMix|replay_mix|showReplayMix", tiling):
        raise SystemExit("Replay Mix references remain in LibraryTilingBox after V17 exclusion.")
    (ROOT / tiling_path).write_text(tiling)

    library_screen_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/library/LibraryScreen.kt"
    library_screen = (ROOT / library_screen_path).read_text()
    library_screen = remove_kotlin_block(
        library_screen,
        r"^[ \t]*LaunchedEffect\(localTrackingEnabled\) \{",
        "Replay Mix library preview refresh",
    )
    library_screen = "\n".join(
        line for line in library_screen.split("\n")
        if "val replayMixPreview by " not in line
        and "replayMix = replayMixPreview" not in line
        and "showReplayMix = localTrackingEnabled" not in line
        and "Replay Mix is ranked from playback_event" not in line
    )
    if re.search(r"ReplayMix|replayMix|replay_mix|showReplayMix", library_screen):
        raise SystemExit("Replay Mix references remain in LibraryScreen after V17 exclusion.")
    (ROOT / library_screen_path).write_text(library_screen)

    dynamic_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/library/LibraryDynamicPlaylistScreen.kt"
    dynamic = (ROOT / dynamic_path).read_text()
    dynamic = "\n".join(
        line for line in dynamic.split("\n")
        if "generated.resources.replay_mix" not in line
        and "val replayMix by " not in line
        and "var tempReplayMix by " not in line
        and "tempReplayMix = replayMix.filter" not in line
        and "Read on every visit too: the mix changes once a day." not in line
    )
    dynamic = remove_kotlin_block(
        dynamic,
        r"^[ \t]*if \(parsed == LibraryDynamicPlaylistType\.ReplayMix\) \{",
        "Replay Mix dynamic-list refresh",
    )
    for marker, label in (
        ("LibraryDynamicPlaylistType.ReplayMix", "Replay Mix dynamic-list branch"),
        ("ReplayMix", "Replay Mix type branch"),
    ):
        dynamic = remove_when_branch(dynamic, marker, label)
    dynamic = re.sub(
        r"^[ \t]*/\*\*\n[ \t]*\* The local Replay Mix:.*?\n[ \t]*data object ReplayMix : LibraryDynamicPlaylistType\(\)\n\n",
        "",
        dynamic,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    dynamic = re.sub(r"^[ \t]*ReplayMix -> Res\.string\.replay_mix\n", "", dynamic, flags=re.MULTILINE)
    dynamic = re.sub(r'^[ \t]*"replay_mix" -> ReplayMix\n', "", dynamic, flags=re.MULTILINE)
    if re.search(r"ReplayMix|replayMix|replay_mix|tempReplayMix", dynamic):
        raise SystemExit("Replay Mix references remain in LibraryDynamicPlaylistScreen after V17 exclusion.")
    (ROOT / dynamic_path).write_text(dynamic)

    dynamic_vm_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/LibraryDynamicPlaylistViewModel.kt"
    dynamic_vm = (ROOT / dynamic_vm_path).read_text()
    dynamic_vm = re.sub(
        r"^[ \t]*/\*\* The local Replay Mix, loaded on demand like the recap: see \[loadReplayMixSongs\]\. \*/\n"
        r"[ \t]*private val _listReplayMixSong:.*?\n[ \t]*val listReplayMixSong:.*?\n",
        "",
        dynamic_vm,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    dynamic_vm = remove_kotlin_block(dynamic_vm, r"^[ \t]*fun getReplayMixSong\(\) \{", "Replay Mix loader method")
    dynamic_vm = re.sub(
        r"^[ \t]*// A mix is named on its own, as YouTube's mixes are:.*?\n"
        r"[ \t]*if \(type == LibraryDynamicPlaylistType\.ReplayMix\) return name\n",
        "",
        dynamic_vm,
        count=1,
        flags=re.MULTILINE,
    )
    dynamic_vm = re.sub(
        r"^[ \t]*/\*\* Replay Mix plays as a radio and is extended once it runs out; every other list just ends\. \*/\n"
        r"[ \t]*private fun queueId\(type: LibraryDynamicPlaylistType\): String\? =\n"
        r"[ \t]*if \(type == LibraryDynamicPlaylistType\.ReplayMix\) REPLAY_MIX_PLAYLIST_ID else null\n\n",
        "",
        dynamic_vm,
        count=1,
        flags=re.MULTILINE,
    )
    dynamic_vm = dynamic_vm.replace("playlistId = queueId(type),", "playlistId = null,")
    dynamic_vm = remove_when_branch(dynamic_vm, "LibraryDynamicPlaylistType.ReplayMix", "Replay Mix view-model branch")
    dynamic_vm = re.sub(
        r"/\*\*\n \* The local Replay Mix: the songs played most in the last \[REPLAY_MIX_WEEK_DAYS\].*?"
        r"private const val REPLAY_MIX_LIMIT = 100\n\n",
        "",
        dynamic_vm,
        count=1,
        flags=re.DOTALL,
    )
    if re.search(r"ReplayMix|replayMix|REPLAY_MIX|replay_mix|loadReplayMixSongs", dynamic_vm):
        raise SystemExit("Replay Mix references remain in LibraryDynamicPlaylistViewModel after V17 exclusion.")
    (ROOT / dynamic_vm_path).write_text(dynamic_vm)

    library_vm_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/LibraryViewModel.kt"
    library_vm = (ROOT / library_vm_path).read_text()
    library_vm = re.sub(
        r"^[ \t]*/\*\* The Replay Mix card's count and top artwork, read each time the screen is shown: it changes daily\. \*/\n"
        r"[ \t]*private val _replayMixPreview:.*?\n[ \t]*val replayMixPreview:.*?\n",
        "",
        library_vm,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    library_vm = remove_kotlin_block(
        library_vm,
        r"^[ \t]*fun refreshReplayMixPreview\(\) \{",
        "Replay Mix preview refresh method",
    )
    if re.search(r"ReplayMix|replayMix|REPLAY_MIX|replay_mix|loadReplayMixSongs", library_vm):
        raise SystemExit("Replay Mix references remain in LibraryViewModel after V17 exclusion.")
    (ROOT / library_vm_path).write_text(library_vm)

strip_replay_mix()


print("Applied the selected 2.7 app, library, lyrics, theme, equalizer and desktop changes.")

# Add only resources used by the selected features. Search Settings, app icons and AI-provider
# resources are deliberately excluded.
resource_path = "composeApp/src/commonMain/composeResources/values/strings.xml"
source_resources = run(
    ["git", "show", f"{UPGRADE}:{resource_path}"],
    text=True, stdout=subprocess.PIPE,
).stdout
resource_keys = (
    "theme_mode_amoled",
    "animated_lyrics_background",
    "animated_lyrics_background_description",
    "lyrics_background_pulse",
    "lyrics_background_pulse_description",
    "lyrics_background_pulse_needs_animated",
    "scroll_long_text",
    "scroll_long_text_description",
    "create_radio_description",
    "delete_lyrics",
    "delete_lyrics_confirm",
)
def add_selected_resources(source: str) -> str:
    additions = []
    for key in resource_keys:
        pattern = re.compile(r'<string\s+name="' + re.escape(key) + r'"[^>]*>.*?</string>', re.DOTALL)
        matches = pattern.findall(source_resources)
        if len(matches) != 1:
            raise SystemExit(f"Expected one upstream resource for {key}, found {len(matches)}")
        existing = re.findall(r'<string\s+name="' + re.escape(key) + r'"(?:\s|>)', source)
        if len(existing) > 1:
            raise SystemExit(f"Duplicate resource already exists: {key}")
        if not existing:
            additions.append("    " + matches[0].strip())
    if additions:
        source = replace_once(source, "</resources>", "\n".join(additions) + "\n</resources>", "resource insertion")
    return source
edit(resource_path, add_selected_resources)

SETTINGS = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/home/SettingScreen.kt"
def patch_settings(source: str) -> str:
    import_anchor = "import simpmusic.composeapp.generated.resources.theme_mode_light\n"
    imports = (
        "import simpmusic.composeapp.generated.resources.theme_mode_amoled\n"
        "import simpmusic.composeapp.generated.resources.animated_lyrics_background\n"
        "import simpmusic.composeapp.generated.resources.animated_lyrics_background_description\n"
        "import simpmusic.composeapp.generated.resources.lyrics_background_pulse\n"
        "import simpmusic.composeapp.generated.resources.lyrics_background_pulse_description\n"
        "import simpmusic.composeapp.generated.resources.lyrics_background_pulse_needs_animated\n"
        "import simpmusic.composeapp.generated.resources.scroll_long_text\n"
        "import simpmusic.composeapp.generated.resources.scroll_long_text_description\n"
    )
    if "import simpmusic.composeapp.generated.resources.theme_mode_amoled\n" not in source:
        source = replace_once(source, import_anchor, import_anchor + imports, "SettingsScreen resource imports")

    if "val animatedLyricsBackground by viewModel.animatedLyricsBackground.collectAsStateWithLifecycle()" not in source:
        state_anchor = "    val enableLiquidGlass by viewModel.enableLiquidGlass.collectAsStateWithLifecycle()\n"
        state_addition = (
            "    val scrollLongText by viewModel.titleMarquee.collectAsStateWithLifecycle()\n"
            "    val animatedLyricsBackground by viewModel.animatedLyricsBackground.collectAsStateWithLifecycle()\n"
            "    val lyricsBackgroundPulse by viewModel.lyricsBackgroundPulse.collectAsStateWithLifecycle()\n"
        )
        source = replace_once(source, state_anchor, state_anchor + state_addition, "SettingsScreen state collectors")

    theme_anchor = "                            DataStoreManager.THEME_MODE_LIGHT to stringResource(Res.string.theme_mode_light),\n"
    if "DataStoreManager.THEME_MODE_AMOLED to stringResource(Res.string.theme_mode_amoled)" not in source:
        source = replace_once(
            source, theme_anchor,
            theme_anchor + "                            DataStoreManager.THEME_MODE_AMOLED to stringResource(Res.string.theme_mode_amoled),\n",
            "AMOLED theme option",
        )

    glass_block = (
        "                    SettingItem(\n"
        "                        title = stringResource(Res.string.enable_liquid_glass_effect),\n"
        "                        subtitle = stringResource(Res.string.enable_liquid_glass_effect_description),\n"
        "                        smallSubtitle = true,\n"
        "                        switch = (enableLiquidGlass to { viewModel.setEnableLiquidGlass(it) }),\n"
        "                    )"
    )
    if "viewModel.setTitleMarquee(it)" not in source:
        source = replace_once(
            source, glass_block,
            glass_block + "\n                    SettingItem(\n"
            "                        title = stringResource(Res.string.scroll_long_text),\n"
            "                        subtitle = stringResource(Res.string.scroll_long_text_description),\n"
            "                        smallSubtitle = true,\n"
            "                        switch = (scrollLongText to { viewModel.setTitleMarquee(it) }),\n"
            "                    )",
            "Scroll long text setting",
        )

    lyrics_anchor = (
        "\n                    }\n\n"
        "                    // Independent of BOTH style settings, and not gated on Android 12:"
    )
    if "viewModel.setAnimatedLyricsBackground(it)" not in source:
        lyrics_controls = (
            "\n                        SettingItem(\n"
            "                            title = stringResource(Res.string.animated_lyrics_background),\n"
            "                            subtitle = stringResource(Res.string.animated_lyrics_background_description),\n"
            "                            switch = (animatedLyricsBackground to { viewModel.setAnimatedLyricsBackground(it) }),\n"
            "                        )\n"
            "                        SettingItem(\n"
            "                            title = stringResource(Res.string.lyrics_background_pulse),\n"
            "                            subtitle = stringResource(\n"
            "                                if (animatedLyricsBackground) Res.string.lyrics_background_pulse_description\n"
            "                                else Res.string.lyrics_background_pulse_needs_animated,\n"
            "                            ),\n"
            "                            switch = (lyricsBackgroundPulse to { viewModel.setLyricsBackgroundPulse(it) }),\n"
            "                            isEnable = animatedLyricsBackground,\n"
            "                        )"
        )
        source = replace_once(source, lyrics_anchor, lyrics_controls + lyrics_anchor, "Animated lyrics settings")

    return source
edit(SETTINGS, patch_settings)

# The custom Insights App.kt comes from its archive. Add the 2.7 title-marquee preference without
# replacing the custom Insights navigation or Analytics screen.
APP = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/App.kt"
def patch_app(source: str) -> str:
    state_anchor = "    val isLiquidGlassEnabled by viewModel.getEnableLiquidGlass().collectAsStateWithLifecycle(DataStoreManager.FALSE)\n"
    state_line = "    val titleMarquee by viewModel.getTitleMarquee().collectAsStateWithLifecycle(true)\n"
    if state_line not in source:
        source = replace_once(source, state_anchor, state_anchor + state_line, "App title-marquee state")
    theme_anchor = "        liquidGlassEnabled = isLiquidGlassEnabled == TRUE,\n"
    theme_line = "        titleMarquee = titleMarquee,\n"
    if theme_line not in source:
        source = replace_once(source, theme_anchor, theme_anchor + theme_line, "App title-marquee theme binding")
    return source
edit(APP, patch_app)

# Port only the three selected non-AI preferences. Do not copy the full 2.7
# SettingsViewModel or SharedViewModel: those files also contain unrelated AI and Analytics work.
SETTINGS_VM = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/SettingsViewModel.kt"
def patch_settings_view_model(source: str) -> str:
    constants = (
        'const val TITLE_MARQUEE_KEY = "title_marquee"\n'
        'const val ANIMATED_LYRICS_BACKGROUND_KEY = "animated_lyrics_background"\n'
        'const val LYRICS_BACKGROUND_PULSE_KEY = "lyrics_background_pulse"\n\n'
    )
    if "const val ANIMATED_LYRICS_BACKGROUND_KEY" not in source:
        source = replace_once(source, "class SettingsViewModel(\n", constants + "class SettingsViewModel(\n", "selected preference keys")

    state_anchor = "    private var _enableLiquidGlass: MutableStateFlow<Boolean> = MutableStateFlow(false)\n    val enableLiquidGlass: StateFlow<Boolean> = _enableLiquidGlass\n"

    state_addition = (
        "    private val _titleMarquee = MutableStateFlow(true)\n"
        "    val titleMarquee: StateFlow<Boolean> = _titleMarquee\n"
        "    private val _animatedLyricsBackground = MutableStateFlow(false)\n"
        "    val animatedLyricsBackground: StateFlow<Boolean> = _animatedLyricsBackground\n"
        "    private val _lyricsBackgroundPulse = MutableStateFlow(false)\n"
        "    val lyricsBackgroundPulse: StateFlow<Boolean> = _lyricsBackgroundPulse\n"
    )
    if "_titleMarquee" not in source:
        source = replace_once(source, state_anchor, state_anchor + state_addition, "selected preference state")

    init_anchor = "        getUpdateChannel()\n        getEnableLiquidGlass()\n        getExplicitContentEnabled()\n"
    init_addition = (
        "        viewModelScope.launch { dataStoreManager.getString(\"title_marquee\").collect { _titleMarquee.value = it != DataStoreManager.FALSE } }\n"
        "        viewModelScope.launch { dataStoreManager.getString(\"animated_lyrics_background\").collect { _animatedLyricsBackground.value = it == DataStoreManager.TRUE } }\n"
        "        viewModelScope.launch { dataStoreManager.getString(\"lyrics_background_pulse\").collect { _lyricsBackgroundPulse.value = it == DataStoreManager.TRUE } }\n"
    )
    if "getString(\"title_marquee\")" not in source:
        source = replace_once(source, init_anchor, init_anchor + init_addition, "selected preference collectors")

    setter_anchor = (
        "    fun setEnableLiquidGlass(enableLiquidGlass: Boolean) {\n"
        "        viewModelScope.launch {\n"
        "            dataStoreManager.setEnableLiquidGlass(enableLiquidGlass)\n"
        "            getEnableLiquidGlass()\n"
        "        }\n"
        "    }\n"
    )
    setters = (
        "\n    fun setTitleMarquee(enabled: Boolean) {\n"
        "        viewModelScope.launch { dataStoreManager.putString(\"title_marquee\", if (enabled) DataStoreManager.TRUE else DataStoreManager.FALSE) }\n"
        "    }\n"
        "    fun setAnimatedLyricsBackground(enabled: Boolean) {\n"
        "        viewModelScope.launch { dataStoreManager.putString(\"animated_lyrics_background\", if (enabled) DataStoreManager.TRUE else DataStoreManager.FALSE) }\n"
        "    }\n"
        "    fun setLyricsBackgroundPulse(enabled: Boolean) {\n"
        "        viewModelScope.launch { dataStoreManager.putString(\"lyrics_background_pulse\", if (enabled) DataStoreManager.TRUE else DataStoreManager.FALSE) }\n"
        "    }\n"
    )
    if "fun setTitleMarquee(" not in source:
        source = replace_once(source, setter_anchor, setter_anchor + setters, "selected preference setters")
    return source
edit(SETTINGS_VM, patch_settings_view_model)

SHARED_VM = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/SharedViewModel.kt"
def patch_shared_view_model(source: str) -> str:
    anchor = "    fun getEnableLiquidGlass() = dataStoreManager.enableLiquidGlass\n"
    addition = "    fun getTitleMarquee(): Flow<Boolean> = dataStoreManager.getString(\"title_marquee\").map { it != FALSE }\n"
    if "fun getTitleMarquee()" not in source:
        source = replace_once(source, anchor, anchor + addition, "title marquee getter")

    delete_methods = """
    /**
     * Remove the exact lyrics shown when the song menu was opened, without changing the custom
     * Insights or playback code in this viewmodel.
     */
    fun deleteLyrics(shown: NowPlayingScreenData.LyricsData) {
        val videoId = shown.videoId
        val onScreen = _nowPlayingScreenData.value.lyricsData
        if (onScreen != null && onScreen.videoId == videoId && onScreen.lyrics == shown.lyrics) {
            resetLyricsVoteState()
            _nowPlayingScreenData.update { it.copy(lyricsData = null, lyricsNotFound = true) }
        }
        val translatedId = shown.translatedLyrics?.takeIf { it.second == LyricsProvider.SIMPMUSIC }?.first?.simpMusicLyrics?.id
        viewModelScope.launch {
            lyricsCanvasRepository.deleteLyrics(
                videoId,
                listOfNotNull(
                    shown.lyrics.id
                        ?.takeIf { shown.lyricsProvider != LyricsProvider.OFFLINE }
                        ?.let { shown.lyricsProvider.name to it },
                    translatedId?.let { LyricsProvider.SIMPMUSIC.name to it },
                ),
            )
        }
        val lyricsId = shown.lyrics.simpMusicLyrics?.id
        if (shown.lyricsProvider == LyricsProvider.SIMPMUSIC && lyricsId != null) {
            viewModelScope.launch { removeFromSimpMusic(lyricsId, translated = false) }
        }
        if (translatedId != null) {
            viewModelScope.launch { removeFromSimpMusic(translatedId, translated = true) }
        }
    }

    private suspend fun removeFromSimpMusic(
        id: String,
        translated: Boolean,
    ) {
        val email = dataStoreManager.contributorEmail.first().trim()
        val deleted =
            email.isNotEmpty() &&
                (
                    if (translated) {
                        lyricsCanvasRepository.deleteSimpMusicTranslatedLyrics(id, email)
                    } else {
                        lyricsCanvasRepository.deleteSimpMusicLyrics(id, email)
                    }
                ).first() is Resource.Success
        if (!deleted) {
            if (translated) {
                lyricsCanvasRepository.voteSimpMusicTranslatedLyrics(id, false).first()
            } else {
                lyricsCanvasRepository.voteSimpMusicLyrics(id, false).first()
            }
        }
    }

"""
    if "fun deleteLyrics(" not in source:
        source = replace_once(
            source,
            "    fun loadSharedMediaItem(videoId: String) {",
            delete_methods + "    fun loadSharedMediaItem(videoId: String) {",
            "Delete Lyrics action",
        )

    # The Insights archive restores the pre-2.7 Spotify lyrics call. The upgraded core
    # requires title and artists so it can rank Spotify lyric matches against the track.
    legacy_spotify_call = "lyricsCanvasRepository.getSpotifyLyrics(dataStoreManager, query, duration)"
    upgraded_spotify_call = (
        "lyricsCanvasRepository.getSpotifyLyrics(\n"
        "                    dataStoreManager,\n"
        "                    query,\n"
        "                    duration,\n"
        "                    track.title,\n"
        "                    track.artists?.map { it.name }.orEmpty(),\n"
        "                )"
    )
    if legacy_spotify_call in source:
        source = replace_once(
            source,
            legacy_spotify_call,
            upgraded_spotify_call,
            "2.7 Spotify lyrics title and artist arguments",
        )
    elif upgraded_spotify_call not in source:
        raise SystemExit("Spotify lyrics API mismatch: neither legacy nor upgraded call was found.")
    return source
edit(SHARED_VM, patch_shared_view_model)

# The custom 2.6 lyrics state did not carry the song id. V17's Delete Lyrics action must
# retain the exact song identity even if playback changes while the confirmation sheet is open.
def patch_lyrics_identity(source: str) -> str:
    data_anchor = (
        "    data class LyricsData(\n"
        "        val lyrics: Lyrics,\n"
    )
    if "data class LyricsData(\n        val videoId: String" not in source:
        source = replace_once(
            source,
            data_anchor,
            "    data class LyricsData(\n        val videoId: String = \"\",\n        val lyrics: Lyrics,\n",
            "LyricsData song identity",
        )
    constructor_anchor = (
        "                                NowPlayingScreenData.LyricsData(\n"
        "                                    lyrics = lyrics,\n"
    )
    if "NowPlayingScreenData.LyricsData(\n                                    videoId = videoId," not in source:
        source = replace_once(
            source,
            constructor_anchor,
            "                                NowPlayingScreenData.LyricsData(\n"
            "                                    videoId = videoId,\n"
            "                                    lyrics = lyrics,\n",
            "LyricsData song identity assignment",
        )
    return source
edit(SHARED_VM, patch_lyrics_identity)

# The newer core requires the exact playlist-row id when deleting. Resolve it before removing
# the row so duplicate copies of a song are handled safely.
NOW_PLAYING_VM = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/NowPlayingBottomSheetViewModel.kt"
def patch_bottom_sheet_pair_id(source: str) -> str:
    import_line = "import kotlinx.coroutines.flow.lastOrNull\n"
    if "import kotlinx.coroutines.flow.firstOrNull\n" not in source:
        source = replace_once(source, import_line, import_line + "import kotlinx.coroutines.flow.firstOrNull\n", "playlist pair lookup import")
    old = """                    localPlaylistRepository
                        .removeTrackFromLocalPlaylist(
                            id = ev.playlistId,
                            song =
                                songRepository.getSongById(ev.videoId).lastOrNull() ?: run {
                                    makeToast(getString(Res.string.error_occurred))
                                    return@launch
                                },
                            successMessage = getString(Res.string.delete_song_from_playlist),
"""
    new = """                    val song =
                        songRepository.getSongById(ev.videoId).lastOrNull() ?: run {
                            makeToast(getString(Res.string.error_occurred))
                            return@launch
                        }
                    val pairId =
                        localPlaylistRepository.getPlaylistPairOfSong(ev.playlistId, ev.videoId).firstOrNull()?.id
                            ?: run {
                                makeToast(getString(Res.string.error_occurred))
                                return@launch
                            }
                    localPlaylistRepository
                        .removeTrackFromLocalPlaylist(
                            id = ev.playlistId,
                            song = song,
                            pairId = pairId,
                            successMessage = getString(Res.string.delete_song_from_playlist),
"""
    if "pairId = pairId," not in source:
        source = replace_once(source, old, new, "single-row playlist removal pair id")
    return source
edit(NOW_PLAYING_VM, patch_bottom_sheet_pair_id)

# Add only the non-AI V17 preference keys to the settings-sync allowlist.
SYNC_SETTINGS = "androidApp/src/main/java/com/maxrave/simpmusic/cloudsync/CloudSyncSettingsSync.kt"
def patch_sync_keys(source: str) -> str:
    source = replace_once(
        source,
        '"now_playing_style", "liquid_glass",',
        '"now_playing_style", "liquid_glass", "title_marquee",',
        "Synced appearance preferences",
    )
    source = replace_once(
        source,
        '"preferred_audio_language",',
        '"preferred_audio_language", "animated_lyrics_background", "lyrics_background_pulse",',
        "Synced lyrics preferences",
    )
    if '"ai_provider"' in source or '"custom_model_id"' in source:
        raise SystemExit("AI-provider settings must not be included in the V17 sync allowlist.")
    return source
edit(SYNC_SETTINGS, patch_sync_keys)

# Explicitly protect the custom Insights implementation and the already-working shuffle fix.
for forbidden in (
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/home/analytics/AnalyticsScreen.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/AnalyticsViewModel.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/PlaylistViewModel.kt",
):
    if not (ROOT / forbidden).is_file():
        raise SystemExit(f"Protected custom source disappeared: {forbidden}")
if "CUSTOM_RANGE" not in (ROOT / "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/home/analytics/AnalyticsScreen.kt").read_text():
    raise SystemExit("The custom Insights screen was unexpectedly replaced.")
if "allTracks.shuffled()" not in (ROOT / "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/PlaylistViewModel.kt").read_text():
    raise SystemExit("The custom full-playlist shuffle fallback was unexpectedly replaced.")

run(["git", "diff", "--check"])
print("Selected 2.7 feature port complete. Custom Insights, custom shuffle, and AI-provider UI remain excluded.")
