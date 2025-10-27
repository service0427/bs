"""
BrowserStack Local 연결 관리
로컬 PC의 IP를 사용하여 BrowserStack 디바이스에서 접속
"""

import subprocess
import time
import os
import sys
import signal
import atexit
import threading
import queue

# 프로젝트 루트 (lib/utils/ → lib/ → 프로젝트 루트)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BROWSERSTACK_LOCAL_BIN = os.path.join(PROJECT_ROOT, 'BrowserStackLocal')

from lib.settings import BROWSERSTACK_ACCESS_KEY


class BrowserStackLocal:
    """BrowserStack Local 터널 관리"""

    def __init__(self):
        self.process = None
        self.local_identifier = None

    def start(self, local_identifier='browserstack-local'):
        """
        BrowserStack Local 연결 시작

        Args:
            local_identifier: Local 식별자 (고유값)

        Returns:
            bool: 성공 여부
        """
        if self.process:
            print("⚠️  BrowserStack Local이 이미 실행 중입니다.")
            return True

        if not os.path.exists(BROWSERSTACK_LOCAL_BIN):
            print(f"❌ BrowserStack Local 바이너리를 찾을 수 없습니다: {BROWSERSTACK_LOCAL_BIN}")
            return False

        self.local_identifier = local_identifier

        print("\n" + "="*60)
        print("🔗 BrowserStack Local 연결 시작")
        print("="*60)
        print(f"Identifier: {self.local_identifier}")
        print("로컬 PC의 IP를 BrowserStack 디바이스에서 사용합니다.")
        print()

        # BrowserStack Local 실행
        # --key: Access Key
        # --local-identifier: 식별자
        # --daemon-mode: 백그라운드 실행
        # --force-local: 모든 트래픽을 로컬로
        cmd = [
            BROWSERSTACK_LOCAL_BIN,
            '--key', BROWSERSTACK_ACCESS_KEY,
            '--local-identifier', self.local_identifier,
            '--force-local'
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )

            # stdout을 읽는 스레드
            output_queue = queue.Queue()
            output_lines = []

            def read_output():
                try:
                    for line in iter(self.process.stdout.readline, ''):
                        if line:
                            output_queue.put(line.strip())
                except:
                    pass

            reader_thread = threading.Thread(target=read_output, daemon=True)
            reader_thread.start()

            # 연결 완료 메시지 대기 (최대 30초)
            print("연결 중", end="", flush=True)
            connected = False
            start_time = time.time()

            while time.time() - start_time < 30:
                # 프로세스가 죽었는지 확인
                if self.process.poll() is not None:
                    print(f"\n\n❌ BrowserStack Local 시작 실패")
                    print(f"출력:")
                    for line in output_lines:
                        print(f"  {line}")
                    return False

                # 큐에서 출력 읽기
                try:
                    line = output_queue.get(timeout=0.5)
                    output_lines.append(line)
                    print(".", end="", flush=True)

                    # 연결 완료 메시지 확인
                    if "You can now access" in line or "Connected" in line or "success" in line.lower():
                        connected = True
                        break
                except queue.Empty:
                    pass

                time.sleep(0.1)

            if not connected:
                print(f"\n\n⚠️ 연결 완료 메시지를 받지 못했습니다")
                print(f"출력 (최근 10줄):")
                for line in output_lines[-10:]:
                    print(f"  {line}")
                print(f"\n계속 진행합니다... (프로세스는 실행 중: PID {self.process.pid})")

            print(" ✓")
            print("\n✅ BrowserStack Local 연결 완료!")
            print(f"PID: {self.process.pid}")
            if output_lines:
                print(f"마지막 메시지: {output_lines[-1][:80]}...")
            print("="*60 + "\n")

            # 종료 시 자동으로 stop 호출
            atexit.register(self.stop)

            return True

        except Exception as e:
            print(f"\n\n❌ BrowserStack Local 실행 오류: {e}")
            return False

    def stop(self):
        """BrowserStack Local 연결 종료"""
        if self.process:
            print("\n" + "="*60)
            print("🔌 BrowserStack Local 연결 종료")
            print("="*60)

            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                print("✓ 정상 종료")
            except subprocess.TimeoutExpired:
                print("⚠️  강제 종료")
                self.process.kill()

            self.process = None
            self.local_identifier = None

    def is_running(self):
        """Local이 실행 중인지 확인 (실제 프로세스 체크)"""
        # Python 인스턴스의 프로세스 정보 확인
        if self.process:
            if self.process.poll() is None:
                return True

        # 실제로 실행 중인 BrowserStackLocal 프로세스 찾기
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'BrowserStackLocal'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                print("✓ BrowserStack Local 프로세스 발견 (PID 재연결)")
                # PID 찾아서 프로세스 정보 복구 (선택)
                return True
        except Exception as e:
            pass

        return False


# 전역 인스턴스
_local_instance = None


def get_local_instance():
    """BrowserStack Local 전역 인스턴스 가져오기"""
    global _local_instance
    if _local_instance is None:
        _local_instance = BrowserStackLocal()
    return _local_instance


def ensure_local_running(local_identifier='browserstack-local'):
    """
    BrowserStack Local이 실행 중인지 확인하고, 없으면 시작

    Args:
        local_identifier: Local 식별자

    Returns:
        tuple: (성공 여부, 인스턴스)
    """
    instance = get_local_instance()

    if instance.is_running():
        print(f"✓ BrowserStack Local 이미 실행 중 (PID: {instance.process.pid})")
        return True, instance

    success = instance.start(local_identifier)
    return success, instance


if __name__ == '__main__':
    # 테스트
    print("BrowserStack Local 테스트 시작\n")

    local = BrowserStackLocal()

    # 시작
    if local.start():
        print("\n연결 성공! 30초 동안 유지합니다...")
        time.sleep(30)

        # 종료
        local.stop()
    else:
        print("\n연결 실패!")
        sys.exit(1)
