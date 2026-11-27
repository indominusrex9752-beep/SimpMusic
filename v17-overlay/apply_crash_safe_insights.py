#!/usr/bin/env python3
"""Apply the V17 crash-safe Insights checkpoint layer after the 2.7.0/Insights merge."""
from pathlib import Path
import re

ROOT = Path(".")
def edit(path, transform):
    file = ROOT / path
    if not file.is_file():
        raise SystemExit(f"Missing checkpoint target: {path}")
    source = file.read_text()
    updated = transform(source)
    if updated == source:
        raise SystemExit(f"No change made to {path}; source shape was not the expected version.")
    file.write_text(updated)

def replace_once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, found {count}.")
    return source.replace(old, new, 1)

def accumulator(source):
    source = replace_once(source,
        "import com.maxrave.domain.data.entities.SongEntity\nimport kotlin.time.TimeSource",
        "import com.maxrave.data.librarysync.newSyncId\nimport com.maxrave.domain.data.entities.SongEntity\nimport com.maxrave.domain.extension.now\nimport kotlinx.serialization.Serializable\nimport kotlin.time.TimeSource",
        "accumulator imports")
    source = replace_once(source,
        "/** A single continuous listening session. Pauses and track changes close the session. */\ninternal data class CompletedListeningSession(\n    val song: SongEntity,\n    val listenedMillis: Long,\n)",
        """/**
 * Durable, minimal representation of an unfinished session. It excludes the full SongEntity:
 * only fields required to write one Analytics event are persisted.
 */
@Serializable
internal data class ListeningSessionCheckpoint(
    val syncId: String,
    val videoId: String,
    val channelIds: List<String>,
    val albumBrowseId: String?,
    val durationSecond: Long,
    val listenedMillis: Long,
    val startedAt: String,
)

/** A single continuous listening session. Pauses and track changes close the session. */
internal data class CompletedListeningSession(
    val song: SongEntity,
    val listenedMillis: Long,
    val syncId: String,
    val startedAt: String,
)""",
        "accumulator session models")
    source = replace_once(source,
        "    private var lastPositionMillis: Long = 0L\n    private var lastTick = TimeSource.Monotonic.markNow()",
        "    private var lastPositionMillis: Long = 0L\n    private var sessionSyncId: String? = null\n    private var startedAt: String? = null\n    private var lastCheckpointMillis: Long = 0L\n    private var lastTick = TimeSource.Monotonic.markNow()",
        "accumulator state")
    source = replace_once(source,
        """        if (song?.videoId != currentSong.videoId) {
            song = currentSong
            listenedMillis = 0L
        } else {
            // Keep accumulated time across a buffering interruption, but never count the stalled interval.
            song = currentSong
        }
        lastPositionMillis = positionMillis""",
        """        if (song?.videoId != currentSong.videoId) {
            song = currentSong
            listenedMillis = 0L
            sessionSyncId = newSyncId()
            startedAt = now().toString()
            lastCheckpointMillis = 0L
        } else {
            // Keep accumulated time and the same event identity across a buffering interruption.
            song = currentSong
            if (sessionSyncId == null) {
                sessionSyncId = newSyncId()
                startedAt = now().toString()
            }
        }
        lastPositionMillis = positionMillis""",
        "accumulator resume")
    source = replace_once(source,
        "    fun pause(positionMillis: Long) {",
        """    /**
     * Returns a checkpoint at most every two seconds, plus immediately when the 30-second
     * complete-play threshold is crossed.
     */
    fun checkpoint(force: Boolean = false): ListeningSessionCheckpoint? {
        val currentSong = song ?: return null
        val id = sessionSyncId ?: return null
        val start = startedAt ?: return null
        if (listenedMillis <= 0L) return null
        val thresholdCrossed = lastCheckpointMillis < 30_000L && listenedMillis >= 30_000L
        if (!force && !thresholdCrossed && listenedMillis - lastCheckpointMillis < 2_000L) return null
        lastCheckpointMillis = listenedMillis
        return ListeningSessionCheckpoint(
            syncId = id,
            videoId = currentSong.videoId,
            channelIds = currentSong.artistId.orEmpty().distinct(),
            albumBrowseId = currentSong.albumId,
            durationSecond = currentSong.durationSeconds.toLong(),
            listenedMillis = listenedMillis,
            startedAt = start,
        )
    }

    fun pause(positionMillis: Long) {""",
        "accumulator checkpoint method")
    source = replace_once(source,
        """        val currentSong = song
        val duration = listenedMillis
        song = null
        listenedMillis = 0L
        lastPositionMillis = 0L
        lastTick = TimeSource.Monotonic.markNow()
        return if (currentSong != null && duration > 0L) {
            CompletedListeningSession(currentSong, duration)
        } else {
            null
        }""",
        """        val currentSong = song
        val duration = listenedMillis
        val id = sessionSyncId
        val start = startedAt
        song = null
        listenedMillis = 0L
        lastPositionMillis = 0L
        sessionSyncId = null
        startedAt = null
        lastCheckpointMillis = 0L
        lastTick = TimeSource.Monotonic.markNow()
        return if (currentSong != null && id != null && start != null) {
            CompletedListeningSession(currentSong, duration, id, start)
        } else {
            null
        }""",
        "accumulator finish")
    return source

