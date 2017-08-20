import sublime

SETTINGS_FILE = 'purescript-ide-sublime.sublime-settings'
settings = None

def plugin_loaded():
    global settings
    settings = sublime.load_settings(SETTINGS_FILE)

def get_settings(*args):
    return settings.get(*args)

def add_on_change(*args):
    return settings.add_on_change(*args)

def clear_on_change(*args):
    return settings.clear_on_change(*args)
