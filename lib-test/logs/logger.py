"""
로거 모듈
콘솔과 파일에 동시 출력하는 TeeLogger
"""

import sys


class TeeLogger:
    """콘솔과 파일에 동시 출력하는 로거"""

    def __init__(self, log_file):
        self.terminal = sys.stdout
        self.log = open(log_file, 'w', encoding='utf-8')
        self.log_file = log_file

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()  # 즉시 파일에 쓰기

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        if self.log:
            self.log.close()
