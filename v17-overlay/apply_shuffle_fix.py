#!/usr/bin/env python3
"""Apply only the V17 full-playlist shuffle fallback to the official 2.7 PlaylistViewModel."""
from pathlib import Path

path = Path("composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/viewModel/PlaylistViewModel.kt")
if not path.is_file():
    raise SystemExit(f"Missing shuffle target: {path}")

source = path.read_text()
if "V17 full-playlist fallback: load every continuation page" in source:
    raise SystemExit("The V17 full-playlist fallback is already present; refusing a duplicate insertion.")

import_anchor = "import kotlinx.coroutines.Dispatchers\n"
if source.count(import_anchor) != 1:
    raise SystemExit("Could not uniquely locate the coroutine imports.")
if "import kotlinx.coroutines.CancellationException\n" not in source:
    source = source.replace(import_anchor, "import kotlinx.coroutines.CancellationException\n" + import_anchor, 1)

event_anchor = "            PlaylistUIEvent.Shuffle -> {\n"
shuffle_anchor = '                val playlistId = data.id.removePrefix("VL")\n'
if source.count(event_anchor) != 1 or source.count(shuffle_anchor) != 1:
    raise SystemExit("The official 2.7 shuffle block has changed; refusing an unsafe insertion.")

fallback = """                // V17 full-playlist fallback: load every continuation page before shuffling.
                // Keep the official 2.7 endpoint path below unchanged whenever an endpoint exists.
                if (data.shuffleEndpoint == null) {
                    viewModelScope.launch {
                        try {
                            val allTracks = tracks.value.toMutableList()
                            val visitedContinuations = mutableSetOf<String>()
                            var nextContinuation = continuation.value

                            while (!nextContinuation.isNullOrEmpty()) {
                                if (!visitedContinuations.add(nextContinuation)) {
                                    throw IllegalStateException("Repeated playlist continuation token")
                                }

                                val page = songRepository
                                    .getContinueTrack(
                                        data.id,
                                        nextContinuation,
                                        fromPlaylist = true,
                                    )
                                    .firstOrNull()
                                    ?: throw IllegalStateException("Unable to load the next playlist page")

                                val pageTracks = page.first
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
                                    playlistName = "\\"\u0024{data.title}\\" \u0024{getString(Res.string.shuffle)}",
                                    playlistType = PlaylistType.PLAYLIST,
                                    continuation = null,
                                ),
                            )
                            loadMediaItem(firstTrack, Config.PLAYLIST_CLICK, 0)
                            Logger.d(tag, "Full playlist shuffle successful: \u0024{shuffledTracks.size} tracks")
                        } catch (e: CancellationException) {
                            throw e
                        } catch (e: Exception) {
                            Logger.w(tag, "Full playlist shuffle failed: \u0024{e.message}")
                            makeToast("Couldn't load the complete playlist. Please try again.")
                        }
                    }
                    return
                }

"""
source = source.replace(shuffle_anchor, fallback + shuffle_anchor, 1)
path.write_text(source)
print("Applied the V17 shuffle fallback without replacing official 2.7 PlaylistViewModel code.")
