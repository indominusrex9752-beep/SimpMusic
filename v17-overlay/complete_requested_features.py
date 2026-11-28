#!/usr/bin/env python3
"""Complete selected V17 features without replacing custom cloud-sync or Insights code."""
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

# SettingItem lives in commonMain. java.text.Normalizer is JVM-only and cannot be imported
# by Kotlin Multiplatform common code, so keep Settings search normalization portable.
setting_item_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/component/SettingItem.kt"
setting_item = (ROOT / setting_item_path).read_text()
setting_item = setting_item.replace(
    "/** Lower case, accents dropped and đ read as d, so typing \"loi bai hat\" finds \"Lời bài hát\". */",
    "/** Case-insensitive Settings search with Vietnamese đ/Đ normalized to d. */",
)
setting_item = setting_item.replace("import java.text.Normalizer\n", "")
normalizer_block = """fun searchKey(text: String): String =
    Normalizer
        .normalize(text.lowercase(), Normalizer.Form.NFD)
        .replace(CombiningMarks, "")
        .replace('đ', 'd')
"""
portable_search_key = """fun searchKey(text: String): String = text.lowercase().replace('đ', 'd')
"""
if normalizer_block in setting_item:
    setting_item = replace_once(setting_item, normalizer_block, portable_search_key, "Multiplatform Settings search normalization")
elif "fun searchKey(text: String): String = text.lowercase().replace('đ', 'd')" not in setting_item:
    raise SystemExit("Could not make Settings search normalization Kotlin Multiplatform-safe.")
setting_item = "\n".join(line for line in setting_item.splitlines() if not line.startswith("private val CombiningMarks")) + "\n"
(ROOT / setting_item_path).write_text(setting_item)

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
    main_launcher = '                <category android:name="android.intent.category.LAUNCHER" />\n'
    if manifest.count(main_launcher) != 1:
        raise SystemExit("Expected exactly one legacy MainActivity launcher category before adding icon aliases.")
    manifest = replace_once(manifest, main_launcher, "", "Move launcher entry to selectable app-icon aliases")
    start = official_manifest.find("        <!-- Selectable app icons")
    end = official_manifest.find("        <provider", start)
    if start < 0 or end < 0:
        raise SystemExit("Could not isolate official app-icon activity aliases.")
    aliases = official_manifest[start:end]
    provider_anchor = '        <provider\n            android:name="androidx.startup.InitializationProvider"'
    manifest = replace_once(manifest, provider_anchor, aliases + provider_anchor, "App icon manifest aliases")
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
search_anchor = "                SettingGroup(\n                    title = stringResource(Res.string.login_sync_section),\n"
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

# The animated-lyrics preference must remain visible on Android 9-11 even though its
# blurred artwork effect is only rendered on Android 12+ (rememberAnimatedLyricsBackground
# enforces the platform capability). apply_selected_2_7_features.py initially inserts this row
# inside the style gate, so move only this row outside and leave the pulse control gated.
animated_row_old = """                        SettingItem(
                            title = stringResource(Res.string.animated_lyrics_background),
                            subtitle = stringResource(Res.string.animated_lyrics_background_description),
                            switch = (animatedLyricsBackground to { viewModel.setAnimatedLyricsBackground(it) }),
                        )
"""
animated_row_new = """                    SettingItem(
                        title = stringResource(Res.string.animated_lyrics_background),
                        subtitle = stringResource(Res.string.animated_lyrics_background_description) +
                            if (isLyricsBlurSupported()) "" else requiresAndroid12,
                        switch = (animatedLyricsBackground to { viewModel.setAnimatedLyricsBackground(it) }),
                    )
"""
if animated_row_old in settings:
    settings = replace_once(settings, animated_row_old, "", "Extract animated lyrics preference from Android 12 gate")
    gate_end = "\n                    }\n\n                    // Independent of BOTH style settings"
    if gate_end not in settings:
        raise SystemExit("Could not locate the end of the Android 12 lyrics-style gate.")
    settings = replace_once(
        settings,
        gate_end,
        "\n                    }\n\n" + animated_row_new + "                    // Independent of BOTH style settings",
        "Place animated lyrics preference outside Android 12 gate",
    )
elif animated_row_new not in settings:
    raise SystemExit("Could not locate the animated lyrics preference inserted by the selected-feature port.")

animated_row = settings.index("title = stringResource(Res.string.animated_lyrics_background)")
lyrics_gate = settings.rfind("if (isLyricsBlurSupported())", 0, animated_row)
if lyrics_gate >= 0 and "\n                    }\n\n" not in settings[lyrics_gate:animated_row]:
    raise SystemExit("Animated lyrics preference is still nested inside the Android 12-only section.")
