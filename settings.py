import sublime

SETTINGS_FILE = 'purescript-ide.sublime-settings'
SETTING_KEYS = ['enable_debug_log', 'purs_path', 'port_starts_from', 'auto_complete_timeout']
settings = {}

def plugin_loaded():
    update_settings()
    raw_setting = sublime.load_settings(SETTINGS_FILE)
    for key in SETTING_KEYS:
        raw_setting.add_on_change(key, update_settings)

# Here is the shit, sublime text's doc claims all APIs
# are thread safe, expect it's not. Setting API is not thread safe
# and will hang when accessed from another thread.
# So here is the code to clone the setting into a python dict.
def update_settings():
    global settings
    raw_setting = sublime.load_settings(SETTINGS_FILE)
    for key in SETTING_KEYS:
        settings[key] = raw_setting.get(key)

def get_settings(key, default=None):
    val = settings.get(key, None)
    if val is not None:
      return val
    return default