edit("core/data/src/commonMain/kotlin/com/maxrave/data/mediaservice/PlaybackListeningAccumulator.kt", accumulator)

def analytics_interface(source):
    return replace_once(source,
        """        durationSecond: Long,
        listenedSecond: Long,
    ): Flow<Long>""",
        """        durationSecond: Long,
        listenedSecond: Long,
        syncId: String? = null,
        timestamp: LocalDateTime? = null,
    ): Flow<Long>""",
        "AnalyticsRepository.insertPlaybackEvent signature")
edit("core/domain/src/commonMain/kotlin/com/maxrave/domain/repository/AnalyticsRepository.kt", analytics_interface)

def analytics_impl(source):
    return replace_once(source,
        """        durationSecond: Long,
        listenedSecond: Long,
    ): Flow<Long> =
        flow {
            emit(
                analyticsDatasource.insertPlaybackEvent(
                    videoId,
                    channelIds,
                    albumBrowseId,
                    durationSecond,
                    listenedSecond,
                ),""",
        """        durationSecond: Long,
        listenedSecond: Long,
        syncId: String?,
        timestamp: LocalDateTime?,
    ): Flow<Long> =
        flow {
            emit(
                analyticsDatasource.insertPlaybackEvent(
                    videoId,
                    channelIds,
                    albumBrowseId,
                    durationSecond,
                    listenedSecond,
                    syncId,
                    timestamp,
                ),""",
        "AnalyticsRepositoryImpl.insertPlaybackEvent")
edit("core/data/src/commonMain/kotlin/com/maxrave/data/repository/AnalyticsRepositoryImpl.kt", analytics_impl)

def analytics_datasource(source):
    return replace_once(source,
        """        durationSecond: Long,
        listenedSecond: Long,
    ): Long {
        val syncId = newSyncId()
        val eventId =
            databaseDao.insertPlaybackWithArtists(
                videoId = videoId,
                channelIds = channelIds,
                albumBrowseId = albumBrowseId,
                durationSecond = durationSecond,
                listenedSecond = listenedSecond,
                syncId = syncId,
            )
        syncRecorder.play(syncId)""",
        """        durationSecond: Long,
        listenedSecond: Long,
        syncId: String? = null,
        timestamp: LocalDateTime? = null,
    ): Long {
        val stableSyncId = syncId ?: newSyncId()
        val eventId =
            databaseDao.insertPlaybackWithArtists(
                videoId = videoId,
                channelIds = channelIds,
                albumBrowseId = albumBrowseId,
                durationSecond = durationSecond,
                listenedSecond = listenedSecond,
                syncId = stableSyncId,
                timestamp = timestamp ?: now(),
            )
        syncRecorder.play(stableSyncId)""",
        "AnalyticsDatasource.insertPlaybackEvent")
edit("core/data/src/commonMain/kotlin/com/maxrave/data/db/datasource/AnalyticsDatasource.kt", analytics_datasource)

