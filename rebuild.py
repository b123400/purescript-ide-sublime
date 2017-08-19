import sublime
import sublime_plugin
from .command import rebuild
from .error import error_manager

from .utility import ( find_project_dir
                     , ignore_non_purescript
                     )

class RebuildEventListener(sublime_plugin.EventListener):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @ignore_non_purescript
    def on_post_save_async(self, view):
        file_name = view.file_name()
        if file_name is None:
            return
        project_path = find_project_dir(view)
        errors = rebuild(project_path, file_name)

        regions_and_errors = []
        regions = []
        for error in errors:
            start = view.text_point(
                error['position']['startLine']-1,
                error['position']['startColumn']-1
            )
            end = view.text_point(
                error['position']['endLine']-1,
                error['position']['endColumn']-1
            )
            region = sublime.Region(start, end+1)

            if region.size() <= 1:
                # try to make the region bigger because
                # zero width region is invisible
                region = view.word(start)

            regions_and_errors.append((region, error))
            regions.append(region)

        # The actual "hover -> show popup" effect is handled in text_hints.py
        error_manager.set_errors(file_name, regions_and_errors)
        view.add_regions("errors", regions,
            "invalid.illegal",

            # This thing does not exist in doc, but it exists in the default theme.
            # It might break some days
            "light_x_bright",

            sublime.DRAW_NO_FILL |
            sublime.DRAW_NO_OUTLINE |
            sublime.DRAW_SQUIGGLY_UNDERLINE
            )
