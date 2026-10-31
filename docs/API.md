# ZephyrGram Python plugin API, version 1

Plugins are single UTF-8 Python files named `<id>.plugin`, run in-app by Chaquopy
(CPython 3.13). Supported on arm64-v8a and x86_64 devices; 32-bit-only devices cannot
run plugins. The plugin API is the Python module `zephyr` (plus `zephyr.ui`,
`zephyr.client`). Python starts lazily, only when at least one plugin is enabled.

There is no real sandbox. Security comes from the signed index, sha256 pinning,
revocation and owner review. Never install plugins from sources you do not trust.

## 1. File layout and metadata

Metadata are plain top-level literals (parsed by regex in the app and by
`ast.literal_eval` in CI, so no expressions or f-strings):

| Constant | Type | Notes |
|---|---|---|
| `__id__` | str | `^[a-z][a-z0-9_]{2,31}$`, must equal the file name stem and directory name |
| `__name__` | str | display name |
| `__description__` | str | short description |
| `__author__` | str | |
| `__version__` | str | SemVer `MAJOR.MINOR.PATCH[-pre]` |
| `__version_code__` | int | strictly increasing for every published change |
| `__api_version__` | int | `1` |
| `__min_app_version__` | str | SemVer; app `ZEPHYR_VERSION` must be `>=` |
| `__max_app_version__` | str, optional | SemVer, exclusive upper bound |
| `__permissions__` | list[str] | see section 2 |
| `__icon__` | str, optional | short name; an `icon.png` (<=64 KB) next to the plugin is preferred |

After the metadata: `from zephyr import ...` and exactly one `class Plugin(BasePlugin)`.
Keep the file <= 512 KB, LF line endings, no BOM.

## 2. Permissions

