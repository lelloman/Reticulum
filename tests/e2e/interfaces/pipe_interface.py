"""
Pipe interface for cross-implementation testing.

This interface communicates with an external process via stdin/stdout,
allowing testing of protocol conformance between different implementations.
"""

import os
import sys
import time
import threading
import subprocess
from queue import Queue, Empty

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import RNS
from RNS.Interfaces.Interface import Interface


class TestPipeInterface(Interface):
    """
    Interface for cross-implementation testing via subprocess.

    Communicates with an external implementation using HDLC-like framing
    over stdin/stdout pipes.

    Frame format:
        FLAG(1) + escaped_data + FLAG(1)
        FLAG = 0x7E
        ESCAPE = 0x7D
        Escaped bytes: 0x7E -> 0x7D 0x5E, 0x7D -> 0x7D 0x5D
    """

    FLAG = 0x7E
    ESCAPE = 0x7D

    def __init__(self, owner, subprocess_cmd, name="TestPipeInterface"):
        """
        Initialize pipe interface.

        Args:
            owner: RNS.Reticulum instance or Transport
            subprocess_cmd: List of command and arguments to spawn
            name: Interface name
        """
        super().__init__()

        self.owner = owner
        self.name = name
        self.IN = True
        self.OUT = True
        self.online = False

        self.subprocess_cmd = subprocess_cmd
        self.process = None
        self.read_thread = None
        self.running = False

        self.rx_buffer = bytearray()
        self.tx_queue = Queue()

        # Capture for testing
        self.outgoing_packets = []
        self.incoming_packets = []

        # Statistics
        self.txb = 0
        self.rxb = 0

    def start(self):
        """Start the subprocess and begin communication."""
        try:
            self.process = subprocess.Popen(
                self.subprocess_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )

            self.running = True
            self.online = True

            # Start read thread
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()

            RNS.log(f"TestPipeInterface started with PID {self.process.pid}", RNS.LOG_DEBUG)
            return True

        except Exception as e:
            RNS.log(f"Failed to start TestPipeInterface: {e}", RNS.LOG_ERROR)
            return False

    def stop(self):
        """Stop the subprocess and clean up."""
        self.running = False
        self.online = False

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                RNS.log(f"Error stopping subprocess: {e}", RNS.LOG_WARNING)

        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=2)

    def _escape(self, data):
        """HDLC-like byte escaping."""
        escaped = bytearray()
        for byte in data:
            if byte == self.FLAG:
                escaped.extend([self.ESCAPE, 0x5E])
            elif byte == self.ESCAPE:
                escaped.extend([self.ESCAPE, 0x5D])
            else:
                escaped.append(byte)
        return bytes(escaped)

    def _unescape(self, data):
        """HDLC-like byte unescaping."""
        unescaped = bytearray()
        i = 0
        while i < len(data):
            if data[i] == self.ESCAPE and i + 1 < len(data):
                if data[i + 1] == 0x5E:
                    unescaped.append(self.FLAG)
                elif data[i + 1] == 0x5D:
                    unescaped.append(self.ESCAPE)
                else:
                    # Invalid escape sequence, pass through
                    unescaped.append(data[i])
                    unescaped.append(data[i + 1])
                i += 2
            else:
                unescaped.append(data[i])
                i += 1
        return bytes(unescaped)

    def _frame(self, data):
        """Create HDLC-like frame."""
        escaped = self._escape(data)
        return bytes([self.FLAG]) + escaped + bytes([self.FLAG])

    def _read_loop(self):
        """Background thread to read from subprocess stdout."""
        in_frame = False

        while self.running and self.process:
            try:
                byte = self.process.stdout.read(1)
                if not byte:
                    # EOF - process likely terminated
                    RNS.log("TestPipeInterface: subprocess closed stdout", RNS.LOG_DEBUG)
                    break

                b = byte[0]

                if b == self.FLAG:
                    if in_frame and len(self.rx_buffer) > 0:
                        # End of frame
                        frame_data = self._unescape(bytes(self.rx_buffer))
                        self._process_frame(frame_data)
                        self.rx_buffer.clear()
                    # Start new frame or consecutive flags
                    in_frame = True
                elif in_frame:
                    self.rx_buffer.append(b)

            except Exception as e:
                if self.running:
                    RNS.log(f"TestPipeInterface read error: {e}", RNS.LOG_WARNING)
                break

        self.online = False

    def _process_frame(self, data):
        """Process received frame."""
        if len(data) < 1:
            return

        timestamp = time.time()
        self.incoming_packets.append((timestamp, data))
        self.rxb += len(data)

        # Pass to owner
        if self.owner and hasattr(self.owner, 'inbound'):
            self.owner.inbound(data, self)

    def processOutgoing(self, data):
        """Send data to subprocess."""
        if not self.online or not self.process:
            return

        try:
            timestamp = time.time()
            self.outgoing_packets.append((timestamp, bytes(data)))

            frame = self._frame(data)
            self.process.stdin.write(frame)
            self.process.stdin.flush()

            self.txb += len(data)

        except Exception as e:
            RNS.log(f"TestPipeInterface write error: {e}", RNS.LOG_WARNING)
            self.online = False

    def get_capture_log(self):
        """Return captured packets for test verification."""
        return {
            "outgoing": [
                {"timestamp": ts, "data_hex": data.hex(), "length": len(data)}
                for ts, data in self.outgoing_packets
            ],
            "incoming": [
                {"timestamp": ts, "data_hex": data.hex(), "length": len(data)}
                for ts, data in self.incoming_packets
            ]
        }

    def clear_capture(self):
        """Clear captured packet logs."""
        self.outgoing_packets.clear()
        self.incoming_packets.clear()

    def inject_packet(self, raw):
        """Inject a packet as if received from subprocess."""
        timestamp = time.time()
        self.incoming_packets.append((timestamp, raw))
        self.rxb += len(raw)

        if self.owner and hasattr(self.owner, 'inbound'):
            self.owner.inbound(raw, self)

    def send_raw(self, data):
        """Send raw data to subprocess (for testing)."""
        if self.process and self.process.stdin:
            frame = self._frame(data)
            self.process.stdin.write(frame)
            self.process.stdin.flush()

    def get_stderr(self):
        """Get any stderr output from subprocess."""
        if self.process and self.process.stderr:
            try:
                return self.process.stderr.read()
            except Exception:
                return b""
        return b""

    def is_alive(self):
        """Check if subprocess is still running."""
        if self.process:
            return self.process.poll() is None
        return False

    def __str__(self):
        return f"TestPipeInterface[{self.name}]"


