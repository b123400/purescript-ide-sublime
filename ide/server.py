import sublime
import sublime_plugin

from .command import ( start_server
                     , stop_server
                     )
from .utility import ( find_project_dir
                     , ignore_non_purescript
                     )


class StartServerEventListener(sublime_plugin.EventListener):

    @ignore_non_purescript
    def on_load(self, view):
        file_name = view.file_name()
        if file_name is None:
            return

        project_dir = find_project_dir(view)
        if project_dir is None:
            return
        self.start_server(view, project_dir)

    @ignore_non_purescript
    def on_activated(self, view):
        # It is possible that a view does not have window
        # (When user's choosing files from the command-p menu)
        # so here I try to catch use the activate event to start server
        file_name = view.file_name()
        if file_name is None:
            return

        project_dir = find_project_dir(view)
        if project_dir is None:
            return
        self.start_server(view, project_dir)

    def start_server(self, view, project_dir):
        window = view.window()
        def callback(message):
            window.status_message(message)
        start_server(project_dir, on_message=callback)

    @ignore_non_purescript
    def on_pre_close(self, view):
        if view.file_name() is None:
            return

        window = view.window()
        this_project_path = find_project_dir(view)

        def perform():
            all_views = [view for win in sublime.windows() for view in win.views() if view.file_name() is not None]
            purs_views = [v for v in all_views if v.file_name().endswith(".purs")]
            all_project_paths = [find_project_dir(v) for v in purs_views]
            all_project_paths = [p for p in all_project_paths if p is not None]
            all_project_paths = list(set(all_project_paths))

            if this_project_path not in all_project_paths:
                stop_server(this_project_path)
                window.status_message('Closed server for path:' + this_project_path)

        # delay server closing for 0.5s, because we may be "switching" between files
        sublime.set_timeout(perform, 500)