if "requiresAndroid12" not in settings[animated_row:animated_row + 500]:
    raise SystemExit("Animated lyrics option does not explain the Android 12 effect requirement.")
# The two alert-state values are checked immediately above, but delegated Compose state is not
# smart-cast by Kotlin. Use non-null assertions inside those guarded branches instead of return.
settings = settings.replace("val alertBasicState = basisAlertData ?: return", "val alertBasicState = basisAlertData!!")
settings = settings.replace("val alertState = alertData ?: return", "val alertState = alertData!!")
if "basisAlertData ?: return" in settings or "alertData ?: return" in settings:
    raise SystemExit("Illegal early return remains in Settings alert rendering.")
(ROOT / settings_path).write_text(settings)

# Guard against silently shipping a partial implementation.
checks = {
    settings_path: ("SearchTextField(", "CompositionLocalProvider(LocalSettingSearch provides searchText)", "currentAppIcon()", "setAppIcon(style)"),
    "composeApp/src/androidMain/kotlin/com/maxrave/simpmusic/expect/AppIcon.android.kt": ("setComponentEnabledSetting", "AppIconPixel"),
    manifest_path: ("AppIconLiquidGlass", "AppIconPixel"),
}
for path, markers in checks.items():
    content = (ROOT / path).read_text()
    for marker in markers:
        if marker not in content:
            raise SystemExit(f"Requested V17 feature wiring missing from {path}: {marker}")

print("V17 requested-feature integration: Settings search and Android app icon chooser wired.")


# V18 refinement: restore the official 2.7 Insights presentation after the custom archive merge.
# The custom AnalyticsViewModel and its playback-event repository remain in place.
copy_text("composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/home/analytics/AnalyticsScreen.kt")

# V18 refinement: restore the official app-icon preview thumbnails in the existing chooser.
settings_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/home/SettingScreen.kt"
settings = (ROOT / settings_path).read_text()
old_icon_options = """                        val options = listOf(
                            AppIconStyle.LIQUID_GLASS to stringResource(Res.string.app_icon_liquid_glass),
                            AppIconStyle.OLD_SCHOOL to stringResource(Res.string.app_icon_old_school),
                            AppIconStyle.MINIMALISM_LIGHT to stringResource(Res.string.app_icon_minimalism_light),
                            AppIconStyle.MINIMALISM_DARK to stringResource(Res.string.app_icon_minimalism_dark),
                            AppIconStyle.PIXEL to stringResource(Res.string.app_icon_pixel),
                        )
"""
new_icon_options = """                        val options = listOf(
                            Triple(AppIconStyle.LIQUID_GLASS, stringResource(Res.string.app_icon_liquid_glass), Res.drawable.app_icon_option_liquid_glass),
                            Triple(AppIconStyle.OLD_SCHOOL, stringResource(Res.string.app_icon_old_school), Res.drawable.app_icon_option_old_school),
                            Triple(AppIconStyle.MINIMALISM_LIGHT, stringResource(Res.string.app_icon_minimalism_light), Res.drawable.app_icon_option_minimalism_light),
                            Triple(AppIconStyle.MINIMALISM_DARK, stringResource(Res.string.app_icon_minimalism_dark), Res.drawable.app_icon_option_minimalism_dark),
                            Triple(AppIconStyle.PIXEL, stringResource(Res.string.app_icon_pixel), Res.drawable.app_icon_option_pixel),
                        )
"""
if old_icon_options in settings:
    settings = replace_once(settings, old_icon_options, new_icon_options, "V18 app icon preview options")
elif new_icon_options not in settings:
    raise SystemExit("Could not find the V17 app-icon chooser options to restore previews.")
preview_anchor = "                                            listSelect = options.map { (it.first == current) to it.second },\n"
preview_value = preview_anchor + "                                            icons = options.map { it.third },\n"
if preview_value not in settings:
    settings = replace_once(settings, preview_anchor, preview_value, "V18 app icon preview thumbnails")
(ROOT / settings_path).write_text(settings)

# V18 refinement: make Home's primary feed independent of mood, chart and new-release requests.
# The previous combine() withheld the home shelves until all four sources emitted at least once.
home_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/HomeViewModel.kt"
home_source = (ROOT / home_path).read_text()
home_start = home_source.find("    fun getHomeItemList(params: String? = null) {")
home_end = home_source.find("    /** A shelf's \"Play all\":", home_start)
if home_start < 0 or home_end < 0:
    raise SystemExit("Could not isolate HomeViewModel.getHomeItemList for the V18 startup fix.")