def dao(source):
    source = replace_once(source,
        """    @Insert
    suspend fun insertEventArtist(eventArtist: EventArtistEntity)

    @Transaction
    suspend fun insertPlaybackWithArtists(""",
        """    @Insert
    suspend fun insertEventArtist(eventArtist: EventArtistEntity)

    @Query("SELECT * FROM playback_event WHERE syncId = :syncId LIMIT 1")
    suspend fun getPlaybackEventBySyncId(syncId: String): PlaybackEventEntity?

    @Update
    suspend fun updatePlaybackEvent(event: PlaybackEventEntity)

    @Transaction
    suspend fun insertPlaybackWithArtists(""",
        "DatabaseDao playback upsert declarations")
    pattern = re.compile(r"""    @Transaction
    suspend fun insertPlaybackWithArtists\(
.*?^        return eventId
    \}""", re.MULTILINE | re.DOTALL)
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise SystemExit(f"DatabaseDao playback transaction: expected one method, found {len(matches)}.")
    method = """    @Transaction
    suspend fun insertPlaybackWithArtists(
        videoId: String,
        channelIds: List<String>,
        albumBrowseId: String?,
        durationSecond: Long,
        listenedSecond: Long,
        syncId: String? = null,
        timestamp: LocalDateTime = now(),
    ): Long {
        // Recovery can run again if the process dies after the DB commit but before the
        // checkpoint is cleared. Reuse the same row instead of creating a second play.
        val existing = syncId?.let { getPlaybackEventBySyncId(it) }
        if (existing != null) {
            updatePlaybackEvent(existing.copy(listenedSecond = listenedSecond))
            return existing.eventId
        }

        val eventId =
            insertPlaybackEvent(
                PlaybackEventEntity(
                    timestamp = timestamp,
                    videoId = videoId,
                    albumBrowseId = albumBrowseId,
                    durationSecond = durationSecond,
                    listenedSecond = listenedSecond,
                    syncId = syncId,
                ),
            )

        // A track can credit the same channel twice. One play counts once per artist.
        channelIds.distinct().forEach { channelId ->
            insertEventArtist(
                EventArtistEntity(
                    eventId = eventId,
                    channelId = channelId,
                    timestamp = timestamp,
                ),
            )
        }
        return eventId
    }"""
    return source[:matches[0].start()] + method + source[matches[0].end():]
edit("core/data/src/commonMain/kotlin/DatabaseDao.kt", dao)