| Permission | Grants |
|---|---|
| `network.requests` | `add_request_hook`, `client.send_request` (Telegram API requests/responses) |
| `updates.read` | `add_update_hook`, `add_on_new_message_hook` (incoming updates/messages) |
| `messages.send` | `add_on_send_message_hook`, `client.send_text`, `client.send_sticker`, `client.set_draft` |
| `chat.read` | `client.get_recent_messages`, `client.get_recent_stickers`, `client.get_dialog_info`, `client.search_dialogs` (cached chat data), `client.resolve_username` (may use the network) |
| `ai.complete` | `client.ai_complete` (the user's configured AI server; the token is never exposed) |
| `ui.menu` | `add_menu_item` |
| `internet` | `client.http_get` (outside Telegram) |
| `java.raw` | direct Java access via `from java import jclass` (the UI warns about this) |

An update that adds a permission is held back until the user approves it.
Calling an API without its permission raises `PermissionError`.

## 3. `zephyr.BasePlugin`

Attributes: `id`, `name`, `version`, `data_dir` (private writable directory, survives
updates, removed on uninstall).

Lifecycle (override as needed; all optional):

```python
def on_plugin_load(self): ...
def on_plugin_unload(self): ...
def on_app_event(self, event): ...        # AppEvent.START / PAUSE / RESUME / STOP
                                          # also the string "settings_changed" (see below)
def create_settings(self): ...            # -> list of zephyr.ui items
```

`settings_changed` (app 0.1.4+): sent to ONE plugin (not broadcast) after the core app edited that plugin's stored
settings from its own screen. It is delivered as a plain string, not an `AppEvent` member (the `AppEvent` class only
has `START`, `PAUSE`, `RESUME`, `STOP`), on the plugin's background executor. Compare defensively, e.g.
`name = getattr(event, "name", None) or event; if str(name) == "settings_changed": ...`, and ignore unknown events.
Re-read anything cached from `get_setting`; keep runtime state (timers, counters). `client.app_locale()` ('uk',
'ru', 'en', app 0.1.4+, no permission) gives the UI language; guard with `hasattr(client, "app_locale")`.

Helpers:

```python
self.log(msg)                    # -> data_dir/log.txt
self.error(msg_or_exception)
self.get_setting(key, default=None)
self.set_setting(key, value)     # str, int, float, bool

self.add_request_hook(name, match_substring=False, priority=0)
self.add_update_hook(name, match_substring=False, priority=0)
self.remove_request_hook(name)
self.add_updates_hook(name, match_substring=False, priority=0)   # updates.read; whole containers
self.add_on_send_message_hook(priority=0)
self.add_on_new_message_hook(priority=0)                          # updates.read
self.add_on_message_edited_hook(priority=0)                       # updates.read
self.add_on_messages_deleted_hook(priority=0)                     # updates.read
self.add_menu_item(menu_item)    # MenuItem
self.remove_menu_item(menu_item)
```

`name` is the TL class name without the `org.telegram.tgnet.` prefix, `TLRPC$` stripped
and `$` replaced by `.` (for example `TL_messages_sendMessage`, `TL_updateNewMessage`).
With `match_substring=True` the hook fires for every name that contains `name`;
the empty string with `match_substring=True` matches everything (slow, avoid).
Higher `priority` runs first.

Hook callbacks (define on your `Plugin` class):

```python
def pre_request_hook(self, name, account, request):            # -> HookResult
def post_request_hook(self, name, account, response, error):   # -> HookResult
def on_update_hook(self, name, account, update):                # -> HookResult  (single update)
def on_updates_hook(self, name, account, updates):              # -> HookResult  (container)
def on_send_message_hook(self, account, params):                # -> HookResult  (SendMessageParams)
def on_new_message(self, account, message_object):              # -> None
def on_message_edited(self, account, message_object):           # -> None
def on_messages_deleted(self, account, dialog_id, message_ids): # -> None
```

`on_new_message`, `on_message_edited` and `on_messages_deleted` are informational: they run
asynchronously on a separate worker thread (in order), after Telegram accepted the update,
and their return value is ignored. All other hooks run synchronously on the thread that
performs the work (network/update thread for requests and updates, usually the UI thread for
`on_send_message_hook`) and block it until they return.

`request`, `response`, `update`, `updates`, `params` and `message_object` are Java
objects (Chaquopy proxies); read/write fields and call methods directly
(`params.message`, `message_object.getId()`).

### Hook results

```python
from zephyr import HookResult, HookStrategy
HookResult(strategy=HookStrategy.DEFAULT, request=None, response=None,
           error=None, update=None, updates=None, params=None)
```

| Strategy | Effect |
|---|---|
| `DEFAULT` | do nothing, continue |
| `CANCEL` | drop the request/update/send. For a request, if `response` (or `error`) is set it is delivered to the caller, otherwise a `TL_error` (-1000, `PLUGIN_CANCELLED`) is. Cancelling an `on_updates_hook` container is **ignored** (it would corrupt Telegram's pts/seq counters); cancel individual updates with `on_update_hook` instead |
| `MODIFY` | use the provided `request`/`response`/`error`/`update`/`updates`/`params`, later hooks still run. A `post_request_hook` result with neither `response` nor `error` keeps the original answer. A replaced `updates` container must be the same class with identical `seq`, `seq_start`, `pts`, `pts_count`, `date`, `id`, otherwise it is ignored |
| `MODIFY_FINAL` | as `MODIFY`, but no further hooks run |

Returning `None` equals `HookResult()`. Python exceptions inside hooks are caught,
logged to `data_dir/log.txt` and treated as `DEFAULT`. A plugin raising 5 exceptions
(`self.error(...)` calls and hooks blocking for more than 3 s count too) within 60 s is
disabled automatically. Hooks slower than 200 ms are logged; keep hooks fast, they run on the
network or UI path and Python cannot be interrupted. Use `client.run_in_bg` for anything slow.
`on_send_message_hook` is not applied again to retries of a failed message or to the host's
internal re-entry of the same `SendMessageParams`; messages sent through `client.send_text`
skip send hooks.

## 4. Menus

```python
from zephyr import MenuItem, MenuType
MenuItem(menu_type, text, on_click, icon=None, subtext=None, priority=0, condition=None, key=None)
```

| `MenuType` | Where |
|---|---|
| `DRAWER` | top-level app menu (the chat list "three dots" menu in this fork, which has no drawer) |
| `MESSAGE_CONTEXT` | message long-press options in a chat |
| `CHAT_ACTION` | chat header menu |
| `PROFILE_ACTION` | profile screen menu |

`on_click(ctx)` receives a dict with keys `account` (int), `dialog_id` (int, may be 0),
`message` (MessageObject or `None`), `fragment` (current Fragment or `None`),
`context` (Android Context). `icon` is an Android drawable resource name (str). `condition(ctx)` (optional) decides whether
the item is shown; it runs on the UI thread every time the menu is built, so keep it trivial.
`key` identifies the item (re-adding the same key replaces it).

## 5. Settings UI: `zephyr.ui`

`create_settings()` returns a list of:

```python
Header(text)
Divider()
Text(text, on_click=None)
Switch(key, text, default=False, subtext=None, on_change=None)
Input(key, text, default="", subtext=None, on_change=None, hint=None, multiline=False)
Selector(key, text, items, default=0, subtext=None, on_change=None)   # items: list[str]; value = index
DialogPicker(key, text, on_pick, subtext=None)
UsernameInput(key, text, on_resolved, subtext=None, hint=None)
```

Values are stored per plugin; read them with `self.get_setting(key, default)`.
`on_change(value)` is called on the UI thread. After a `Text.on_click`, `DialogPicker` or
`UsernameInput` callback the settings screen calls `create_settings()` again, so changes you
made (added/removed rows) show up.

**How rows render (host `ZephyrPluginSettingsActivity`).** `Header` is a one-line, non-clickable
title. `Text` is a clickable one-line button (`UItem.asButton`): longer text is cut and a tap only
runs `on_click`. `subtext` of any item and the text of a `Divider` are drawn as a grey, multi-line,
non-clickable block (`UItem.asShadow`). So for long explanations use a `Divider` whose `text`
attribute you set (`d = Divider(); d.text = "..."`; the constructor takes no argument) and for a
readable list use `Header(title)` + such a block per entry; never put long text into `Text`.

**`DialogPicker`** is a button that opens Telegram's own chat picker (the same screen used by
Forward/Share, over the user's chat list). When the user chooses a chat, `on_pick(dialog_id, title)`
runs on the UI thread (so use `client.run_in_bg` for blocking calls). The picker needs no permission.

**`UsernameInput`** is a button that opens an input dialog for `@username`, `username` or a
`t.me/username` link. The host resolves it asynchronously (local cache, then Telegram's
`contacts.resolveUsername` over the network), shows an error if the name does not exist or is not a
public username (invite links and phone numbers are not supported), and otherwise calls
`on_resolved(dialog_id, title)` on the UI thread. It needs no permission because the owner types the
name; the plugin only sees the result.

## 6. `zephyr.client`

```python
client.send_request(request, callback=None, account=None)   # network.requests
    # callback(response, error); account defaults to the current one
client.send_text(dialog_id, text, reply_to=None, account=None)   # messages.send
    # reply_to: message id in the same dialog to reply to. NOTE: `account` is now the 4th parameter.
client.set_draft(dialog_id, text, account=None)             # messages.send
    # Puts text into the chat input draft for the user to review ('suggest' mode). "" clears it.
    # If that chat is open right now the input box may not refresh until it is reopened.
client.ai_complete(messages, system=None, model=None, temperature=None, timeout=60) -> str   # ai.complete
client.get_recent_messages(dialog_id, limit=20, account=None) -> list[dict]   # chat.read
client.get_dialog_info(dialog_id, account=None) -> dict                       # chat.read
client.get_recent_stickers(limit=30, account=None) -> list[dict]              # chat.read
client.send_sticker(dialog_id, sticker_id, account=None, reply_to=None) -> bool   # messages.send
client.search_dialogs(query, limit=20, account=None) -> list[dict]            # chat.read
client.resolve_username(username, account=None) -> dict | None                # chat.read, network
client.message_to_dict(message_object) -> dict   # also zephyr.message_to_dict; no permission needed
client.current_account() -> int       # selected account index (default `account` of the helpers)
client.run_on_ui(fn, delay_ms=0)
client.run_in_bg(fn)
client.bulletin(text)                  # short toast-like message (UI thread safe)
client.copy_to_clipboard(text)         # clipboard helper
client.http_get(url, headers=None, timeout=15) -> (status:int, body:bytes)   # internet
client.app_version() -> str            # ZEPHYR_VERSION, e.g. "0.1.0"
client.api_version() -> int            # 1
client.app_locale() -> str             # 'uk' | 'ru' | 'en' (app 0.1.4+; guard with hasattr)
```

`run_on_ui` / `run_in_bg` callbacks that raise are logged and swallowed.

### AI and chat helpers

**`ai_complete(messages, system=None, model=None, temperature=None, timeout=60) -> str`**
Synchronous, non-streaming chat completion through the AI server configured in ZephyrGram
settings (URL, token, model). The plugin never sees the token. `messages` is a list of
`{"role": "user"|"assistant"|"system", "content": str}` (a plain string means one user message);
`system` is prepended as a system message (the app's own assistant system prompt is NOT used).
`model=None` uses the configured model, `temperature=None` the configured one (0..2 otherwise).
`timeout` seconds (1..300). Blocking: call it only from a worker thread (`client.run_in_bg`);
on the UI thread it raises `IllegalStateException`. At most 3 requests run at once; input is
capped at 200000 characters. Failures raise `zephyr.AiError` (`.code`: 1 not configured,
2 unauthorized, 3 rate limit, 4 server starting, 5 network/timeout, 6 server error), or
`PermissionError` without `ai.complete`.

**`get_recent_messages(dialog_id, limit=20, account=None) -> list[dict]`**
Newest first. Reads the local message database only (no network, no history loading), so
messages that were never synced to this device are missing and a message that arrived a
fraction of a second ago may not be stored yet. `limit` is clamped to 1..100. Blocking
(short disk read): worker thread only. Each dict: `id, dialog_id, from_id (user id, negative
chat/channel id), out (bool), date (unix seconds), text (caption for media, "" if none),
is_bot, is_secret, is_service, reply_to (message id or None), has_media`.

**`get_recent_stickers(limit=30, account=None) -> list[dict]`** (`chat.read`)
Recent stickers, newest first (favorites are appended after them, duplicates removed). Served
from the in-memory cache, never blocks on the network. If the cache is not loaded yet, a
background load starts and the list may be empty: retry a moment later. `limit` is clamped to
1..100. Each dict: `id` (document id, int), `emoji` (associated emoji or ""), `set_title`
(sticker set title if the set is cached, else ""), `mime`, `is_animated` (bool).

**`send_sticker(dialog_id, sticker_id, account=None, reply_to=None) -> bool`** (`messages.send`)
Sends the sticker whose document `id` is `sticker_id`, looked up among recent, favorite and
installed stickers. Returns `True` if queued, `False` if not found or the chat is a secret chat.
Marked like `send_text` (plugin hooks are skipped for it; ghost mode still applies) and, like
`send_text`, returns no message id. `reply_to` is a message id in the same dialog. Worker thread only.

**`get_dialog_info(dialog_id, account=None) -> dict`**
`{id, title, type: 'user'|'group'|'channel'|'secret', is_bot, username (None if absent)}`
from cached users/chats; `title` is "" if the peer is not cached.

**`search_dialogs(query, limit=20, account=None) -> list[dict]`**
Chats from the user's chat list whose title or `@username` contains `query` (case-insensitive;
empty query lists the first ones). Local cache only, never touches the network. Returns
`[{id, title, type, username}]` with `type` as in `get_dialog_info`; `limit` is clamped to 1..100.

**`resolve_username(username, account=None) -> dict | None`**
Accepts `@name`, `name`, `t.me/name` or `https://t.me/name`. Returns `{id, title, type, is_bot,
username}` or `None` if no such public user/chat exists or the text is not a valid public username.
Looks in the local cache first; for unknown names it sends `contacts.resolveUsername` to Telegram
(**network use**, up to ~20 s, counts toward Telegram flood limits, so do not call it in a loop).
Blocking: worker thread only (`IllegalStateException` on the UI thread). Raises `OSError`-like
Java `IOException` on timeout/network errors and `PermissionError` without `chat.read`.

**`message_to_dict(message_object) -> dict`**
Same shape as above for the `MessageObject` passed to `on_new_message(account, message_object)`
(`on_message_edited` too). `dialog_id` is included, so you rarely need `Java` fields.

**Ghost mode and plugins.** `send_text` / `set_draft` use the normal send path. Messages go
through `ZephyrGhost` like everything else, so ghost mode (no typing, no read receipts, ...)
is not bypassed or switched off by a plugin; a plugin that replies does not mark chats as read
either. A plugin cannot read or change ghost settings.

### Safety guidelines for auto-reply plugins

- Default to **draft/suggest** mode (`set_draft`); automatic sending must be an explicit,
  per-chat opt-in setting that is off by default, with an allow-list of dialogs.
- Never reply to `out` messages, bots (`is_bot`), service messages (`is_service`), secret
  chats (`is_secret`, unless the user opted in; text goes to the AI server), channels, or
  your own plugin's messages. Ignore edits and old messages (check `date`).
- Rate limit: per-dialog cooldown, a global cap per minute/hour, and a reply-chain limit so
  two auto-responders cannot loop. Stop on repeated errors.
- Run `ai_complete` in `client.run_in_bg`, never in a hook; hooks that block more than 3 s
  count as plugin errors and can disable the plugin.
- Tell the user what is sent to the AI server (chat text leaves the device). Send only the
  minimum context (`limit` small), strip phone numbers/links if possible, and never log
  message text unless the user enabled debugging.
- Treat chat text as untrusted input (prompt injection): never let it choose recipients,
  dialogs, settings or tools; the model output is only ever sent to the dialog it came from.
- Cap reply length, drop empty replies, and optionally prefix them (e.g. "[auto]") so people
  know a bot answered.

Example (suggest mode):

```python
def on_new_message(self, account, mo):
    m = client.message_to_dict(mo)
    if m["out"] or m["is_bot"] or m["is_service"] or m["is_secret"] or not m["text"]:
        return
    if m["dialog_id"] < 0 or m["dialog_id"] not in self.allowed:
        return
    def work():
        hist = client.get_recent_messages(m["dialog_id"], 10)[::-1]
        chat = [{"role": "assistant" if x["out"] else "user", "content": x["text"]} for x in hist if x["text"]]
        try:
            reply = client.ai_complete(chat, system="Reply briefly as me.", timeout=45)
        except Exception as exc:
            self.log("ai error: %s" % exc)
            return
        client.run_on_ui(lambda: client.set_draft(m["dialog_id"], reply[:1000]))
    client.run_in_bg(work)
```

## 7. Life cycle, updates and failure handling

- A load marker is written before each plugin loads; a plugin that crashes the app twice
  is disabled, three early crashes (<30 s after start) enable safe mode (all plugins off).
- There is no dedicated plugin thread: callbacks run on whichever app thread triggers them
  (network/update thread, UI thread, or the `ZephyrPlugin*` worker threads) and share one
  Python GIL. `on_plugin_load` runs on the plugin manager thread; blocking in it delays startup.
  Threads you start yourself have no plugin context, so `zephyr` helpers raise `RuntimeError`
  there; use `client.run_in_bg` / `client.run_on_ui`.
- Each log is capped (256 KB, rotated to `log.old.txt`).
- Plugin updates keep the previous file; a failed update rolls back automatically.
- `data_dir` and settings persist across updates.

## 8. Examples

Request hook that blocks "typing" notifications:

```python
class Plugin(BasePlugin):
    def on_plugin_load(self):
        self.add_request_hook("TL_messages_setTyping")

    def pre_request_hook(self, name, account, request):
        return HookResult(strategy=HookStrategy.CANCEL)
```

See `templates/hello.plugin` and `plugins/` for complete, working samples.

## 9. Core change requests

Proposals only, not implemented. `ai_autoreply` 0.3.2 works around the first two.

1. `Divider(text="")` and `Text(text, on_click=None, clickable=True, multiline=False)`: a constructor
   argument for the text of a `Divider` (today it is a class attribute that has to be assigned on an
   instance) and a way to mark a `Text` row as non-clickable and multi-line (`clickable=False` would map
   to a non-interactive `UItem`, `multiline=True` to unlimited lines). Java: `PluginSettingsModel.Item`
   already has `multiline`; `ZephyrPluginSettingsActivity.fillItems` would use it for `TYPE_TEXT`.
2. `client.app_locale() -> str`: language code of the app UI, e.g. `"uk"`, from
   `LocaleController.getInstance().getCurrentLocale().getLanguage()`. Without it a plugin cannot follow
   the app language (Python `locale`/`LANG` is not the app locale and `java.raw` is a heavy permission), so
   `ai_autoreply` has an `Interface language` setting (Auto = phone language if visible, else Ukrainian).
3. `Header(text, multiline=False)`: long section titles are cut to one line.

## 10. ai_autoreply storage format

For other parts of the app (for example a core screen that lists the chats where the bot is active).
Everything lives in the plugin's settings store (`id = ai_autoreply`, one string/int/bool value per key).
The format is stable since 0.3.0; 0.3.4 only adds optional keys (marked *new*). Readers must ignore unknown keys.

**`chats`** (string, JSON object; missing, empty or invalid = no chats). Key: `"<account>:<dialog_id>"`
(`account` = account index, `dialog_id` = Telegram dialog id as a signed integer: user id > 0, group/chat id < 0),
for example `"0:123456789"`. Value:

```json
{"enabled": true, "account": 0, "dialog_id": 123456789, "title": "Alice", "type": "user", "fails": 0}
```

| field | type | meaning |
|---|---|---|
| `enabled` | bool | the bot answers in this chat. `false` = paused (switched off in the menu or settings) |
| `account` | int | account index |
| `dialog_id` | int | dialog id (same as in the key) |
| `title` | string | chat title when it was added (refreshed from dialog info when the settings screen opens) |
| `type` | string | `"user"` (private chat) or `"group"`; channels, bots and secret chats are never stored |
| `fails` | int | consecutive AI/send failures (reset on success; at 5 the chat is auto-paused) |
| `auto_off_ts` | number, optional | unix time when errors paused the chat; resumes after 30 minutes |
| `disclosed` | bool, optional | the AI disclosure prefix was already sent in this chat |

"Active" chat = `enabled == true`. `.ai off` removes the entry, the chat-menu toggle and the "Enabled" switch only
set `enabled`.

**Per-chat settings**, key suffix `<sk>` = the chat key with `:` replaced by `_` and `-` by `n`
(`"0:123456789"` -> `0_123456789`, `"0:-1001"` -> `0_n1001`):

| key | type | meaning |
|---|---|---|
| `mode_<sk>` | int | `0` Auto (answers by itself), `1` Draft (writes into the input field), `2` Friend (the other person triggers with `.ai `). Missing = `0` |
| `prompt_<sk>` | string | extra system prompt for this chat, empty = default |
| `keep_<sk>` | bool | mirror of `enabled` for the settings switch |
| `rlang_<sk>` | int, *new* | reply language for this chat: `0` as global, `1` Auto, `2` Ukrainian, `3` Russian, `4` the other person's language |

**Global settings of interest:** `master` (bool, default true; false = the bot is silent everywhere),
`reply_lang` (int, *new*: `0` Auto by the owner's context, `1` Ukrainian, `2` Russian, `3` the other person's
language; since 0.3.6 a missing value means `3`), `preset` (int: `0` Balanced, `1` Chatty, `2` Quiet, `3` Live; since
0.3.6 a missing value means `3` Live, an explicit `0..2` stays), `owner_active` (string, seconds the bot stays
silent after the owner wrote in the chat; empty = preset, Balanced 45), `chat_hourly` (string; empty = preset,
Balanced 20), `ui_lang` (int: `0` auto, `1` uk, `2` ru, `3` en).

**0.4.0 additions.** `reply_all` (bool, default false: a private chat that is not in `chats` is added automatically when
its person writes; never groups, channels, bots, secret chats, listed chats or chats in `all_skip`), `all_accounts`
(string of 1-based account numbers, empty = all), `all_skip` (JSON text of a list of chat keys the owner removed;
written by the plugin on removal and by the core screen's remove; cleared for a key when it is added again),
`skip_links` (bool, default true: incoming messages with a link are not answered), `short_msgs` (bool, default true: the
answer is written as 1-4 short separate messages, `max_parts` string, default 4), `revive` (bool, default false: a
quiet conversation in an Auto chat is restarted with a fitting topic), `revive_after` / `revive_window` /
`revive_daily` (minutes of silence, hours after which the chat counts as finished, revivals per chat per day),
`revive_marks` (JSON text of {chat key: [timestamps]}, internal).

**0.4.2 additions.** `lore` (string, the owner's description of themselves, goes into the prompt as the only personal
facts the AI may state), `lore_learn` (bool, default false: the AI keeps short notes about each chat), per chat
`lore_<sk>` (string, owner's facts about this chat's person) and `learned_<sk>` (string, lines `- note`, written by the
plugin, editable; removed together with the chat).

**`decisions`** (string, JSON array, at most 400 since 0.4.4 (60 since 0.3.6, 20 before), oldest first, no message
text; since 0.4.4 written at most every 5 s, plus on unload, copy, clear and report, so the stored value can lag a
few seconds behind the plugin):
`{"t": <unix seconds>, "chat": "<account>:<dialog_id>", "o": "<outcome>", "r": "<reason code>"}` (0.3.7: plus an optional `"x"`, a short extra such as an emoji).
`o` is one of `sent`, `draft`, `skip`, `error`, `disabled`, `resume`, `test`, and (*new*) `seen`
(reason `incoming_seen`: a message from the other person reached the plugin; consecutive ones of a chat are
collapsed into one entry) and `cmd` (in-chat commands: `admin_on`, `admin_off`, `admin_status`, `admin_list`,
`admin_log` (0.4.4),
`admin_mode_auto|draft|friend`, `admin_refused`, `menu_on`, `menu_off`). Since 0.3.6 also `info` (timing and
side actions: `scan_found`, `latency_wait_<seconds>`, `typing_sent`, `read_sent`, `read_blocked_by_ghost`,
`sticker_sent`) and `defer` (`deferred_owner_active`: the reply is postponed, not dropped). The last real decision of
a chat is the newest entry of that chat whose `o` is not `seen`, `cmd` or `info`.

To list active chats: parse `chats`, keep entries with `enabled == true`, show `title`, mode from `mode_<sk>`.
To add or remove a chat from the core side, write the same JSON back (keep unknown fields) and set `mode_<sk>`
to `0` for a new chat. Since 0.3.5 the plugin re-reads `chats` (and drops its reply-language cache) when it receives
the app event `settings_changed` (see section 3), so after a core-side edit call
`PluginManager.notifySettingsChanged("ai_autoreply")`. The plugin's own writes are reload-merge-save: it re-reads
`chats`, changes only the one chat field(s) it owns and writes back, so concurrent core edits are not lost. Per-chat
keys (`mode_`, `keep_`, `rlang_`, `prompt_`) and `master` are read from the store on every use and need no reload.

**In-chat owner commands (private chats only, never sent as messages):** `.ai on` (add/enable, mode Auto),
`.ai off` (remove), `.ai status`, `.ai list`, `.ai mode auto|draft|friend`, `.ai start` (0.4.3), `.ai log` (0.4.4,
see section 18). They are intercepted by the send hook;
the command words (default `.ai`, `.аі`) are the `cmd_triggers` setting and the whole feature is `cmd_enable`.

## 11. ai_autoreply 0.3.6: Live preset, scan, human timing, read marks, stickers

Preset `3` **Live** is the default when `preset` is missing (new installs and settings without an explicit choice);
Balanced/Chatty/Quiet (`0..2`) behave as before. Every number below is an optional string setting; empty = the value
of the current preset (Live column), a value overrides it. Switches (`human_timing`, `scan`) behave the same: unset =
preset (on in Live, off in the others).

| setting | Live default | meaning |
|---|---|---|
| `debounce`, `cooldown` | 2-5 s, 0-3 s (`cooldown_jitter`) | burst collection and pause between conversational turns |
| `owner_active` / `owner_defers` | 15 s / 8 | silence after the owner's own message; the reply is **deferred** (retried up to `owner_defers` times), not dropped. If the owner wrote after the incoming message arrived, the bot stays silent (`owner_replied`) |
| `chat_hourly`, `hourly_cap`, `daily_cap` | 60, 0 (= none), 400 | per-chat hourly, global hourly and per-chat daily limits |
| `loop_burst` | 10 | own replies within 2 min that count as a ping-pong loop (others: 4) |
| `ack_reply_pct` | 25 | chance to answer a plain acknowledgement ("ок", "дякую"); questions are always answered; emoji-only messages are still skipped |
| `lat_warm_min/max` | 2 / 9 s | reply latency (from the arrival of the first message) when the interlocutor's previous message is younger than `warm_window` (120 s) and somebody replied within 5 min |
| `lat_cold_min/max` | 8 / 40 s | latency after more than `cold_after` (600 s) of silence; `lat_long_pct` (10 %) of them take `lat_long_min/max` (60-120 s) |
| `type_ms`, `warm_cap` | 35 ms/char, 25 s | typing time per reply character is added to the latency; the whole warm latency is capped |
| `split2_pct`, `split_gap_min/max` | 15 %, 1-3 s | chance to send a reply with a natural break as 2 messages, and the pause between them |
| `catchup_min`, `scan_interval` | 30 min, 25 s | maximum age of a message to answer; period of the safety-net scan |
| `show_typing`, `read_msgs`, `read_always`, `stickers`, `sticker_pct`, `sticker_recent` | on, on, off, on, 12, on | independent of the preset |

**Safety-net scan.** Besides `on_new_message` and the two short-update hooks, a timer (`client.run_on_ui` +
`client.run_in_bg`, one chain) runs every `scan_interval` s (+-15 %): for each enabled chat it reads
`client.get_recent_messages(dialog_id, limit=8)`, takes the incoming run after the newest outgoing message that is not
younger than 6 s (the events own those), not older than `catchup_min`, above the chat's last handled id (`scan_marks`)
and not already seen/answered, and feeds at most 5 of them into the normal pipeline (reason `scan_found`; the same
de-duplication as the events). With no enabled chat or `master` off the interval backs off to 60 s; the chain stops
when the scan is switched off and restarts on `settings_changed`, app `START`/`RESUME` (which also run one pass after
1.5 s). Nothing in it sleeps.

**Typing and read marks use Telegram requests.** `client.send_request` (permission `network.requests`, added in 0.3.6)
needs a TLRPC object. As `zephyr.client` has no typing/read helper yet, the plugin builds
`TL_messages_setTyping` (`TL_sendMessageTypingAction` / `TL_sendMessageCancelAction`) and `TL_messages_readHistory`
(private chats only, `max_id` = newest answered message) with `java.jclass` and `MessagesController.getInputPeer`.
If the client ever gets `set_typing(dialog_id, account=None, cancel=False)` or `mark_read(dialog_id, max_id,
account=None)` (also `send_typing` / `read_history`), the plugin calls those first. Everything is wrapped in
try/except: when Java access or a helper is missing the plugin silently works without typing/read marks.
`ZephyrGhost.intercept` drops `messages.readHistory` (ghostNoRead) and answers typing with a fake `true`
(ghostNoTyping) without telling the caller, so the plugin reads `ZephyrConfig.ghostNoRead/ghostNoTyping` first: reading
is skipped and logged as `read_blocked_by_ghost` (once an hour per chat; turn off "do not read" in ghost mode to get
read marks), typing is skipped silently.

**Stickers (0.3.7: chosen by context).** They need `client.get_recent_stickers(limit, account)` and
`client.send_sticker(dialog_id, sticker_id, account, reply_to)` (section 6; missing = no stickers). `sticker_pct`
(12) is the chance per reply (private chats, never for questions) to ask a separate `client.ai_complete` call, the
"picker": system prompt = decide with strict JSON `{"use_sticker": bool, "index": N, "reason_emoji": "...", "mode":
"instead"|"after"}`, use a sticker only when it naturally fits and never for serious/conflict/informational messages;
user content = the last chat messages, the incoming message(s), the finished reply and the candidates numbered from
1 (`3: <emoji> (<set_title>)`, first 25 recent stickers, not the last id/set used in the chat). The answer is parsed
leniently (JSON found inside text); on garbage or an AI error only a sticker whose emoji appears in the reply is used,
otherwise none. `instead` is honoured only when the text reply is <= 30 characters. If the app provides
`client.get_message_media(dialog_id, message_id, account=None) -> dict` (keys `kind`, `emoji`, `set_title`,
`description`, all optional) and the setting `see_media` is on, the description of the newest incoming media is added to
the picker prompt. Log reasons: `sticker_decided_yes` (record field `x` = the emoji), `sticker_decided_no`,
`sticker_skipped_<why>`, `sticker_sent`.

**Language.** `reply_lang = 3` (default): the language of the messages being answered decides (distinctive letters
ы э ъ ё / і ї є ґ and everyday words), then the last 2-3 incoming messages, then the owner's own messages, then
Ukrainian; the prompt says to answer in the language the other person wrote in. Storage additions: `scan_marks`
(JSON object chat key -> highest handled message id).

## 12. Media for vision (0.1.5): `get_message_media`, `ai_complete(images=)`

```
client.get_message_media(dialog_id, message_id, account=None, max_side=768, timeout_s=20) -> dict | None   # chat.read
client.ai_complete(messages, system=None, model=None, temperature=None, timeout=60, images=None) -> str    # ai.complete
```

**`get_message_media`** is blocking: call it from `client.run_in_bg` only. It reads the message from the local
database, never throws into Python on failure (returns `None` when the message or its media is not found, or on any
error); only a missing `chat.read` permission raises `PermissionError`. `max_side` is clamped to 128..1280,
`timeout_s` to 1..60 (the budget for downloads). Result:

| key | meaning |
| --- | --- |
| `type` | `photo`, `video`, `gif`, `sticker`, `animated_sticker` (tgs/webm), `voice`, `audio`, `document`, `other` |
| `caption` | message text (str) |
| `emoji`, `set_title` | stickers: emoji and set title (title only if the set is cached), else `""` |
| `mime`, `duration` (s, 0 if n/a), `width`, `height` | document/photo metadata |
| `image_b64` | JPEG, longest side <= `max_side`, quality ~75, base64 **without** `data:` prefix, <= 400 KB; `None` if no image |
| `image_kind` | `photo` (real image), `thumb` (server thumbnail / stripped preview), `frame` (middle frame of an already downloaded video/gif < 20 MB), `sticker` (static webp on white), `None` |

Rules: photos download the smallest size >= `max_side` (and <= 1280) if not cached, falling back to the stripped
preview (`thumb`). Videos/gifs are never downloaded: a middle frame is taken only from a file that is already local
(< 20 MB), otherwise the cached/small thumbnail is used. Static stickers are downloaded (tiny); animated stickers
return only `emoji` + `set_title`. Secret chats return metadata without an image. Downloading does not mark the chat
as read and sends no read receipts (ghost mode is untouched).

**`ai_complete(images=[b64, ...])`**: optional list of base64 JPEG strings (a `data:image/jpeg;base64,` prefix is
tolerated), at most 4 and ~1.6 MB of base64 in total (else `ValueError`). The images are attached to the LAST `user`
message, whose `content` becomes `[{"type":"text","text":...}, {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."}}]`
(OpenAI vision format; the configured model/server must support it). Without `images` the behaviour is unchanged.

```python
def work():
    m = client.get_message_media(dialog_id, msg_id)
    imgs = [m["image_b64"]] if m and m["image_b64"] else []
    hint = m and m["type"] in ("sticker", "animated_sticker") and (m["emoji"] + " " + m["set_title"])
    return client.ai_complete([{"role": "user", "content": "What is in this picture? " + (hint or "")}], images=imgs)
client.run_in_bg(work)
```

## 13. Voice messages: `get_voice`, `ai_transcribe` (0.1.5)

```
client.get_voice(dialog_id, message_id, account=None, timeout_s=30, max_seconds=300) -> dict | None   # chat.read
client.ai_transcribe(audio_b64, mime='audio/ogg', language=None) -> str                                # ai.complete
```

Both are blocking: worker thread only (`client.run_in_bg`).

**`get_voice`** returns `None` when the message is not found or on an internal failure. Otherwise a dict:

* voice / audio: `{type: 'voice'|'audio', is_voice: bool, duration: int (s), mime, size: int (bytes), audio_b64}`;
  `audio_b64` is the original file (normally OGG/Opus), base64 without a `data:` prefix.
* limits: more than 2.5 MB or longer than `max_seconds` gives `{'error': 'too_big'}` / `{'error': 'too_long'}`;
  a download not finished within `timeout_s` (1..120) gives `{'error': 'download_failed'}`. Other errors:
  `not_audio` (no voice/audio in the message), `secret` (secret chat, never fetched).
* round video ("circle"): no audio is extracted; the result has the `get_message_media` shape with
  `type: 'round_video'`, `is_voice: false` and a frame/thumb in `image_b64`.

The file is downloaded through the normal file loader; this does not mark the message as read or listened and sends
no read receipts. Telegram's own Premium transcription is not used.

**`ai_transcribe`** sends a multipart POST (`file`, `response_format=json`, optional `language`) to
`{server}/v1/audio/transcriptions` with the user's AI token (same server, HTML detection, retries and error mapping
as `ai_complete`; the token is never exposed). Audio is limited to ~3 MB. Returns the transcript (JSON field `text`)
or raises `AiError` (`.code` as in `ai_complete`; an empty transcript is an error); `PermissionError` without `ai.complete`.

```python
def work():
    v = client.get_voice(dialog_id, msg_id)
    if v and v.get("audio_b64"):
        return client.ai_transcribe(v["audio_b64"], v["mime"] or "audio/ogg")
client.run_in_bg(work)
```


## 14. AI auto-reply 0.3.8: per-chat media consent

In the plugin settings expand a chat row to opt in separately to **See media** and
**Transcribe voice messages**. These are `see_media_<sk>` and `transcribe_voice_<sk>`,
where `<sk>` is the existing account/dialog settings suffix. Both default to false;
the former global `see_media` switch never grants consent to a chat.

Only incoming attachment IDs in the current reply batch are fetched, with its explicit
account and dialog. Up to two small images/frames are passed via `ai_complete(images=...)`.
Voice audio is sent only with that chat's voice consent. Unsupported/403 transcription
is recorded as `voice_transcription_unavailable`, leaves the chat enabled, and never
creates an imaginary transcript. The currently configured gateway's Whisper route
returned 403 during the external audit; recognition still needs server/provider access.
The server may translate provider access errors to 503; the plugin treats those equally
as transcription unavailable, without changing the user's auth token.

Settings changes and unload invalidate in-flight media work. Consent is rechecked after
each blocking call, before retries and before delivery. Old SDK compatibility for sends
and drafts is allowed only when the intended account is currently selected.

### Actual typing/read helpers in app 0.1.5

`client.set_typing(dialog_id, account=None, cancel=False)` (`send_typing` alias) and
`client.mark_read(dialog_id, max_id, account=None)` (`read_history` alias) require
`network.requests` and return whether a Telegram request was queued. Ghost-suppressed,
secret or unknown dialogs return false; `mark_read` also requires a positive message ID.
Channel read requests are supported. The auto-reply plugin prefers these helpers and
retains its older-app fallback.


## 15. AI auto-reply 0.3.9: context size and answer detail

Plugin settings now expose `context_n` (default 40, range 1-100) and `context_chars`
(default 16000, range 2000-48000). The app's `get_recent_messages` API returns at most
100 cached messages; this is a recent local context window, not unlimited history or
model training. The plugin filters rows by dialog/account, preserves chronological
order and speaker roles, de-duplicates history IDs, and gives current question parts
priority before older history. If a single current message exceeds the budget, its
start and end remain with an explicit `[context trimmed]` marker. The character budget
covers conversation messages; system instructions, style samples and separately
retrieved memory have their own limits.

`answer_detail` is 0 Short, 1 Balanced (default), or 2 Detailed. When `max_reply` is empty,
the respective character limits are 400, 1200 and 3000 (hard maximum 4000). Existing
explicit values are preserved: for example, clear an old saved `max_reply=300` to use
the new detail-dependent default. This changes how much useful explanation the prompt
requests; it does not promise factual knowledge missing from the selected context.

Style learning reads only the current account/chat by default. `style_share=false`
is the default; setting it to true permits examples from other enabled chats of the
same account, never another account. The shared examples are labelled STYLE ONLY and
must not be treated as facts about the current conversation. `learn_n` allows 5-100
samples, with at most 24 examples of up to 200 characters included in the system prompt.


## 16. Local chat memory (ai_autoreply 0.3.9)

The per-chat **Local chat memory** switch (`memory_<account>_<dialog>`) is off by default. Enabling it permits bounded older text from that exact chat to be sent to the configured AI service for summarization. Only compact summaries are persisted under the plugin's private `data_dir/memory/<Telegram-owner-id>/`; no full message archive or media/audio is duplicated. SQLite is already bundled with app 0.1.5.

The most recent 12 messages and current questions remain ordinary conversation context. At least 10 eligible older messages are required for a new summary; only 100 recent local-history rows are examined, so this does not import a chat's entire archive. Summary input is bounded to 16000 characters, stored summaries to 6000 characters, and the append-only database to 16 MiB / 4096 revisions per chat. Reaching a storage limit stops new memory writes, while ordinary replies continue. Files and old revisions are never deleted by this feature.

Owner identity, account slot, dialog, consent and task epoch are checked before and after model calls and before the optimistic write. Service/secret/forwarded messages are excluded. Summaries are explicitly marked as potentially incomplete, untrusted background; the latest conversation takes precedence. Turning memory off stops its use and updates without deleting saved files.

## 17. Mandatory sticker-only replies (ai_autoreply 0.3.9)

For an enabled auto-reply chat, a current incoming batch consisting only of genuine Telegram stickers uses a dedicated path without text generation. The ordinary sticker chance, including 0%, does not suppress this route. A recent sticker is preferred; when unavailable the original incoming document is queued using Telegram's native `SendMessagesHelper` outbox. No image upload, transcription or AI text is needed for this path.

Mixed text/sticker batches keep the normal reply behavior. Explicit draft or command-only mode, master-off/disabled chats, account/epoch cancellation and anti-loop/rate guards remain effective. The rule guarantees deterministic selection/attempt rather than a probabilistic 12% gate; connectivity, Telegram permissions and a valid document reference still determine actual delivery. Failures are logged rather than replaced by text. This has unit/mock coverage; actual device testing is still required.

### Upgrade settings

The context defaults are 40 messages / 16000 characters; up to 100 messages are supported by app 0.1.5. Answer detail is Short / Balanced / Detailed, with default character budgets 400 / 1200 / 3000. Previously explicitly saved `context_n` and `max_reply` values remain in force: increase a saved context of 10 manually, and clear a saved reply limit of 300 to use the chosen detail mode's default. Local memory must be enabled separately for each chat.

## 18. Diagnostic report (ai_autoreply 0.4.4)

For "where did the bot stall" questions the owner can copy one text report of the **last hour** and send it to the
developer: the button **Copy report (last hour)** in the "Recent decisions" group, or the in-chat command **`.ai log`**
(also `.ai лог`, `.ai журнал`, `.ai report`, `.ai звіт`, `.ai отчет`), which like the other admin commands is never sent
and works in any chat. The report is collected in `client.run_in_bg` (history reads), put into the clipboard with
`client.copy_to_clipboard` and confirmed with a bulletin (characters, entries); it is not stored anywhere.

Content, at most 15 000 characters (the oldest timeline lines are dropped first; header, summary and state snapshots
always stay):
- header: plugin version, local time + unix time, interface language, preset, master, the effective key settings
  (preset values for empty fields), number of listed / enabled chats, log size, AI calls in the hour;
- summary: counts of outcome and outcome/reason in the hour, incoming -> bot reply time (avg / max, from history),
  suspicious pauses (an incoming message followed by no message and no decision for more than 10 minutes in an enabled
  chat while master is on; Friend-mode chats are not checked);
- up to 12 chats (those with decisions in the hour, newest first, then enabled chats with live state or incoming
  history): key `<account>:<dialog_id>`, type, mode, enabled, fails, auto-off; the in-memory state (pending, timer,
  inflight, sending, revive/learn busy, retries, defers, seconds since last incoming / reply / owner / bot send,
  cooldown left); flags `!! STUCK FLAG?` (a busy flag with no decision, incoming or send for 5 minutes),
  `!! PENDING WITHOUT TIMER`, `!! AUTO-DISABLED`; and a merged timeline of the hour: decisions (code + plain text in
  the owner's language) and the last 15 history rows as time, direction (`in`, `out-bot`, `out-owner`, `out-?` for an
  outgoing row without text that cannot be attributed), length in characters, type (`text`, `media`, `text+media`,
  `sticker` when known) and message id. A failing history read prints `history unavailable (<error type>)`.

The report never contains message texts, chat titles, names, usernames or phone numbers.
