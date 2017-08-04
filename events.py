import sublime
import sublime_plugin

import os

from .command import start_server, stop_server

def is_project_dir(path):
    return os.path.isfile(os.path.join(path, 'package.json'))

def find_project_dir(file_path):
    this_path = file_path
    while True:
        parent = os.path.dirname(this_path)
        if is_project_dir(parent):
            return parent
        if parent == this_path:
            return None
        else:
            this_path = parent

class ExampleCommand(sublime_plugin.TextCommand):
  def run(self, edit):
    self.view.insert(edit, 0, 'Hello, World!')

class EventListener(sublime_plugin.EventListener):
    def on_load(self, view):
        file_name = view.file_name()
        if file_name is None:
            return

        syntax = view.settings().get('syntax')
        if 'purescript' not in syntax:
            return

        project_dir = find_project_dir(file_name)
        if project_dir is None:
            return

        start_server(project_dir)

    def on_pre_close(self, view):
        if view.file_name() is None:
            return

        all_views = [view for win in sublime.windows() for view in win.views()]
        all_project_paths = [find_project_dir(v.file_name()) for v in all_views]
        all_project_paths = [p for p in all_project_paths if p is not None]
        all_project_paths = list(set(all_project_paths))
        this_project_path = find_project_dir(view.file_name())

        if this_project_path in all_project_paths:
            print('Closing purs server for path:', this_project_path)
            stop_server(this_project_path)
