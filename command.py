import os
import subprocess
import threading
import json
import time

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
        proc.stdin.write(stdin_text.encode('utf-8'))
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

def start_server(project_path, callback=None):
    if project_path in servers:
        print('purs ide server for', project_path, 'is alrady started')
        return

    server = Server(project_path)
    server.start()

    def load_all_files():
        retry = 0
        while True:
            time.sleep(0.5)
            return_val = send_client_command(server.port, {"command": "load", "params": {}})
            print(return_val)
            if return_val is not None and return_val[0] == 0:
                if callback is not None:
                    callback(json.loads(return_val[1].decode('utf-8'))['result'])
                break
            retry += 1
            if retry >= 10:
                break
    threading.Thread(target=load_all_files).start()
    print('Started purs ide server for path: ', project_path)

def stop_server(project_path):
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

def get_code_complete(project_path, prefix):
    if project_path not in servers:
        print('Server for path ', project_path, ' is not running')
        return
    try:
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
        if num != 0:
            return
        return json.loads(result.decode('utf-8'))['result']
    except Exception as e:
        print(e)

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