new_home_method = """    fun getHomeItemList(params: String? = null) {
        loading.value = true
        _homeListState.value = ListState.LOADING
        language =
            runBlocking {
                dataStoreManager.getString(SELECTED_LANGUAGE).first()
                    ?: SUPPORTED_LANGUAGE.codes.first()
            }
        regionCode = runBlocking { dataStoreManager.location.first() }
        homeJob?.cancel()
        homeJob =
            viewModelScope.launch {
                regionCodeChart.value = dataStoreManager.chartKey.first()

                // The home feed is the critical path. Do not make its first render wait for
                // recommendations, charts or new releases, which are independent requests.
                launch {
                    homeRepository.getHomeData(
                        params,
                        getString(Res.string.view_count),
                        getString(Res.string.song),
                    ).collect { home ->
                        when (home) {
                            is Resource.Success -> {
                                _continuation.value = home.data?.first
                                _homeItemList.value = home.data?.second ?: emptyList()
                                _homeBackground.value = home.data?.third
                                _homeListState.value =
                                    if (_continuation.value.isNullOrEmpty()) {
                                        ListState.PAGINATION_EXHAUST
                                    } else {
                                        ListState.IDLE
                                    }
                                loading.value = false
                                if (dataStoreManager.cookie.first().isNotBlank()) {
                                    _accountInfo.emit(
                                        Pair(
                                            dataStoreManager.getString("AccountName").first(),
                                            dataStoreManager.getString("AccountThumbUrl").first(),
                                        ),
                                    )
                                }
                            }

                            is Resource.Error -> {
                                _continuation.value = null
                                _homeItemList.value = emptyList()
                                _homeBackground.value = null
                                _homeListState.value = ListState.PAGINATION_EXHAUST
                                loading.value = false
                                showSnackBarErrorState.emit(home.message)
                                Logger.w("HomeViewModel", "getHomeItemList: ${home.message}")
                            }

                            else -> Unit
                        }
                    }
                }

                launch {
                    homeRepository.getMoodAndMomentsData().collect { mood ->
                        when (mood) {
                            is Resource.Success -> _exploreMoodItem.value = mood.data
                            is Resource.Error -> {
                                _exploreMoodItem.value = null
                                showSnackBarErrorState.emit(mood.message)
                            }
                            else -> Unit
                        }
                    }
                }

                launch {
                    homeRepository.getChartData(dataStoreManager.chartKey.first()).collect { chart ->
                        when (chart) {
                            is Resource.Success -> _chart.value = chart.data
                            is Resource.Error -> {
                                _chart.value = null
                                showSnackBarErrorState.emit(chart.message)
                            }
                            else -> Unit
                        }
                    }
                }

                launch {
                    homeRepository.getNewRelease(
                        getString(Res.string.new_release),
                        getString(Res.string.music_video),
                    ).collect { newRelease ->
                        when (newRelease) {
                            is Resource.Success -> _newRelease.value = newRelease.data ?: emptyList()
                            is Resource.Error -> _newRelease.value = emptyList()
                            else -> Unit
                        }
                    }
                }
            }
    }

"""
home_source = home_source[:home_start] + new_home_method + home_source[home_end:]
(ROOT / home_path).write_text(home_source)

# V18 refinement: prefer YouTube's native shuffle endpoint, even when the parser omitted it.
# Keep the complete-playlist shuffle as a fallback when that endpoint cannot return tracks.
playlist_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/PlaylistViewModel.kt"
playlist_source = (ROOT / playlist_path).read_text()
if "import com.maxrave.domain.data.model.streams.YouTubeWatchEndpoint\n" not in playlist_source:
    playlist_source = replace_once(
        playlist_source,
        "import com.maxrave.domain.data.model.browse.playlist.PlaylistState\n",
        "import com.maxrave.domain.data.model.browse.playlist.PlaylistState\nimport com.maxrave.domain.data.model.streams.YouTubeWatchEndpoint\n",
        "V18 synthetic shuffle endpoint import",
    )

shuffle_start = re.search(
    r"(?ms)^            PlaylistUIEvent\.Shuffle -> \{.*?(?=^            PlaylistUIEvent\.StartRadio -> \{)",
    playlist_source,
)
if not shuffle_start:
    raise SystemExit("Could not isolate PlaylistUIEvent.Shuffle for the V18 endpoint-first fix.")