def handler(source, platform):
    if "import kotlinx.coroutines.CompletableDeferred" not in source:
        source = replace_once(source,
            "import kotlinx.coroutines.CancellationException",
            "import kotlinx.coroutines.CancellationException\nimport kotlinx.coroutines.CompletableDeferred",
            platform + " handler coroutine imports")
    tag_line = re.search(r"private (?:const )?val TAG = [^\n]+\n", source)
    if not tag_line:
        raise SystemExit(platform + ": could not find TAG declaration.")
    source = source[:tag_line.end()] + '\nprivate const val LISTENING_CHECKPOINT_KEY = "analytics_active_listening_checkpoint_v1"\n' + source[tag_line.end():]
    source = replace_once(source,
        "    private val listeningAccumulator = PlaybackListeningAccumulator()",
        """    private val listeningAccumulator = PlaybackListeningAccumulator()
    private val listeningPersistenceMutex = Mutex()
    private val listeningRecoveryReady = CompletableDeferred<Unit>()""",
        platform + " handler persistence state")
    source = replace_once(source,
        "        player.addListener(this)",
        """        player.addListener(this)
        backgroundScope.launch {
            try {
                recoverListeningCheckpoint()
            } finally {
                listeningRecoveryReady.complete(Unit)
            }
        }""",
        platform + " handler recovery startup")
    resume_line = "                listeningAccumulator.resume(nowPlayingState.value.songEntity?.takeIf { it.videoId == player.currentMediaItem?.mediaId }, player.currentPosition)"
    source = replace_once(source, resume_line,
        "                listeningRecoveryReady.await()\n" + resume_line,
        platform + " handler recovery gate")
    tick_line = """                    listeningAccumulator.tick(nowPlayingState.value.songEntity?.takeIf { it.videoId == player.currentMediaItem?.mediaId }, player.currentPosition)?.let {
                        saveListeningSession(it)
                    }"""
    source = replace_once(source, tick_line,
        tick_line + "\n                    listeningAccumulator.checkpoint()?.let { persistListeningCheckpoint(it) }",
        platform + " handler periodic checkpoint")
    pause_line = "                listeningAccumulator.pause(player.currentPosition)"
    source = replace_once(source, pause_line,
        pause_line + """
                listeningAccumulator.checkpoint(force = true)?.let { checkpoint ->
                    coroutineScope.launch { persistListeningCheckpoint(checkpoint) }
                }""",
        platform + " handler buffering checkpoint")
    seek_line = "        listeningAccumulator.seek(positionMs)"
    source = replace_once(source, seek_line,
        seek_line + """
        listeningAccumulator.checkpoint(force = true)?.let { checkpoint ->
            coroutineScope.launch { persistListeningCheckpoint(checkpoint) }
        }""",
        platform + " handler seek checkpoint")

    # The upstream 2.7 percentage-based tracker must not run beside the fixed 30-second
    # accumulator: it would create duplicate events and count short plays prematurely.
    legacy_call = re.compile(
        r"        val lastPlayed = nowPlayingState\\.value\\.songEntity\\n"
        r"        val currentState = simpleMediaState\\.value\\n"
        r"        if \\(currentState is SimpleMediaState\\.Progress && lastPlayed != null && lastPlayed\\.durationSeconds > 0\\) \\{\\n"
        r"            mayBeTrackingListeningLocal\\(lastPlayed, currentState\\.progress\\)\\n"
        r"        \\}\\n"
    )
    legacy_calls = list(legacy_call.finditer(source))
    if len(legacy_calls) > 1:
        raise SystemExit(platform + ": found multiple legacy local-tracking call sites.")
    if legacy_calls:
        source = source[:legacy_calls[0].start()] + source[legacy_calls[0].end():]

    start = source.find("    private fun saveListeningSession(session: CompletedListeningSession) {")
    if start < 0:
        raise SystemExit(platform + ": saveListeningSession method not found.")
    end = source.find("\n    private fun updateDiscordRpc", start)
    if end < 0:
        raise SystemExit(platform + ": could not find the end of saveListeningSession.")
    replacement = """    private fun saveListeningSession(session: CompletedListeningSession) {
        coroutineScope.launch {
            try {
                persistCompletedListeningSession(session)
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                Logger.e(TAG, "Could not persist listening session " + session.syncId + "; checkpoint retained.", e)
            }
        }
    }

    private suspend fun persistListeningCheckpoint(checkpoint: ListeningSessionCheckpoint) {
        listeningPersistenceMutex.withLock {
            val currentRaw = dataStoreManager.getString(LISTENING_CHECKPOINT_KEY).first()
            val current = currentRaw?.takeIf { it.isNotBlank() }?.let {
                runCatching { json.decodeFromString<ListeningSessionCheckpoint>(it) }.getOrNull()
            }
            // Do not let a delayed write from the previous track replace a newer session.
            if (current != null && current.syncId != checkpoint.syncId &&
                current.startedAt >= checkpoint.startedAt
            ) return
            if (current?.syncId == checkpoint.syncId &&
                current.listenedMillis > checkpoint.listenedMillis
            ) return
            dataStoreManager.putString(LISTENING_CHECKPOINT_KEY, json.encodeToString(checkpoint))
        }
    }

    private suspend fun persistCompletedListeningSession(session: CompletedListeningSession) {
        listeningPersistenceMutex.withLock {
            val listenedSeconds = (session.listenedMillis / 1000L).coerceAtLeast(0L)
            if (listenedSeconds > 0L) {
                analyticsRepository.insertPlaybackEvent(
                    videoId = session.song.videoId,
                    channelIds = session.song.artistId ?: emptyList(),
                    albumBrowseId = session.song.albumId,
                    durationSecond = session.song.durationSeconds.toLong(),
                    listenedSecond = listenedSeconds,
                    syncId = session.syncId,
                    timestamp = kotlinx.datetime.LocalDateTime.parse(session.startedAt),
                ).collect { eventId ->
                    Logger.d(TAG, "Saved listening session for " + session.song.title + ": " + listenedSeconds + "s (event " + eventId + ")")
                }
            }
            clearListeningCheckpointIfMatches(session.syncId)
        }
    }

    private suspend fun clearListeningCheckpointIfMatches(syncId: String) {
        val raw = dataStoreManager.getString(LISTENING_CHECKPOINT_KEY).first()
        if (raw.isNullOrBlank()) return
        val checkpoint = runCatching { json.decodeFromString<ListeningSessionCheckpoint>(raw) }.getOrNull()
        if (checkpoint?.syncId == syncId) dataStoreManager.putString(LISTENING_CHECKPOINT_KEY, "")
    }

    private suspend fun recoverListeningCheckpoint() {
        listeningPersistenceMutex.withLock {
            val raw = dataStoreManager.getString(LISTENING_CHECKPOINT_KEY).first()
            if (raw.isNullOrBlank()) return@withLock
            val checkpoint = try {
                json.decodeFromString<ListeningSessionCheckpoint>(raw)
            } catch (e: Exception) {
                Logger.e(TAG, "Discarding an unreadable Insights checkpoint.", e)
                dataStoreManager.putString(LISTENING_CHECKPOINT_KEY, "")
                return@withLock
            }
            try {
                val listenedSeconds = (checkpoint.listenedMillis / 1000L).coerceAtLeast(0L)
                if (listenedSeconds > 0L) {
                    analyticsRepository.insertPlaybackEvent(
                        videoId = checkpoint.videoId,
                        channelIds = checkpoint.channelIds,
                        albumBrowseId = checkpoint.albumBrowseId,
                        durationSecond = checkpoint.durationSecond,
                        listenedSecond = listenedSeconds,
                        syncId = checkpoint.syncId,
                        timestamp = kotlinx.datetime.LocalDateTime.parse(checkpoint.startedAt),
                    ).collect { eventId ->
                        Logger.d(TAG, "Recovered interrupted listening session " + checkpoint.syncId + " (event " + eventId + ")")
                    }
                }
                dataStoreManager.putString(LISTENING_CHECKPOINT_KEY, "")
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                Logger.e(TAG, "Could not recover Insights checkpoint; it will be retried next launch.", e)
            }
        }
    }
"""
    source = source[:start] + replacement + source[end:]

    # A merged 2.7 handler can still contain the now-unused legacy helper if it landed
    # before saveListeningSession. Remove it as well, so no percentage-based writer remains.
    legacy_method = re.compile(
        r"    private fun mayBeTrackingListeningLocal\\(\\n.*?^    \\}\\n",
        re.MULTILINE | re.DOTALL,
    )
    legacy_methods = list(legacy_method.finditer(source))
    if len(legacy_methods) > 1:
        raise SystemExit(platform + ": found multiple legacy local-tracking helpers.")
    if legacy_methods:
        source = source[:legacy_methods[0].start()] + source[legacy_methods[0].end():]

    release_start = source.find("            listeningAccumulator.finish()?.let { session ->")
    if release_start < 0:
        raise SystemExit(platform + ": release finalization block not found.")
    release_end = source.find("\n            mayBeSaveRecentSong", release_start)
    if release_end < 0:
        raise SystemExit(platform + ": release finalization block end not found.")
    release_replacement = """            listeningAccumulator.finish()?.let { session ->
                runBlocking { persistCompletedListeningSession(session) }
            }"""
    source = source[:release_start] + release_replacement + source[release_end:]
    return source

edit("core/data/src/androidMain/kotlin/com/maxrave/data/mediaservice/MediaServiceHandlerImpl.kt", lambda s: handler(s, "Android"))
edit("core/data/src/jvmMain/kotlin/com/maxrave/data/mediaservice/JvmMediaPlayerHandlerImpl.kt", lambda s: handler(s, "JVM"))

print("Crash-safe Insights checkpoints applied to Android and JVM playback handlers.")
