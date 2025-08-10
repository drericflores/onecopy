
### `tests/manual-qa-checklist.md`
```md
# onecopy Manual QA Checklist

## Launch & UI
- [ ] App starts without errors from terminal: `onecopy`
- [ ] Status bar visible; toolbar and menu actions enabled
- [ ] Dark mode toggles and persists across restarts

## File copy
- [ ] Copy a 1GB file to a writable directory – progress advances to 100%
- [ ] Overwrite off: attempt to copy onto an existing file – prompt appears
- [ ] Overwrite on: destination replaced silently
- [ ] Preserve mode: destination permissions match source
- [ ] Verify on: SHA-256 displayed in status bar

## Elevation path
- [ ] Destination requires root (e.g., `/usr/local/share/testfile`)
- [ ] App requests authentication via pkexec
- [ ] Copy succeeds and reports bytes in status bar

## Keyboard shortcuts
- [ ] Ctrl+O, Ctrl+D, Ctrl+C, Ctrl+Shift+D, Ctrl+Q

## Persistence
- [ ] Last source/destination paths remembered after restart