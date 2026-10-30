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
| `messages.send` | `add_on_send_message_hook`, `client.send_text`, `client.set_draft` |
| `chat.read` | `client.get_recent_messages`, `client.get_dialog_info`, `client.search_dialogs` (cached chat data), `client.resolve_username` (may use the network) |
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
`reply_lang` (int, *new*: `0` Auto by the chat context, `1` Ukrainian, `2` Russian, `3` the other person's
language), `preset` (int: `0` Balanced, `1` Chatty, `2` Quiet), `owner_active` (string, seconds the bot stays
silent after the owner wrote in the chat; empty = preset, Balanced 45), `chat_hourly` (string; empty = preset,
Balanced 20), `ui_lang` (int: `0` auto, `1` uk, `2` ru, `3` en).

**`decisions`** (string, JSON array, at most 20, oldest first, no message text):
`{"t": <unix seconds>, "chat": "<account>:<dialog_id>", "o": "<outcome>", "r": "<reason code>"}`.
`o` is one of `sent`, `draft`, `skip`, `error`, `disabled`, `resume`, `test`, and (*new*) `seen`
(reason `incoming_seen`: a message from the other person reached the plugin; consecutive ones of a chat are
collapsed into one entry) and `cmd` (in-chat commands: `admin_on`, `admin_off`, `admin_status`, `admin_list`,
`admin_mode_auto|draft|friend`, `admin_refused`, `menu_on`, `menu_off`). The last real decision of a chat is the
newest entry of that chat whose `o` is not `seen` or `cmd`.

To list active chats: parse `chats`, keep entries with `enabled == true`, show `title`, mode from `mode_<sk>`.
To add or remove a chat from the core side, write the same JSON back (keep unknown fields) and set `mode_<sk>`
to `0` for a new chat. Since 0.3.5 the plugin re-reads `chats` (and drops its reply-language cache) when it receives
the app event `settings_changed` (see section 3), so after a core-side edit call
`PluginManager.notifySettingsChanged("ai_autoreply")`. The plugin's own writes are reload-merge-save: it re-reads
`chats`, changes only the one chat field(s) it owns and writes back, so concurrent core edits are not lost. Per-chat
keys (`mode_`, `keep_`, `rlang_`, `prompt_`) and `master` are read from the store on every use and need no reload.

**In-chat owner commands (private chats only, never sent as messages):** `.ai on` (add/enable, mode Auto),
`.ai off` (remove), `.ai status`, `.ai list`, `.ai mode auto|draft|friend`. They are intercepted by the send hook;
the command words (default `.ai`, `.аі`) are the `cmd_triggers` setting and the whole feature is `cmd_enable`.
