import sublime
import sublime_plugin

import os

from .command import start_server

def is_project_dir(path):
    return os.path.isfile(os.path.join(path, 'package.json'))

class ExampleCommand(sublime_plugin.TextCommand):
  def run(self, edit):
    self.view.insert(edit, 0, 'Hello, World!')

class EventListener(sublime_plugin.EventListener):
    def on_load(self, view):
        filename = view.file_name()
        if filename is None:
            return

        syntax = view.settings().get('syntax')
        if 'purescript' not in syntax:
            return

        project_dir = None
        this_path = filename
        while True:
            parent = os.path.dirname(this_path)
            if is_project_dir(parent):
                project_dir = parent
                break
            if parent == this_path:
                # root reached
                break
            else:
                this_path = parent

        if project_dir is None:
            return

        start_server(project_dir)
