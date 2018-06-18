import sublime
import sublime_plugin
import os
from functools import wraps


def first_starts_with(arr, element):
    for x in arr:
        if element.startswith(x):
            return x
    return None


def is_in_module_word(char):
    if "a" <= char <= "z" or "A" <= char <= "Z" or "0" < char < "9" or char == ".":
        return True
    return False

def is_operator(string):
    for char in string:
        if "a" <= char <= "z" or "A" <= char <= "Z" or "0" < char < "9":
            return False
    return True

def module_word(view, point):
    region = view.word(point)
    space_count = 0
    view_word = view.substr(region)
    if is_operator(view_word):
        return (None, view_word)
    for c in view_word:
        if c == ' ':
            space_count += 1
        else:
            break
    begin = region.begin() + space_count - 1

    while True:
        if begin < 0:
            begin = 0
            break
        this_char = view.substr(sublime.Region(begin, begin+1))
        if not is_in_module_word(this_char):
            begin += 1
            break
        begin -= 1
    module_word = view.substr(sublime.Region(begin, region.end()))
    parts = module_word.split(".")
    last = parts.pop().replace('\n', '')
    module = None
    if len(parts) > 0:
        module = ".".join(parts)
    if module == '':
        module = None
    return (module, last)


project_path_cache = {}
def find_project_dir(view):
    file_path = view.file_name()
    if file_path is None:
        return None
    if view.window() is None:
        return None

    folders = [x + os.sep for x in view.window().folders()]
    project_folder = first_starts_with(folders, file_path)
    if project_folder is None:
        return None

    target_folder = project_folder
    current_paths = file_path.split(os.sep)[:-1]
    while os.sep.join(current_paths).startswith(project_folder):
        current_path = os.sep.join(current_paths)
        files = os.listdir(current_path)
        if ("psc-package.json" in files) or ("package.json" in files):
            target_folder = current_path
            break
        current_paths = current_paths[:-1]

    if file_path in project_path_cache:
        return project_path_cache[file_path]

    project_path_cache[file_path] = target_folder
    return target_folder


def ignore_non_purescript(f):
    @wraps(f)
    def wrapped(self, view, *args, **kwds):
        syntax = view.settings().get('syntax')
        if syntax is None:
            return
        if 'purescript' not in syntax:
            return
        return f(self, view, *args, **kwds)
    return wrapped


class PurescriptViewEventListener(sublime_plugin.ViewEventListener):

    # We need this to fix infinity recursion :(
    def __init__(self, *args, **kwargs):
        super(PurescriptViewEventListener, self).__init__(*args, **kwargs)

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        if syntax is None:
            return
        if 'purescript' not in syntax:
            return False
        return True

