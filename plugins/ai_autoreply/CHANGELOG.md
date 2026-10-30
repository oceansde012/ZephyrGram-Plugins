# Changelog

## 0.3.4
- Settings screen restructured. The first section is 'Chats with the bot': one row per chat (title from the app's dialog info; below it mode, on/off and the last decision). Tap a row to open its options (mode, enabled, prompt, reply language, style test, remove), tap again to close. 'Add chat' (chat picker, @username) is right below; everything advanced (general, modes, command, humanize, prompts and model, limits, style test) follows under headers, and 'Recent decisions' is last.
- New owner commands in a private chat (intercepted, never sent, no need to list the chat first): '.ai on' (add and enable, mode Auto), '.ai off' (remove the chat), '.ai status' (state and last decision), '.ai list' (active chats), '.ai mode auto|draft|friend'. Localized uk/ru/en, written to the decision log; groups, channels, bots and secret chats are refused with a message. The chat header menu item is now 'Bot in this chat: on/off' and toggles the same.
- Fix: the bot did not react to messages of a friend in private chats. Private messages arrive as TL_updateShortMessage / TL_updateShortChatMessage, which never become updateNewMessage; the plugin now also listens to these two updates (same pipeline, de-duplicated per chat and message id, so a message that arrives through both paths is answered once). Every message from the other person in a listed chat is written to the decision log as 'received' (no text), so you can see that the plugin got it.
- More reliable autonomous replies: a chat added by any route starts enabled in mode Auto; Balanced preset: silence after you wrote in the chat 45 s (was 2 min), 20 replies per hour per chat (was 12). A message that comes while you are writing is no longer dropped: the reason 'owner_active' is logged and the bot answers after your silence window (up to 2 retries; if you answered yourself meanwhile, it stays silent).
- Reply language follows the chat: Auto (default) takes the language you write in this chat from the last ~15 messages (your own messages decide, a Ukrainian/Russian mix follows your latest message, Ukrainian when there is no signal), cached 10 minutes per chat, and the prompt now names the language explicitly. New 'Reply language' setting (Auto / Ukrainian / Russian / the other person's language), globally and per chat. Applies to auto-replies, '.ai', '.ai <topic>', '.ai ?' and opening phrases (built-in openers in Ukrainian and Russian, chosen by chat language).
- Storage format is unchanged (new optional keys only: rlang_<sk>, reply_lang, decision outcomes 'seen' and 'cmd'); documented in docs/API.md section 10.

## 0.3.3
- Fix: the '.ai' command did nothing and left no trace. The input field always sets an animation object (and often a link-preview object) on a plain text message, and the plugin treated that as an attachment and silently let the message through. Only real attachments (photo, document, location, poll, game, invoice, contact, to-do, retry, video, rich message) are skipped now.
- Every command attempt is in the decision log with a reason: command_disabled, chat_not_listed (sent as a normal message), command_ignored_media, master_off, owner_command_busy, owner_command_* (topic/continue/opener/draft), ai failed, send failed, command_hook_exception.
- Robustness: if the app did not pass an outgoing '.ai' to the plugin before sending (so it reached the chat), the new-message hook now runs the command anyway (logged as owner_command_hook_missed; the '.ai' message itself stays in the chat, the plugin API has no delete call).
- New chat menu item 'AI: write the next message for me' in chats of the plugin: the same command without typing it.
- No app change needed.

## 0.3.2
- Settings screen readable on the phone: 'Recent decisions' is one entry per decision, newest first (title '21:45:30 · Cherish' with the chat name from the plugin list or the app cache, id as fallback; below it the reason in plain language, shown in full and never cut). 'Copy log (last 20)' puts the last 20 decisions on the clipboard, 'Clear log' empties the list.
- Explanatory rows (Modes, hints, style test result, 'No decisions') are no longer tap-looking buttons that do nothing: they use the non-clickable multi-line block. No app change needed; a cleaner API is proposed in docs/API.md 'Core change requests'.
- Localization: settings, hints, decision reasons, bulletins and the menu are in Ukrainian, Russian and English. New 'Interface language' setting (Auto / Українська / Русский / English). zephyr.client has no app-locale call yet, so Auto uses the phone language when Python can see it (uk/ru) and Ukrainian otherwise.
- New: the bot writes first. Type the command (default '.ai' or '.аі', configurable) in a chat of the plugin: the text is cancelled (never sent) and the plugin starts the conversation in your style. '.ai' alone continues the last day's conversation (answers the last unanswered message or gently raises a topic) or, with no fresh context, sends a short opener (editable list, rephrased by the model when Humanize is on); '.ai <topic>' writes the first message about the topic without inventing facts; '.ai ?' / '.ai draft' puts it into the input field instead. Settings: enable, command words, sends/draft, 'Allow in any private chat' (off by default), opener list. Ignores cooldown and hourly limits; every use is in the decision log; sent texts are remembered as plugin texts (no style learning from them, no loop with the new-message hook).

## 0.3.1
- Fix: the bot could stay silent. After the retry the best cleaned reply is now sent anyway (banned words, AI-tell, wrong language); a reply is skipped only when it is empty, emoji-only or identical to our previous reply. A message without a date is no longer dropped. A chat auto-disabled by repeated errors resumes after 30 minutes. Scheduler/process exceptions are caught and logged, and a stuck debounce timer can no longer block a chat.
- Decision log: every sent/skipped decision (reason code, chat id, time; no message text) goes to log.txt and to the 'Recent decisions' item in settings (last 20).
- Presets (Balanced default / Chatty / Quiet), each field editable (empty = preset): debounce 4-6 s with one answer per batch, 20 s between replies, 12 replies/hour per chat with one polite stop line, plain 'ок/дякую/ага/лол' ignored unless a question follows, silent for 2 minutes after you wrote in the chat, groups only for questions/requests, never answers the same message twice, optional quiet hours.
- Typing delay 0.3 s + 25 ms/char, 0.4-2.5 s in total (cap setting 'Typing delay cap'); split only replies over ~120 characters, into at most 2 messages.
- Human text: shorter, stricter prompt; language rule (language of the last message, Ukrainian by default, never Chinese); built-in banned words list (звісно, безумовно, розумію, дійсно, ... and Russian equivalents) plus your own extra words: a reply with them is regenerated once with an explicit instruction, then sent anyway.
- Test style hardened (no stuck 'already running', clear message when nothing to test).

## 0.3.0
- Humanize (new switch, on by default): replies sound like the owner. Strong anti-AI prompt (no assistant filler like "звісно/розумію/як ШІ", no lists/markdown, no intros or summaries, no question back every time, mirror the other person's language, no invented facts). Your own prompt stays as an extra layer; tone presets Neutral / Friendly / Toxic.
- Learn my style: the last 5-50 own outgoing messages (commands, links, long and plugin-sent texts skipped) go to the prompt as examples, plus measured rules (typical length, lowercase start, final period, emoji, slang/swear words, Ukrainian/Russian mix). Cached per chat (default 30 min); chats with few own messages borrow from other added chats. Examples are sent only to your own AI server.
- Delivery: split into 1-3 short messages, typing delay proportional to length with jitter, skip emoji-only messages, max reply length (default 300).
- Generation: temperature 0.95. `max_tokens` and frequency penalty are not exposed by `client.ai_complete`, so the length is limited by prompt and `max_reply`.
- Post-processing: strips markdown, quotes, `Assistant:` prefixes and filler openers; matches the owner's capitalisation, final period and emoji habits; a reply that repeats the previous one or sounds like an AI is regenerated once, then skipped.
- 'Test style': pick a chat (or use the per-chat item) to see 5 sample replies to the last 5 incoming messages; nothing is sent.
- Humanize off keeps the 0.2.0 behavior.

## 0.2.0
- Settings: 'Add chat' section with a chat-list picker and @username / t.me link input (needs an app with `DialogPicker` / `UsernameInput`; older apps keep the chat header menu).
- Friend mode (command mode): the other person triggers the AI with `.ai ` while you stay silent; documented in settings.
- Per-chat list with mode, prompt, enabled switch and Remove chat.

## 0.1.0
- Initial release: per-chat allowlist via the chat header menu, auto / draft / command modes, per-chat prompts, cooldown, daily and hourly caps, loop protection, 3 s debounce.
- Icon: optional; ship a PNG (64 KB max) as `icon.png` next to the plugin, a robot or chat bubble with a spark works well.