new_shuffle_branch = """            PlaylistUIEvent.Shuffle -> {
                val playlistId = data.id.removePrefix("VL")
                val shuffleEndpoint =
                    data.shuffleEndpoint
                        ?: YouTubeWatchEndpoint(
                            playlistId = playlistId,
                            params = if (playlistId.startsWith("RD")) RADIO_SHUFFLE_PARAMS else SHUFFLE_PARAMS,
                        )

                viewModelScope.launch {
                    // The official 2.7 path is fast because YouTube returns a shuffled queue.
                    // Try that first; only enumerate every page if the endpoint is unavailable.
                    val endpointResult =
                        songRepository
                            .getRadioFromEndpoint(shuffleEndpoint)
                            .firstOrNull { it !is Resource.Loading }
                    val endpointData = (endpointResult as? Resource.Success)?.data
                    val endpointTracks = endpointData?.first.orEmpty()
                    val endpointFirst = endpointTracks.firstOrNull()

                    if (endpointFirst != null) {
                        setQueueData(
                            QueueData.Data(
                                listTracks = endpointTracks.toCollection(arrayListOf<Track>()),
                                firstPlayedTrack = endpointFirst,
                                playlistId = shuffleEndpoint.playlistId,
                                playlistName = "\\"${data.title}\\" ${getString(Res.string.shuffle)}",
                                playlistType = PlaylistType.RADIO,
                                continuation = endpointData?.second,
                            ),
                        )
                        loadMediaItem(endpointFirst, Config.RADIO_CLICK, 0)
                        Logger.d(tag, "Native shuffle endpoint successful: ${endpointTracks.size} tracks")
                        return@launch
                    }

                    try {
                        val allTracks = tracks.value.toMutableList()
                        val visitedContinuations = mutableSetOf<String>()
                        var nextContinuation = continuation.value

                        while (!nextContinuation.isNullOrEmpty()) {
                            if (!visitedContinuations.add(nextContinuation)) {
                                throw IllegalStateException("Repeated playlist continuation token")
                            }

                            val page =
                                songRepository
                                    .getContinueTrack(
                                        data.id,
                                        nextContinuation,
                                        fromPlaylist = true,
                                    ).firstOrNull()
                                    ?: throw IllegalStateException("Unable to load the next playlist page")

                            val pageTracks =
                                page.first
                                    ?: throw IllegalStateException("Playlist page returned no track data")

                            allTracks.addAll(pageTracks)
                            nextContinuation = page.second
                        }

                        if (allTracks.isEmpty()) {
                            makeToast(getString(Res.string.playlist_is_empty))
                            return@launch
                        }

                        _tracks.value = allTracks
                        _continuation.value = null
                        _tracksListState.value = ListState.PAGINATION_EXHAUST

                        val shuffledTracks = allTracks.shuffled()
                        val firstTrack = shuffledTracks.first()
                        setQueueData(
                            QueueData.Data(
                                listTracks = shuffledTracks.toCollection(arrayListOf<Track>()),
                                firstPlayedTrack = firstTrack,
                                playlistId = data.id,
                                playlistName = "\\"${data.title}\\" ${getString(Res.string.shuffle)}",
                                playlistType = PlaylistType.PLAYLIST,
                                continuation = null,
                            ),
                        )
                        loadMediaItem(firstTrack, Config.PLAYLIST_CLICK, 0)
                        Logger.d(tag, "Full playlist shuffle fallback successful: ${shuffledTracks.size} tracks")
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        Logger.w(tag, "Full playlist shuffle fallback failed: ${e.message}")
                        makeToast("Couldn't load the complete playlist. Please try again.")
                    }
                }
            }

"""
playlist_source = playlist_source[:shuffle_start.start()] + new_shuffle_branch + playlist_source[shuffle_start.end():]
if "private const val SHUFFLE_PARAMS = " not in playlist_source:
    playlist_source += """
// The params YouTube puts on a Shuffle button for normal playlists and radio mixes.
private const val SHUFFLE_PARAMS = "wAEB8gECKAE%3D"
private const val RADIO_SHUFFLE_PARAMS = "wAEB8gECGAE%3D"
"""
(ROOT / playlist_path).write_text(playlist_source)

# Fail the build early if any of the V18 refinements were omitted.
if "icons = options.map { it.third }" not in settings:
    raise SystemExit("App icon preview thumbnails are not connected.")
if "homeRepository.getHomeData(" not in home_source or "homeRepository.getMoodAndMomentsData()" not in home_source:
    raise SystemExit("Independent home feed loading is incomplete.")
if "YouTubeWatchEndpoint(" not in playlist_source or "Full playlist shuffle fallback successful" not in playlist_source:
    raise SystemExit("Endpoint-first shuffle or the complete-playlist fallback is missing.")
print("V18 refinements applied: native-first shuffle, independent home loading, official Insights UI and icon previews.")


# V18 custom Insights periods: month, year, all-time and a selectable date range.
analytics_vm_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/AnalyticsViewModel.kt"
analytics_vm = (ROOT / analytics_vm_path).read_text()

