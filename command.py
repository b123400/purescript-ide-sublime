import os
import subprocess
import threading

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
        proc.stdin.write(stdin_text)
        proc.stdin.close()
    result = b''
    return_val = None
    while True:
        return_val = proc.poll()
        if return_val is not None:
            break
        line = proc.stdout.readline() # This blocks until it receives a newline.
        print(line)
        result += line
    # When the subprocess terminates there might be unconsumed output
    # that still needs to be processed.
    result += proc.stdout.read()
    return (return_val, result)

# Path: Thread
servers = {}

def start_server(project_path):
    if project_path in servers:
        print('purs ide server for', project_path, 'is alrady started')
        return

    thread = threading.Thread(
        target=run_command,
        args=([
            PURS_PATH, 'ide', 'server',
            '--directory', project_path,
            './**/*.purs',
            '--log-level', 'all',
            '--port', str(PURS_IDE_PORT)],))

    servers[project_path] = thread
    # TODO: different port for different projects
    # TODO: handle server quit
    thread.start()
    print('started purs ide server for path: ', project_path)
