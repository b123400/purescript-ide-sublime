# purescript-ide-sublime

This sublime text plugin integrates `psc-ide`.

- Autocomplete + auto import
- Hover to show type info
- Save to rebuild file, and error report
- Auto fix warning when possible

- Sublime Text 3 only
- Detect `purs` from PATH

## Settings

```
{
  "enable_debug_log": true,

  // Expecting an absolute path, or use `null` to use shell's PATH
  "purs_path": null,

  // timeout in second, null means no timeout
  "auto_complete_timeout": null,

  // Servers that are already running will not change port
  // when you modify this setting. Restart if you need.
  "port_starts_from": 4242
}
```
