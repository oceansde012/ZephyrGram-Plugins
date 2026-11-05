# Repository state

Snapshot taken 2026-11-05 from `origin/main` at `b84569e` ("ai_autoreply 0.8.1: revive in groups (switch), revive_daily default 3 (#21)"). Every number below was read from files or command output on that commit; anything not verifiable is marked `unknown`.

## Plugins

| id | `__version__` | `__version_code__` | `__min_app_version__` | size (bytes) | permissions |
|---|---|---|---|---|---|
| ai_autoreply | 0.8.1 | 40 | 0.2.2 | 521299 | ai.complete, ai.memory, chat.read, messages.send, network.requests, ui.menu, updates.read |
| chat_history_export | 1.0.2 | 3 | 0.1.4 | 36752 | ui.menu, chat.read, network.requests, java.raw |
| copy_message_id | 1.0.0 | 1 | 0.1.0 | 849 | ui.menu |
| outgoing_signature | 1.0.0 | 1 | 0.1.0 | 1401 | messages.send |

All four use `__api_version__ = 1`. The published index on the `index` branch is `sequence 42`, generated 2026-11-05T13:35:25Z from `b84569e`, and lists the same versions (ai_autoreply 0.8.1/40, chat_history_export 1.0.2/3, copy_message_id 1.0.0/1, outgoing_signature 1.0.0/1). The last `publish` workflow runs on GitHub were all successful.

Other repo parts: `tools/build_index.py` (validate/build/sign/verify/keygen; build writes `index.json` and `index-v2.json`), `.github/workflows/publish.yml`, `templates/hello.plugin`, `docs/API.md` (plugin API v1), `docs/release-reports.json` (per-release report registry, schema 1).

## ai_autoreply