class MockExternalProcess:
    """
    Mock external process for testing the pipe interface itself.

    This can be used to test the pipe interface without a real
    external implementation.
    """

    FLAG = 0x7E
    ESCAPE = 0x7D

    def __init__(self):
        self.received_frames = []
        self.responses = []

    def _escape(self, data):
        escaped = bytearray()
        for byte in data:
            if byte == self.FLAG:
                escaped.extend([self.ESCAPE, 0x5E])
            elif byte == self.ESCAPE:
                escaped.extend([self.ESCAPE, 0x5D])
            else:
                escaped.append(byte)
        return bytes(escaped)

    def _unescape(self, data):
        unescaped = bytearray()
        i = 0
        while i < len(data):
            if data[i] == self.ESCAPE and i + 1 < len(data):
                if data[i + 1] == 0x5E:
                    unescaped.append(self.FLAG)
                elif data[i + 1] == 0x5D:
                    unescaped.append(self.ESCAPE)
                else:
                    unescaped.append(data[i])
                    unescaped.append(data[i + 1])
                i += 2
            else:
                unescaped.append(data[i])
                i += 1
        return bytes(unescaped)

    def receive_frame(self, framed_data):
        """Simulate receiving a frame from the interface."""
        # Strip flags and unescape
        if framed_data[0] == self.FLAG:
            framed_data = framed_data[1:]
        if framed_data[-1] == self.FLAG:
            framed_data = framed_data[:-1]

        data = self._unescape(framed_data)
        self.received_frames.append(data)
        return data

    def create_response(self, data):
        """Create a framed response."""
        escaped = self._escape(data)
        return bytes([self.FLAG]) + escaped + bytes([self.FLAG])

    def queue_response(self, data):
        """Queue a response to be sent."""
        self.responses.append(self.create_response(data))
