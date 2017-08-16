import sublime
import sublime_plugin
import time
import tempfile
import os
from functools import wraps

from .command import ( start_server
                     , stop_server
                     , CodeCompleteThread
                     , add_import
                     , get_module_imports
                     , get_type
                     , rebuild )

from .error import error_manager

def is_project_dir(path):
    return os.path.isfile(os.path.join(path, 'package.json'))

project_path_cache = {}
def find_project_dir(file_path):
    if file_path is None:
        return None
    if file_path in project_path_cache:
        return project_path_cache[file_path]

    this_path = file_path
    while True:
        parent = os.path.dirname(this_path)
        if is_project_dir(parent):
            project_path_cache[file_path] = parent
            return parent
        if parent == this_path:
            return None
        else:
            this_path = parent


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


class StartServerEventListener(sublime_plugin.EventListener):

    @ignore_non_purescript
    def on_load(self, view):
        file_name = view.file_name()
        if file_name is None:
            return

        project_dir = find_project_dir(file_name)
        if project_dir is None:
            return

        def callback(message):
            view.window().status_message(message)

        start_server(project_dir, callback=callback)
        view.window().status_message('Starting purs ide server')

    @ignore_non_purescript
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


class CompletionEventListener(PurescriptViewEventListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_completion_results = None

    def on_query_completions(self, prefix, locations):
        view = self.view
        if view.file_name() is None:
            return

        project_path = find_project_dir(view.file_name())

        this_thread = CodeCompleteThread(project_path, prefix)
        this_thread.start()
        # TODO, read timeout from pref
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

    def on_modified_async(self):
        view = self.view
        command, detail, _ = view.command_history(0, True)
        print(command)
        if command != 'insert_completion':
            return
        if self.last_completion_results is None:
            return
        completion = self.last_completion_results.get(detail['completion'], None)
        if completion is None:
            return

        project_path = find_project_dir(view.file_name())
        file_text = view.substr(sublime.Region(0, view.size()))

        # 1. Save the content of file to somewhere else
        # 2. Use psc-ide to get the new content after auto import
        # 3. Replace the file with the new content
        # 4. Delete temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(file_text.encode('utf-8'))
        temp_file.close()
        result = add_import(
            project_path,
            temp_file.name,
            completion['module'],
            completion['identifier'])
        os.unlink(temp_file.name)

        view.run_command('replace', {'text': '\n'.join(result)})

        # Prevent replace again when pressed undo
        self.last_completion_results = None


class TypeHintEventListener(PurescriptViewEventListener):

    def on_hover(self, point, hover_zone):
        view = self.view
        file_name = view.file_name()
        if file_name is None:
            return

        error = error_manager.get_error_at_point(file_name, point)
        if error:
            self.show_error(view, error, point)
            return
        self.show_type_hint(view, point)

    def show_error(self, view, error, point):
        error_message_lines = error['message'].split('\n')
        error_message = "".join(['<p>%s</p>' % s.replace(' ', '&nbsp;') for s in error_message_lines])

        handle_nav = None
        def default_handle_nav(href):
            pass
        handle_nav = default_handle_nav

        suggestion = error.get('suggestion', None)
        if suggestion is not None:
            before_auto_save = handle_nav
            error_message = '<p><a href="replace">Fix it!</a></p>' + error_message
            def auto_fix(href):
                if href != 'replace':
                    before_auto_save(href)
                    return

                start_point = view.text_point(
                    suggestion['replaceRange']['startLine']-1,
                    suggestion['replaceRange']['startColumn']-1
                )
                end_point = view.text_point(
                    suggestion['replaceRange']['endLine']-1,
                    suggestion['replaceRange']['endColumn']-1
                )

                # if the last char is \n, create one less \n
                replacement = suggestion['replacement']
                if len(replacement) > 0 and replacement[-1] == '\n':
                    replacement = replacement[:-1]

                view.run_command(
                    'replace_region',
                    {
                        'text': replacement,
                        'start': start_point,
                        'end': end_point
                    })

            handle_nav = auto_fix

        view.show_popup(error_message,
            sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            point,
            600,
            600,
            handle_nav)

    def show_type_hint(self, view, point):
        project_path = find_project_dir(view.file_name())
        module_info = get_module_imports(project_path, view.file_name())
        word = view.substr(view.word(point))
        type_info = get_type(
            project_path,
            module_info['moduleName'],
            word
        )
        if len(type_info) == 0:
            return

        first_result = type_info[0]

        def on_navigate(string):
            view.window().open_file(string, sublime.ENCODED_POSITION)

        #filepath:row:col
        link_url = first_result['definedAt']['name'] + ':' + \
            str(first_result['definedAt']['start'][0]) + ':' + \
            str(first_result['definedAt']['start'][1])

        view.show_popup('''
            <p>From: <a href="%s">%s</a> </p>
            <p>Type: %s </p>
        ''' % ( link_url,
                ",".join(first_result['exportedFrom']),
                first_result['type']),
        sublime.HIDE_ON_MOUSE_MOVE_AWAY,
        point,
        500,    # max width
        500,    # max height
        on_navigate)

class RebuildEventListener(sublime_plugin.EventListener):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @ignore_non_purescript
    def on_post_save_async(self, view):
        file_name = view.file_name()
        if file_name is None:
            return
        project_path = find_project_dir(file_name)
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


class ReplaceCommand(sublime_plugin.TextCommand):
    def run(self, edit, text):
        self.view.replace(
            edit,
            sublime.Region(0, self.view.size()),
            text)


class ReplaceRegionCommand(sublime_plugin.TextCommand):
    def run(self, edit, text, start, end):
        self.view.replace(
            edit,
            sublime.Region(start, end),
            text)