- Version 0.8.1 (code 40) is merged to `main` (PR #21, squash). sha256 of the plugin file: `22824a1f883ed7aa9b6b6289ab2ada3b4eaba326e3be6ed4778dd1fb7d4e5939`; it matches the entry in `docs/release-reports.json`.
- **Size**: 553356 B (0.9.3, minAppVersion 0.2.5, only in index-v2.json; 0.9.0 stays latest in index.json). The hard limit is now `MAX_PLUGIN_BYTES = 2 MiB` (D-020); `LEGACY_MAX_BYTES = 512 KiB` is the limit for `index.json`, which old apps (<= 0.2.4) need. Growing past 524288 B makes ai_autoreply invisible to app <= 0.2.4 (it is omitted from `index.json`; those users stay on the last small version they have, if any) and requires app >= 0.2.5. Until app 0.2.5 ships and is adopted, keep the file under 524288 B (headroom 2989 B). The file has 9189 lines.
- **Tests**: 869 tests collected and passing (`python3 -m pytest -q tests`, about 3 s); the 0.8.1 release report records the same 869. Collect-only count: `python3 -m pytest --collect-only -q tests | tail -2`. No `pytest.ini`/`conftest.py`; tests are plain files in `tests/`. Two files pin the exact version and code (`tests/test_ai_autoreply_v034.py` line 527 and `tests/test_ai_autoreply_v036.py` lines 825-826), so every version bump must edit them (see RELEASE.md).
- **Settings structure**: with `client.SETTINGS_PAGES` true (app 0.2.2+) the screen is a tree of `Page` rows defined by `Plugin.PAGES` (root, chats, persona, style, style_adv, media, timing, time_adv, type_adv, limits_adv, memory, model, model_custom, cmd, service, log, queue, news, bulk, setup1-3, per-chat `chat`, `lore`, `access`). Simple/advanced view is stored as `ui_mode`; a fresh install without chats gets simple view and the three-step quick setup. Without page support the plugin falls back to a legacy flat screen with a `ui_section` selector (`Plugin.UI_SECTIONS`). Enforced by `tests/test_ai_settings_pages_v080.py`: each main category page (root, chats, persona, style, media, timing, memory, model, cmd, service) has at most 14 items (`assertLessEqual(len(...), 14)`); every key of the legacy screen must remain reachable in the page tree; no duplicate keys on any page. The legacy flat screen itself is not limited by that test: the 14-item limit applies to the main (page) items, not to the legacy screen.
- **Presets** (`PRESET_NAMES`): `Balanced`, `Chatty`, `Quiet`, `Live (human-like, default)`; `LIVE_PRESET = 3` is used when no preset is stored.
- **Model**: `NEW_INSTALL_MODEL = "best-of"`, applied only on a brand-new install (no `chats`, `decisions`, `model`, `master`, `humanize`, `preset`, `model_pick` stored; `install_v` is then set to 38). `MODEL_PRESETS` = "", best-of, glm-5.3, kimi-k3, DeepSeek-V4-Pro, DeepSeek-V4.1-Flash, DeepSeek-V4-Flash, glm-5.3-flash.
- **Revive constants** (conversation revival of a quiet chat): `REVIVE_AFTER_MIN = 20`, `REVIVE_WINDOW_H = 3`, `REVIVE_DAILY = 3` (was 1 before 0.8.1; user setting `revive_daily`, range 1-10), `REVIVE_CHECK_SEC = 300`, `REVIVE_PER_PASS = 3`. 0.8.1 added the switch `revive_groups` (default off): revival in groups only for chats in Auto mode. The 0.8.1 CHANGELOG also says no new revival is sent while the person has not answered the previous one.
- Other constants: `MAX_AGE_SEC = 180`, `MAX_FAILURES = 5`, `MAX_REPLY_CHARS = 4000`, `MAX_RETRIES = 2`.
- Phone behaviour of 0.8.x is **unverified** (stated in the release reports; no real-device check has been recorded).

## Branches and worktrees

Compared with `origin/main` (`b84569e`) on 2026-11-05. "Merged" means the branch tip is an ancestor of `origin/main`, or its tree is identical to `origin/main`.

| worktree (in /home/user) | branch | status |
|---|---|---|
| zephyrgram-plugins (main checkout) | ccr-40da9ed7-07luj0 | merged (ancestor; 54 commits behind main); also exists on origin |
| wt-appr-p | feature/approval-bot | merged (ancestor, no own commits, local only) |
| wt-cmdmem-p | feature/commands-memory | merged (ancestor, no own commits, local only) |
| wt-guihub-p | feature/gui-ai-hub | merged (ancestor, no own commits, local only) |
| wt-medlib-p | feature/media-library | merged (ancestor, no own commits, local only) |
| wt-profile-p | feature/profile-context | merged (ancestor, no own commits, local only) |
| wt-vidvoice-p | feature/video-voice | merged (ancestor, no own commits, local only) |
| zg-p-cost | plugin-cost | merged (ancestor, no own commits, local only) |
| wt-merge-p | ai-revive-groups-081 | content merged: PR #21 was squash-merged (tip `848bbeb` has a tree identical to `main`), so git does not see it as an ancestor. **Has an uncommitted modification** to `plugins/ai_autoreply/ai_autoreply.plugin` (unknown origin); check before removing. Branch also exists on origin. |
| wt-anti-inline | feature/anti-inline | **not merged**: 1 commit ahead (`8c025fb`, "docs: request core hook for inline-bot results (anti_inline blocked)", +8 lines in `docs/API.md`), 17 behind; also on origin. Worktree has an uncommitted modification to the plugin file. |
| wt-docs-plugins | docs/state-decisions | this docs work |

The six `feature/*` branches and `plugin-cost` sit at `a33de2b` (an old main commit) with nothing of their own, so "merged" only says they hold no unique work. Also on origin: `fix/quality-0.7.7` (merged via PR #19) and `ccr-40da9ed7-07luj0`. Two detached scratch worktrees exist in the session scratchpad (`old61`, `rv-plugins`).

## Known limitations

- **Menu types**: `docs/API.md` lists `MESSAGE_CONTEXT`, `CHAT_ACTION`, `PROFILE_ACTION`, `DRAWER`. The current app does not render `CHAT_ACTION` or `PROFILE_ACTION` menus; only `MESSAGE_CONTEXT` is wired in `ChatActivity` (stated in the 0.8.1 release report; the app source is not in this repo, so this was not re-verified here). Consequences: the ai_autoreply chat-header toggle (`menu_on`/`menu_off`/`menu_cmd`, registered as `CHAT_ACTION`) and chat_history_export's "export" menu item (`CHAT_ACTION`) are not reachable from the chat header; chat_history_export is started from its settings screen instead (since 1.0.1).
- **Plugin size**: single file, 2 MiB hard limit via `index-v2.json` (D-020; app >= 0.2.5 must fetch `index-v2.json` first, falling back to `index.json`; the app is not in this repo, so this is not verified here). Versions over 512 KiB are hidden from older apps. 2989 B left below the legacy 512 KiB line in ai_autoreply.
- **Phone verification**: 0.8.0/0.8.1 behaviour and the settings pages have not been checked on a real device (unverified in release reports).
- Release reports mention that earlier races (typing cancellation, lost timer) were tested only with synthetic tests.
- Anti-inline-bot plugin is blocked on a core hook request (branch `feature/anti-inline`, not merged).

## Next steps

1. Ship app 0.2.5 (fetch `index-v2.json` + `.sig` first, fallback `index.json`); after the first publish check that the `index` branch has all four files. D-019 is closed by D-020. Until 0.2.5 is widely adopted, avoid pushing ai_autoreply over 524288 B.
2. Check 0.8.1 and the 0.8.0 settings pages on a phone and record the result.
3. Decide on `feature/anti-inline` (docs request for a core hook) and the app side of `CHAT_ACTION`/`PROFILE_ACTION` rendering.
4. Clean up merged branches/worktrees listed above (inspect the two worktrees with uncommitted changes first).
