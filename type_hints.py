import sublime
import sublime_plugin
import webbrowser

from .command import ( get_module_imports
                     , get_type )
from .utility import ( find_project_dir
                     , PurescriptViewEventListener
                     )
from .error import error_manager


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

        error_link = error.get('errorLink', None)
        if error_link is not None:
            before_error_link = handle_nav
            error_message = error_message + '<p><a href="error_link">More Info</a></p>'
            def open_error_link(href):
                if href != 'error_link':
                    before_error_link()
                    return
                webbrowser.open_new_tab(error_link)
            handle_nav = open_error_link

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
        project_path = find_project_dir(view)
        module_info = get_module_imports(project_path, view.file_name())
        word = view.substr(view.word(point))
        type_info = get_type(
            project_path,
            module_info['moduleName'],
            word,
            [m['module'] for m in module_info['imports']]
        )
        if len(type_info) == 0:
            return

        first_result = type_info[0]

        def on_navigate(string):
            view.window().open_file(string, sublime.ENCODED_POSITION)

        #file_path:row:col
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
