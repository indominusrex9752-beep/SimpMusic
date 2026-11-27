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
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/home/EqualizerSection.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/ModalBottomSheet.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/FullscreenLyricsContent.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/LyricsFlowBackground.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/player/NowPlayingScreen.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/SharedViewModel.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/SettingsViewModel.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/theme/Theme.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/theme/Color.kt",
    "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/extension/UIExt.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/extension/UIExt.jvm.kt",
    "composeApp/src/jvmMain/kotlin/com/maxrave/simpmusic/DesktopApp.kt",
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
run(["git", "cat-file", "-e", f"{BASE}^{{commit}}"])
run(["git", "cat-file", "-e", f"{UPGRADE}^{{commit}}"])
diff = run(
    ["git", "diff", "--binary", "--no-ext-diff", BASE, UPGRADE, "--", *FEATURE_PATHS],
    stdout=subprocess.PIPE,
).stdout
if not diff:
    raise SystemExit("No selected 2.7 feature changes were found between the custom and upgrade branches.")
run(["git", "apply", "--check", "-"], input=diff)
run(["git", "apply", "-"], input=diff)
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
    "replay_mix",
    "replay_mix_subtitle",
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

    # Expose the selected YouTube identity in the existing account picker, without adding AI settings.
    account_anchor = (
        "                val googleAccounts by viewModel.googleAccounts.collectAsStateWithLifecycle(\n"
        "                    minActiveState = Lifecycle.State.RESUMED,\n"
        "                )\n"
    )
    if "val selectedYouTubeGoogleEmail by viewModel.selectedYouTubeGoogleEmail.collectAsStateWithLifecycle" not in source:
        source = replace_once(
            source, account_anchor,
            account_anchor +
            "                val selectedYouTubeGoogleEmail by viewModel.selectedYouTubeGoogleEmail.collectAsStateWithLifecycle(\n"
            "                    minActiveState = Lifecycle.State.RESUMED,\n"
            "                )\n",
            "Selected YouTube identity state",
        )
    email_anchor = "                                        Text(it.email, style = typo().bodySmall)\n"
    diagnostic = (
        "                                        Text(it.email, style = typo().bodySmall)\n"
        "                                        if (it.isUsed && getPlatform() == Platform.Android) {\n"
        "                                            val selectedGoogleEmail = selectedYouTubeGoogleEmail?.trim()?.takeIf { email -> email.isNotBlank() }\n"
        "                                            Text(\n"
        "                                                text = selectedGoogleEmail?.let { email ->\n"
        "                                                    \"YouTube Google email: $email\"\n"
        "                                                } ?: \"SimpCloud matching unavailable: Google email for this YouTube account could not be verified. Sync remains disabled.\",\n"
        "                                                style = typo().bodySmall,\n"
        "                                                color = if (selectedGoogleEmail == null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,\n"
        "                                                maxLines = 2,\n"
        "                                            )\n"
        "                                        }\n"
    )
    if "SimpCloud matching unavailable" not in source:
        source = replace_once(source, email_anchor, diagnostic, "Selected-account diagnostic")
    if "import com.maxrave.simpmusic.getPlatform\n" not in source and "getPlatform()" in source:
        source = replace_once(
            source, "import com.maxrave.simpmusic.Platform\n",
            "import com.maxrave.simpmusic.Platform\nimport com.maxrave.simpmusic.getPlatform\n",
            "getPlatform import",
        )
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
