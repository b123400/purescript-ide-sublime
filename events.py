import sublime
import sublime_plugin
import tempfile
import os

from .command import start_server, stop_server, CodeCompleteThread

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

class StartServerEventListener(sublime_plugin.EventListener):
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

        def callback(message):
            view.window().status_message(message)

        start_server(project_dir, callback=callback)
        view.window().status_message('Starting purs ide server')

    def on_pre_close(self, view):
        if view.file_name() is None:
            return

        this_project_path = find_project_dir(view.file_name())

        def perform():
            all_views = [view for win in sublime.windows() for view in win.views()]
            all_project_paths = [find_project_dir(v.file_name()) for v in all_views]
            all_project_paths = [p for p in all_project_paths if p is not None]
            all_project_paths = list(set(all_project_paths))

            if this_project_path not in all_project_paths:
                print('Closing purs server for path:', this_project_path)
                stop_server(this_project_path)

        # delay server closing for 0.5s, because we may be "switching" between files
        sublime.set_timeout(perform, 500)


class CompletionEventListener(sublime_plugin.EventListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_completion_results = None

    def on_query_completions(self, view, prefix, locations):
        syntax = view.settings().get('syntax')
        if 'purescript' not in syntax:
            return

        # print('query', prefix, locations)
        # print('scope', view.scope_name(locations[0]))

        if view.file_name() is None:
            return

        project_path = find_project_dir(view.file_name())

        this_thread = CodeCompleteThread(project_path, prefix)
        this_thread.start()
        this_thread.join(timeout=None)

        self.last_completion_results = {}
        completions = []
        for r in this_thread.return_val:
            str_to_display = r['identifier']+'\t'+r['type']
            if str_to_display in self.last_completion_results:
                continue
            self.last_completion_results[str_to_display] = r
            completions.append([str_to_display, r['identifier']])
        return completions
