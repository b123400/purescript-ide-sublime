import os
import subprocess
import threading
import json
import time
from .settings import get_settings


def log(*args):
    if get_settings('enable_debug_log'):
        print(*args)


path_cache = None
def guess_path():
    global path_cache
    if path_cache is None:
        try:
            shell = os.environ['SHELL']
            if shell.endswith('zsh'):
                path_cache = run_command([
                    os.environ['SHELL'],
                    '--login',
                    '--interactive',
                    '-c',
                    'echo " __SUBLIME_PURESCRIPT__$PATH __SUBLIME_PURESCRIPT__"'
                    ],
                    path=os.environ['PATH'])[1].split(' __SUBLIME_PURESCRIPT__')[1]
            else:
                # normal bash
                path_cache = run_command([
                    os.environ['SHELL'],
                    '--login',
                    '-c',
                    'echo " __SUBLIME_PURESCRIPT__$PATH __SUBLIME_PURESCRIPT__"'
                    ],
                    path=os.environ['PATH'])[1].split(' __SUBLIME_PURESCRIPT__')[1]
        except Exception as e:
            path_cache = os.environ['PATH']+':/usr/local/bin'
    return path_cache


def run_command(commands, stdin_text=None, path=None):
    if path is None:
        env_path = guess_path()
    else:
        env_path = os.environ['PATH']
    new_env = dict(
        os.environ,
        TERM='ansi',
        CLICOLOR='',
        PATH=env_path)
    log('running: ', commands)
    proc = subprocess.Popen(
        commands,
        env=new_env,
        stdin=(None if stdin_text is None else subprocess.PIPE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if stdin_text is not None:
        proc.stdin.write(stdin_text.encode('utf-8'))
        proc.stdin.close()
    result = b''
    exit_int = None
    while True:
        exit_int = proc.poll()
        if exit_int is not None:
            break
        line = proc.stdout.readline() # This blocks until it receives a newline.
        log(line)
        result += line
    # When the subprocess terminates there might be unconsumed output
    # that still needs to be processed.
    result += proc.stdout.read()
    if exit_int != 0:
        log('purescript-ide-sublime error', exit_int, result)
        pass
    return (exit_int, result.decode('utf-8'))


purs_path_cache = None
def get_purs_path():
    global purs_path_cache

    custom_path = get_settings('purs_path', None)
    if custom_path is not None:
        return custom_path

    if not purs_path_cache:
        try:
            num, result = run_command(['which', 'purs'])
            if num != 0:
                raise Exception()
            purs_path_cache = result.replace('\n', '')
        except Exception:
            return None
    return purs_path_cache


# Path: Thread
servers = {}
# Path: [String] (module name)
projects_modules = {}

class Server(threading.Thread):
    def __init__(self, project_path):
        super().__init__()
        self.project_path = project_path
        default_port = get_settings('port_starts_from', 4242)
        self.port = max([s.port for s in servers.values()] + [default_port-1]) + 1

    def run(self):
        servers[self.project_path] = self
        purs_path = get_purs_path()
        if not purs_path:
            return
        exit_int, stdout = run_command([
            purs_path, 'ide', 'server',
            '--directory', self.project_path,
            './**/*.purs',
            '--log-level', 'all',
            '--port', str(self.port)])
        servers.pop(self.project_path, None)


def start_server(project_path, on_message=lambda x:x):
    if project_path in servers:
        log('purs ide server for', project_path, 'is alrady started')
        return

    if get_purs_path() is None:
        on_message('Cannot find purs. See logs.')
        print('Cannot find purs in PATH: '+guess_path())
        print('Please set custom path in purescript-ide.sublime-settings with the key "purs_path"')
        return

    server = Server(project_path)
    server.start()

    def load_all_files():
        retry = 0
        while True:
            time.sleep(0.5)
            return_val = send_client_command(server.port, {"command": "load", "params": {}})
            log(return_val)
            if return_val is not None and return_val[0] == 0:
                on_message(json.loads(return_val[1])['result'])
                break
            retry += 1
            if retry >= 10:
                break
    threading.Thread(target=load_all_files).start()
    on_message('Starting purs ide server at path: ' + project_path)

def stop_server(project_path):
    if project_path not in servers:
        log('Server for path ', project_path, ' is not running')
        return
    return send_quit_command(servers[project_path].port)

def stop_all_servers():
    # Avoid "changing dict size while looping dict" issue
    for project_path in list(servers.keys()):
        stop_server(project_path)

def send_client_command(port, json_obj):
    purs_path = get_purs_path()
    if not purs_path:
        return None
    return run_command([
        purs_path, 'ide', 'client',
        '--port', str(port)],
        stdin_text=json.dumps(json_obj))

def send_quit_command(port):
    return send_client_command(port, {"command":"quit"})

def get_code_complete(project_path, prefix):
    if project_path not in servers:
        log('Server for path ', project_path, ' is not running')
        return
    num, result = send_client_command(
        servers[project_path].port,
        {
            "command":"complete",
            "params":{
                "matcher": {
                    "matcher":"flex",
                    "params":{"search":prefix}
                },
                "options": {
                    "maxResults": 10
                }
            }
        })
    result = json.loads(result)
    if result['resultType'] != 'success':
        return None
    return result['result']


class CodeCompleteThread(threading.Thread):
    def __init__(self, project_path, prefix):
        super().__init__()
        self.project_path = project_path
        self.prefix = prefix
        self.return_val = None

    def run(self):
        self.return_val = get_code_complete(
            self.project_path,
            self.prefix)


def get_module_complete(project_path, prefix):
    if project_path not in servers:
        log('Server for path ', project_path, ' is not running')
        return

    modules = projects_modules.get(project_path, None)

    if modules is None:
        num, result = send_client_command(
        servers[project_path].port,
        {
            "command": "list",
            "params": {
                "type": "availableModules"
            }
        })
        result = json.loads(result)
        if result['resultType'] != 'success':
            return None
        modules = result['result']
        projects_modules[project_path] = modules

    return [m for m in modules if m.lower().startswith(prefix.lower())]


class ModuleCompleteThread(threading.Thread):
    def __init__(self, project_path, prefix):
        super().__init__()
        self.project_path = project_path
        self.prefix = prefix
        self.return_val = None

    def run(self):
        self.return_val = get_module_complete(
            self.project_path,
            self.prefix)


def add_import(project_path, file_path, module, identifier, qualifier=None):
    num, result = send_client_command(
        servers[project_path].port,
        {
            "command": "import",
            "params": {
                "file": file_path,
                "filters": [{
                    "filter": "modules",
                    "params": {
                        "modules": [module]
                    }
                }],
                "importCommand": ({
                    "importCommand": "addImport",
                    "identifier": identifier,
                } if qualifier is None else
                ({
                    "importCommand": "addQualifiedImport",
                    "module": module,
                    "qualifier": qualifier,
                }))
            }
        }
    )
    result = json.loads(result)
    if result['resultType'] != 'success':
        return None
    return result['result']


def get_module_imports(project_path, file_path):
    num, result = send_client_command(
        servers[project_path].port,
        {
            "command": "list",
            "params": {
                "file": file_path,
                "type": "import"
            }
        }
    )
    result = json.loads(result)
    if result['resultType'] != 'success':
        return None
    return result['result']


def get_type(project_path, module_name, identifier, imported_modules=[]):
    filters = []
    if len(imported_modules) > 0:
        filters.append({
           "filter": "modules",
           "params": {
             "modules": imported_modules
           }
        })

    num, result = send_client_command(
        servers[project_path].port,
        {
            "command": "type",
            "params": {
                "search": identifier,
                "filters": filters,
                "currentModule": module_name
            }
        }
    )
    result = json.loads(result)
    if result['resultType'] != 'success':
        return None
    return result['result']


def rebuild(project_path, file_path):
    num, result = send_client_command(
        servers[project_path].port,
        {
          "command": "rebuild",
          "params": {
            "file": file_path
          }
        }
    )
    result = json.loads(result)
    # Clean modules cache for auto complete
    projects_modules.pop(project_path, None)
    return result['result']


def plugin_unloaded():
    stop_all_servers()
