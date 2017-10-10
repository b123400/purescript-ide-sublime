import sublime
import sublime_plugin
import time
import tempfile
import os
import webbrowser
from functools import wraps

from .command import CodeCompleteThread, add_import, log
from .utility import ( find_project_dir
                     , PurescriptViewEventListener
                     , module_word
                     )
from .settings import get_settings


class CompletionEventListener(PurescriptViewEventListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_completion_results = None

    def on_query_completions(self, prefix, locations):
        view = self.view
        if view.file_name() is None:
            return

        project_path = find_project_dir(view)
        module_alias, _ = module_word(view, locations[0])

        this_thread = CodeCompleteThread(project_path, prefix)
        this_thread.start()

        timeout = get_settings('auto_complete_timeout', None)
        this_thread.join(timeout=timeout)

        if this_thread.return_val is None:
            log('autocomplete probably timeout')
            return

        self.last_completion_results = {}
        completions = []

        for r in this_thread.return_val:
            str_to_display = r['identifier']+'\t'+r['type']
            if str_to_display in self.last_completion_results:
                continue
            r['module_alias'] = module_alias
            self.last_completion_results[str_to_display] = r
            completions.append([str_to_display, r['identifier']])
        return completions

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
