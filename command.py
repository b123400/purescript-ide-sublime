import os
import subprocess
import threading
import json

# TODO: find out how to embed purs in plugin
PURS_PATH = '/Users/b123400/.npm-node5/bin/purs'
PURS_IDE_PORT = 45454

def run_command(commands, stdin_text=None):
    new_env = dict(
        os.environ,
        PATH=os.environ['PATH']+':/usr/local/bin')
    print('running: ', commands)
    proc = subprocess.Popen(
        commands,
        env=new_env,
        #shell=True,
        stdin=(None if stdin_text is None else subprocess.PIPE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if stdin_text is not None:
        proc.stdin.write(stdin_text.encode('utf8'))
        proc.stdin.close()
    result = b''
    exit_int = None
    while True:
        exit_int = proc.poll()
        if exit_int is not None:
            break
        line = proc.stdout.readline() # This blocks until it receives a newline.
        print(line)
        result += line
    # When the subprocess terminates there might be unconsumed output
    # that still needs to be processed.
    result += proc.stdout.read()
    return (exit_int, result)

# Path: Thread
servers = {}

class Server(threading.Thread):
    def __init__(self, project_path):
        super().__init__()
        self.project_path = project_path
        self.port = max([s.port for s in servers.values()] + [PURS_IDE_PORT-1]) + 1

    def run(self):
        servers[self.project_path] = self
        exit_int, stdout = run_command([
            PURS_PATH, 'ide', 'server',
            '--directory', self.project_path,
            './**/*.purs',
            '--log-level', 'all',
            '--port', str(self.port)])
        servers.pop(self.project_path, None)

def start_server(project_path):
    if project_path in servers:
        print('purs ide server for', project_path, 'is alrady started')
        return

    Server(project_path).start()
    print('Started purs ide server for path: ', project_path)

def stop_server(project_path):
    # TODO stop server
    if project_path not in servers:
        print('Server for path ', project_path, ' is not running')
        return
    return send_quit_command(servers[project_path].port)

def send_client_command(port, json_obj):
    return run_command([
        PURS_PATH, 'ide', 'client',
        '--port', str(port)],
        stdin_text=json.dumps(json_obj))

def send_quit_command(port):
    return send_client_command(port, {"command":"quit"})