range_pattern = re.compile(r"(?ms)^    private fun rangeFor\(.*?(?=^    private fun loadPeriod\(\))")
new_range_for = """    private fun rangeFor(
        dayRange: AnalyticsUiState.DayRange,
        offset: Int,
    ): Pair<LocalDateTime, LocalDateTime> {
        val today = now().date
        val state = _analyticsUIState.value
        return when (dayRange) {
            AnalyticsUiState.DayRange.THIS_YEAR -> {
                val year = today.year - offset
                val start = LocalDate(year, 1, 1)
                val end = if (offset == 0) today else LocalDate(year, 12, 31)
                start.atTime(0, 0) to end.atTime(23, 59, 59)
            }

            AnalyticsUiState.DayRange.THIS_MONTH -> {
                val monthStart = LocalDate(today.year, today.month.number, 1)
                    .minus(DatePeriod(months = offset))
                val monthEnd =
                    if (offset == 0) today
                    else monthStart.plus(DatePeriod(months = 1)).minus(DatePeriod(days = 1))
                monthStart.atTime(0, 0) to monthEnd.atTime(23, 59, 59)
            }

            AnalyticsUiState.DayRange.ALL_TIME ->
                LocalDate(2026, 11, 1).atTime(0, 0) to today.atTime(23, 59, 59)

            AnalyticsUiState.DayRange.CUSTOM_RANGE -> {
                val start = state.customStartDate ?: LocalDate(2026, 11, 1)
                val end = state.customEndDate ?: today
                start.atTime(0, 0) to end.atTime(23, 59, 59)
            }

            else -> {
                val length = dayRange.lengthInDays
                val end = today.minus(DatePeriod(days = offset * length))
                val start = end.minus(DatePeriod(days = length - 1))
                start.atTime(0, 0) to end.atTime(23, 59, 59)
            }
        }
    }

"""
if not range_pattern.search(analytics_vm):
    raise SystemExit("Could not isolate AnalyticsViewModel.rangeFor for custom periods.")
analytics_vm, n = range_pattern.subn(new_range_for, analytics_vm, count=1)
if n != 1:
    raise SystemExit("AnalyticsViewModel.rangeFor replacement was not unique.")

analytics_vm = replace_once(
    analytics_vm,
    "        getScrobblesLineChart(state.dayRange, end.date)\n",
    "        getScrobblesLineChart(state.dayRange, start.date, end.date)\n",
    "V18 chart date-span wiring",
)

stats_pattern = re.compile(r"(?ms)^    private fun getPeriodStats\(.*?(?=^    /\*\*)")
new_stats = """    private fun getPeriodStats(
        dayRange: AnalyticsUiState.DayRange,
        offset: Int,
    ) {
        viewModelScope.launch {
            _analyticsUIState.update { it.copy(stats = LocalResource.Loading()) }
            val (start, end) = rangeFor(dayRange, offset)
            val current = analyticsRepository.getPeriodStats(start, end)
            if (dayRange == AnalyticsUiState.DayRange.ALL_TIME ||
                dayRange == AnalyticsUiState.DayRange.CUSTOM_RANGE
            ) {
                _analyticsUIState.update {
                    it.copy(stats = LocalResource.Success(current), previousStats = null)
                }
            } else {
                val (prevStart, prevEnd) = rangeFor(dayRange, offset + 1)
                val previous = analyticsRepository.getPeriodStats(prevStart, prevEnd)
                _analyticsUIState.update {
                    it.copy(
                        stats = LocalResource.Success(current),
                        previousStats = previous.takeIf { p -> !p.isEmpty },
                    )
                }
            }
        }
    }

"""
if not stats_pattern.search(analytics_vm):
    raise SystemExit("Could not isolate AnalyticsViewModel.getPeriodStats.")
analytics_vm, n = stats_pattern.subn(new_stats, analytics_vm, count=1)
if n != 1:
    raise SystemExit("AnalyticsViewModel.getPeriodStats replacement was not unique.")

analytics_vm = replace_once(
    analytics_vm,
    "    fun stepPeriod(delta: Int) {\n        val next = (_analyticsUIState.value.periodOffset - delta).coerceAtLeast(0)\n",
    "    fun stepPeriod(delta: Int) {\n        if (_analyticsUIState.value.dayRange in setOf(AnalyticsUiState.DayRange.ALL_TIME, AnalyticsUiState.DayRange.CUSTOM_RANGE)) return\n        val next = (_analyticsUIState.value.periodOffset - delta).coerceAtLeast(0)\n",
    "V18 fixed-range period navigation",
)

