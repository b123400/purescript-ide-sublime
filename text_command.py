import sublime
import sublime_plugin

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
