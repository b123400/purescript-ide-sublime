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
        self.phantom_sets = [] # [(view, phantomset)]

    @ignore_non_purescript
    def on_post_save_async(self, view):
        file_name = view.file_name()
        if file_name is None:
            return
        project_path = find_project_dir(view)
        errors = rebuild(project_path, file_name)

        regions_and_errors = []
        regions = []
        error_without_position = []
        for error in errors:
            # it's possible to have error with no position like this
            #
            # {'suggestion': None,
            # 'position': None,
            # 'errorCode': 'UnusableDeclaration',
            # 'moduleName': 'Localization.Smolder',
            # 'errorLink': 'https://github.com/purescript/documentation/blob/master/errors/UnusableDeclaration.md',
            # 'message': "  The declaration withEvent is unusable.\n  This happens when a constraint couldn't possibly have enough information to work out which instance is required.\n",
            # 'filename': None
            # }
            if error['position'] is None:
                print(error)
                error_without_position.append(error)
                continue
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
            "warning",

            sublime.DRAW_NO_FILL |
            sublime.DRAW_NO_OUTLINE |
            sublime.DRAW_SQUIGGLY_UNDERLINE
            )

        ps = sublime.PhantomSet(view)

        ps.update([sublime.Phantom(
                    view.sel()[0],
                    "".join(['<p>%s</p>' % s.replace(' ', '&nbsp;')
                        for s in error['message']
                            .split('\n')]),
                    sublime.LAYOUT_BLOCK) for error in error_without_position])

        self.delete_phantom_in_view(view)
        self.phantom_sets.append((view, ps))

    @ignore_non_purescript
    def on_close(self, view):
        self.delete_phantom_in_view(view)

    def delete_phantom_in_view(self, view):
        i = 0
        index = None
        for (v, _) in self.phantom_sets:
            if v == view:
                index = i
            i += 1
        if index is not None:
            del self.phantom_sets[index]