chart_pattern = re.compile(r"(?ms)^    private fun getScrobblesLineChart\(.*?(?=^    fun setDayRange\()")
new_chart = """    private fun getScrobblesLineChart(
        dayRange: AnalyticsUiState.DayRange,
        startDate: LocalDate,
        endDate: LocalDate,
    ) {
        viewModelScope.launch {
            _analyticsUIState.update { it.copy(scrobblesLineChart = LocalResource.Loading()) }
            val chartTypes = mutableListOf<AnalyticsUiState.ChartType>()

            when (dayRange) {
                AnalyticsUiState.DayRange.LAST_7_DAYS -> {
                    for (offset in 0 until 7) {
                        chartTypes += AnalyticsUiState.ChartType.Day(endDate.minus(DatePeriod(days = offset)))
                    }
                }

                AnalyticsUiState.DayRange.LAST_30_DAYS -> {
                    for (week in 0 until 5) {
                        val end = endDate.minus(DatePeriod(days = week * 7))
                        val start = maxOf(startDate, end.minus(DatePeriod(days = 6)))
                        if (start <= endDate && start <= end) chartTypes += AnalyticsUiState.ChartType.Week(start, end)
                    }
                }

                AnalyticsUiState.DayRange.LAST_90_DAYS,
                AnalyticsUiState.DayRange.THIS_YEAR,
                AnalyticsUiState.DayRange.ALL_TIME -> {
                    var month = LocalDate(startDate.year, startDate.month.number, 1)
                    while (month <= endDate) {
                        chartTypes += AnalyticsUiState.ChartType.Month(month.month, month.year)
                        month = month.plus(DatePeriod(months = 1))
                    }
                }

                AnalyticsUiState.DayRange.THIS_MONTH,
                AnalyticsUiState.DayRange.CUSTOM_RANGE -> {
                    val dayCount = (0..60).count { offset ->
                        startDate.plus(DatePeriod(days = offset)) <= endDate
                    }
                    if (dayCount <= 14) {
                        var day = startDate
                        while (day <= endDate) {
                            chartTypes += AnalyticsUiState.ChartType.Day(day)
                            day = day.plus(DatePeriod(days = 1))
                        }
                    } else if (dayCount <= 60) {
                        var weekStart = startDate
                        while (weekStart <= endDate) {
                            val weekEnd = minOf(endDate, weekStart.plus(DatePeriod(days = 6)))
                            chartTypes += AnalyticsUiState.ChartType.Week(weekStart, weekEnd)
                            weekStart = weekEnd.plus(DatePeriod(days = 1))
                        }
                    } else {
                        var month = LocalDate(startDate.year, startDate.month.number, 1)
                        while (month <= endDate) {
                            chartTypes += AnalyticsUiState.ChartType.Month(month.month, month.year)
                            month = month.plus(DatePeriod(months = 1))
                        }
                    }
                }
            }

            val currentTimeZone = TimeZone.currentSystemDefault()
            val data =
                chartTypes.map { bucket ->
                    val bucketStart: LocalDate
                    val bucketEnd: LocalDate
                    when (bucket) {
                        is AnalyticsUiState.ChartType.Day -> {
                            bucketStart = bucket.day
                            bucketEnd = bucket.day
                        }
                        is AnalyticsUiState.ChartType.Week -> {
                            bucketStart = bucket.start
                            bucketEnd = bucket.end
                        }
                        is AnalyticsUiState.ChartType.Month -> {
                            val firstOfMonth = LocalDate(bucket.year, bucket.month.number, 1)
                            val nextMonth = firstOfMonth.plus(DatePeriod(months = 1))
                            bucketStart = maxOf(startDate, firstOfMonth)
                            bucketEnd = minOf(endDate, nextMonth.minus(DatePeriod(days = 1)))
                        }
                    }
                    val startTimestamp =
                        bucketStart.atStartOfDayIn(currentTimeZone).toLocalDateTime(currentTimeZone)
                    val endTimestamp =
                        bucketEnd.plus(DatePeriod(days = 1))
                            .atStartOfDayIn(currentTimeZone)
                            .toLocalDateTime(currentTimeZone)
                    val count =
                        analyticsRepository.getPlaybackEventCountInRange(
                            startTimestamp = startTimestamp,
                            endTimestamp = endTimestamp,
                        ).lastOrNull() ?: 0L
                    bucket to count
                }

            _analyticsUIState.update {
                it.copy(scrobblesLineChart = LocalResource.Success(data))
            }
        }
    }

"""
if not chart_pattern.search(analytics_vm):
    raise SystemExit("Could not isolate AnalyticsViewModel.getScrobblesLineChart.")
analytics_vm, n = chart_pattern.subn(new_chart, analytics_vm, count=1)
if n != 1:
    raise SystemExit("AnalyticsViewModel.getScrobblesLineChart replacement was not unique.")

