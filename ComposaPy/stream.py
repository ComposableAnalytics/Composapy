import io
from System import Byte, Array
from CompAnalytics.IServices import *


class CsStream(io.RawIOBase):
    def __init__(self, stream):
        self.messageBodyStream = stream
        self.buffer = Array.CreateInstance(Byte, 4096)

    def read(self, size=-1):
        read_size = 4096 if size == -1 else min(size, 4096)
        number_bytes_read = self.messageBodyStream.Read(self.buffer, 0, read_size)
        return bytes(self.buffer)[0:number_bytes_read]

    def readable(self):
        return True
