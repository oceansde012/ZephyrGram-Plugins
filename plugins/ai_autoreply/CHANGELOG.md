# Changelog

## 0.2.0
- Settings: 'Add chat' section with a chat-list picker and @username / t.me link input (needs an app with `DialogPicker` / `UsernameInput`; older apps keep the chat header menu).
- Friend mode (command mode): the other person triggers the AI with `.ai ` while you stay silent; documented in settings.
- Per-chat list with mode, prompt, enabled switch and Remove chat.

## 0.1.0
- Initial release: per-chat allowlist via the chat header menu, auto / draft / command modes, per-chat prompts, cooldown, daily and hourly caps, loop protection, 3 s debounce.
- Icon: optional; ship a PNG (64 KB max) as `icon.png` next to the plugin, a robot or chat bubble with a spark works well.