custom_method = """    fun setCustomRange(
        start: LocalDate,
        end: LocalDate,
    ) {
        val first = minOf(start, end)
        val last = maxOf(start, end)
        _analyticsUIState.update {
            it.copy(
                dayRange = AnalyticsUiState.DayRange.CUSTOM_RANGE,
                periodOffset = 0,
                customStartDate = first,
                customEndDate = last,
            )
        }
        loadPeriod()
    }

"""
analytics_vm = replace_once(
    analytics_vm,
    "    fun setDayRange(dayRange: AnalyticsUiState.DayRange) {\n",
    custom_method + "    fun setDayRange(dayRange: AnalyticsUiState.DayRange) {\n",
    "V18 custom date-range setter",
)
analytics_vm = replace_once(
    analytics_vm,
    "    val periodEnd: LocalDate? = null,\n",
    "    val periodEnd: LocalDate? = null,\n    val customStartDate: LocalDate? = null,\n    val customEndDate: LocalDate? = null,\n",
    "V18 custom date-range state",
)
analytics_vm = replace_once(
    analytics_vm,
    "        LAST_90_DAYS(90),\n\n        /** Length is unused — a year steps by calendar years, see rangeFor. */\n        THIS_YEAR(365),\n",
    "        LAST_90_DAYS(90),\n        THIS_MONTH(31),\n\n        /** Length is unused — calendar periods are resolved in rangeFor. */\n        THIS_YEAR(365),\n        ALL_TIME(0),\n        CUSTOM_RANGE(0),\n",
    "V18 Analytics range options",
)
(ROOT / analytics_vm_path).write_text(analytics_vm)

# Extend the official 2.7 range pill with month/all-time choices and a native date-range picker.
analytics_screen_path = "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/ui/screen/home/analytics/AnalyticsScreen.kt"
analytics_screen = (ROOT / analytics_screen_path).read_text()
for imp in (
    "import androidx.compose.material3.DatePickerDialog\n",
    "import androidx.compose.material3.DateRangePicker\n",
    "import androidx.compose.material3.TextButton\n",
    "import androidx.compose.material3.rememberDateRangePickerState\n",
    "import kotlinx.datetime.Instant\n",
    "import kotlinx.datetime.LocalDate\n",
    "import kotlinx.datetime.TimeZone\n",
    "import kotlinx.datetime.toLocalDateTime\n",
    "import simpmusic.composeapp.generated.resources.this_month\n",
    "import simpmusic.composeapp.generated.resources.all_time\n",
    "import simpmusic.composeapp.generated.resources.custom_range\n",
):
    if imp not in analytics_screen:
        analytics_screen = replace_once(
            analytics_screen,
            "import androidx.compose.material3.DropdownMenuItem\n",
            "import androidx.compose.material3.DropdownMenuItem\n" + imp if imp.startswith("import androidx.compose.material3") else "import androidx.compose.material3.DropdownMenuItem\n",
            "V18 Analytics imports",
        ) if imp.startswith("import androidx.compose.material3") else analytics_screen
        if not imp.startswith("import androidx.compose.material3"):
            analytics_screen = replace_once(
                analytics_screen,
                "import kotlinx.coroutines.flow.map\n",
                "import kotlinx.coroutines.flow.map\n" + imp,
                "V18 Analytics date imports",
            ) if imp.startswith("import kotlinx.datetime") else replace_once(
                analytics_screen,
                "import simpmusic.composeapp.generated.resources.this_year\n",
                "import simpmusic.composeapp.generated.resources.this_year\n" + imp,
                "V18 Analytics range resources",
            )

