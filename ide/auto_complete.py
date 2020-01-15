import sublime
import sublime_plugin
import time
import tempfile
import os
import webbrowser
from functools import wraps

from .command import ( CodeCompleteThread
                     , ModuleCompleteThread
                     , add_import
                     , log
                     , get_module_imports)
from .utility import ( find_project_dir
                     , PurescriptViewEventListener
                     , module_word
                     )
from .settings import get_settings


class CompletionEventListener(PurescriptViewEventListener):
    def __init__(self, *args, **kwargs):
        super(CompletionEventListener, self).__init__(*args, **kwargs)
        self.last_completion_results = None
        self.last_completions = None
        self.current_completion_prefix = None

        # Make autocomplete shows after "."
        auto = self.view.settings().get('auto_complete_triggers')
        auto.append({"selector": "source.purescript", "characters": "."})
        self.view.settings().set('auto_complete_triggers', auto)


    def on_query_completions(self, prefix, locations):
        view = self.view
        if view.file_name() is None:
            return
        if not get_settings('enable_auto_complete', True):
            return

        line_str = view.substr(view.line(view.sel()[0]))
        if line_str.startswith('import '):
            # module complete
            return self.get_completion_for_import(prefix, locations)
        else:
            return self.get_completion_for_identifier(prefix, locations)

    def get_completion_for_import(self, prefix, locations):
        view = self.view
        project_path = find_project_dir(view)

        module_prefix, identifier = module_word(view, locations[0])
        if module_prefix is None:
            full_module_prefix = identifier
        else:
            full_module_prefix = module_prefix + '.' + identifier

        this_thread = ModuleCompleteThread(project_path, full_module_prefix)
        this_thread.start()

        timeout = get_settings('auto_complete_timeout', None)
        this_thread.join(timeout=timeout)

        if this_thread.return_val is None:
            log('autocomplete probably timeout')
            return

        self.last_completion_results = {}
        self.last_completions = []

        for m in this_thread.return_val:
            completion = m if module_prefix is None else m.strip(module_prefix + '.')
            self.last_completions.append([completion, completion])
        return self.last_completions

    def get_completion_for_identifier(self, prefix, locations):
        view = self.view
        project_path = find_project_dir(view)
        module_alias, _ = module_word(view, locations[0])

        if self.current_completion_prefix != prefix:
            self.current_completion_prefix = prefix
            self.last_completion_results = {}
            self.last_completions = []
            def callback(_prefix, result):
                if _prefix != self.current_completion_prefix:
                    # We have new input so this result is discarded
                    return
                for r in result:
                    str_to_display = r['identifier']+'\t'+r['module']+'\t'+r['type']

                    # Remove completely duplicated entry
                    if str_to_display in self.last_completion_results:
                        continue

                    # module alias for qualified import
                    r['module_alias'] = module_alias
                    # In order to know which completion the user selected
                    # we have to save all completions, and catch the completion
                    # event in on_modified_async
                    self.last_completion_results[str_to_display] = r
                    self.last_completions.append([str_to_display, r['identifier']])

            this_thread = CodeCompleteThread(project_path, prefix, callback)
            this_thread.start()

            return []

        else:
            return self.last_completions

    def on_modified_async(self):
        # Import the module after the user selected the auto complete
        view = self.view
        command, detail, _ = view.command_history(0, True)
        if command != 'insert_completion':
            return
        if self.last_completion_results is None:
            return
        completion = self.last_completion_results.get(detail['completion'], None)
        if completion is None:
            return

        project_path = find_project_dir(view)

        if completion.get('module_alias') is not None:
            file_imports = get_module_imports(project_path, view.file_name())['imports']
            is_alias_exist = any([a.get('qualifier') == completion['module_alias'] for a in file_imports])
            if is_alias_exist:
                return

        file_text = view.substr(sublime.Region(0, view.size()))

        # TODO, also import the types

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
            completion['identifier'],
            qualifier=completion['module_alias'])
        os.unlink(temp_file.name)

        view.run_command('replace', {'text': '\n'.join(result)})

        pos = view.word(view.sel()[0]).end()
        view.sel().clear()
        view.sel().add(sublime.Region(pos))

        # Prevent replace again when pressed undo
        self.last_completion_results = None
