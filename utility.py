import sublime
import sublime_plugin
import os
from functools import wraps


def first_starts_with(arr, element):
    for x in arr:
        if element.startswith(x):
            return x
    return None


project_path_cache = {}
def find_project_dir(view):
    file_path = view.file_name()
    if file_path is None:
        return None
    if view.window() is None:
        return None

    folders = [x + os.sep for x in view.window().folders()]
    folder = first_starts_with(folders, file_path)
    if folder is None:
        return None

    if file_path in project_path_cache:
        return project_path_cache[file_path]

    project_path_cache[file_path] = folder
    return folder


def ignore_non_purescript(f):
    @wraps(f)
    def wrapped(self, view, *args, **kwds):
        syntax = view.settings().get('syntax')
        if 'purescript' not in syntax:
            return
        return f(self, view, *args, **kwds)
    return wrapped


class PurescriptViewEventListener(sublime_plugin.ViewEventListener):

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        if 'purescript' not in syntax:
            return False
        return True