analytics_screen = replace_once(
    analytics_screen,
    "                onPick = { analyticsViewModel.setDayRange(it) },\n",
    "                onPick = { analyticsViewModel.setDayRange(it) },\n                onCustomRange = { start, end -> analyticsViewModel.setCustomRange(start, end) },\n",
    "V18 custom range callback",
)
pill_pattern = re.compile(r"(?ms)^@Composable\nprivate fun DayRangePill\(.*?(?=^// ========== Header ==========)")
new_pill = """@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DayRangePill(
    uiState: AnalyticsUiState,
    backdrop: PlatformBackdrop,
    onPick: (AnalyticsUiState.DayRange) -> Unit,
    onCustomRange: (LocalDate, LocalDate) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    var showCustomRange by rememberSaveable { mutableStateOf(false) }
    val pickerState = rememberDateRangePickerState()
    val label =
        stringResource(
            when (uiState.dayRange) {
                AnalyticsUiState.DayRange.LAST_7_DAYS -> Res.string.last_7_days
                AnalyticsUiState.DayRange.LAST_30_DAYS -> Res.string.last_30_days
                AnalyticsUiState.DayRange.LAST_90_DAYS -> Res.string.last_90_days
                AnalyticsUiState.DayRange.THIS_MONTH -> Res.string.this_month
                AnalyticsUiState.DayRange.THIS_YEAR -> Res.string.this_year
                AnalyticsUiState.DayRange.ALL_TIME -> Res.string.all_time
                AnalyticsUiState.DayRange.CUSTOM_RANGE -> Res.string.custom_range
            },
        )
    Box(modifier) {
        Row(
            modifier =
                Modifier
                    .height(48.dp)
                    .liquidGlass(backdrop, RoundedCornerShape(24.dp), highlight = Highlight(width = 1.dp))
                    .clip(RoundedCornerShape(24.dp))
                    .clickable { expanded = true }
                    .padding(horizontal = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(text = label, style = typo().labelSmall, color = Color.White, maxLines = 1)
            Icon(
                imageVector = SimpIcons.KeyboardArrowDown,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(18.dp),
            )
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            AnalyticsUiState.DayRange.entries.forEach { range ->
                DropdownMenuItem(
                    text = {
                        Text(
                            stringResource(
                                when (range) {
                                    AnalyticsUiState.DayRange.LAST_7_DAYS -> Res.string.last_7_days
                                    AnalyticsUiState.DayRange.LAST_30_DAYS -> Res.string.last_30_days
                                    AnalyticsUiState.DayRange.LAST_90_DAYS -> Res.string.last_90_days
                                    AnalyticsUiState.DayRange.THIS_MONTH -> Res.string.this_month
                                    AnalyticsUiState.DayRange.THIS_YEAR -> Res.string.this_year
                                    AnalyticsUiState.DayRange.ALL_TIME -> Res.string.all_time
                                    AnalyticsUiState.DayRange.CUSTOM_RANGE -> Res.string.custom_range
                                },
                            ),
                            style = typo().labelSmall,
                        )
                    },
                    onClick = {
                        expanded = false
                        if (range == AnalyticsUiState.DayRange.CUSTOM_RANGE) {
                            showCustomRange = true
                        } else {
                            onPick(range)
                        }
                    },
                )
            }
        }
    }

    if (showCustomRange) {
        DatePickerDialog(
            onDismissRequest = { showCustomRange = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        val startMillis = pickerState.selectedStartDateMillis
                        val endMillis = pickerState.selectedEndDateMillis
                        if (startMillis != null && endMillis != null) {
                            val start = Instant.fromEpochMilliseconds(startMillis).toLocalDateTime(TimeZone.UTC).date
                            val end = Instant.fromEpochMilliseconds(endMillis).toLocalDateTime(TimeZone.UTC).date
                            onCustomRange(start, end)
                            showCustomRange = false
                        }
                    },
                ) { Text("Apply") }
            },
            dismissButton = {
                TextButton(onClick = { showCustomRange = false }) { Text("Cancel") }
            },
        ) {
            DateRangePicker(state = pickerState, modifier = Modifier.height(500.dp))
        }
    }
}

"""
if not pill_pattern.search(analytics_screen):
    raise SystemExit("Could not isolate official AnalyticsScreen.DayRangePill.")
analytics_screen, n = pill_pattern.subn(new_pill + "// ========== Header ==========", analytics_screen, count=1)
if n != 1:
    raise SystemExit("Official Insights range picker replacement was not unique.")
(ROOT / analytics_screen_path).write_text(analytics_screen)

# Add localized labels without replacing any existing resource entries.
strings_path = "composeApp/src/commonMain/composeResources/values/strings.xml"
strings = (ROOT / strings_path).read_text()
new_strings = {
    "this_month": "This month",
    "all_time": "All time",
    "custom_range": "Custom range",
}
additions = []
for key, value in new_strings.items():
    if not re.search(r'<string\s+name="' + re.escape(key) + r'"(?:\s|>)', strings):
        additions.append(f'    <string name="{key}">{value}</string>')
if additions:
    strings = replace_once(strings, "</resources>", "\n".join(additions) + "\n</resources>", "V18 Insights period labels")
    (ROOT / strings_path).write_text(strings)

# Validate every new enum value is handled by both the view model and the official range picker.
for marker in ("THIS_MONTH", "ALL_TIME", "CUSTOM_RANGE", "fun setCustomRange("):
    if marker not in analytics_vm:
        raise SystemExit(f"V18 AnalyticsViewModel filter is missing: {marker}")
for marker in ("DayRange.THIS_MONTH", "DayRange.ALL_TIME", "DayRange.CUSTOM_RANGE", "onCustomRange"):
    if marker not in analytics_screen:
        raise SystemExit(f"V18 official Insights UI filter is missing: {marker}")
print("V18 custom Insights filters applied: this month, this year, all-time and custom date range.")
