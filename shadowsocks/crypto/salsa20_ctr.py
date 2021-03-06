#!/usr/bin/env python

# Copyright (c) 2014 clowwindy
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import absolute_import, division, print_function, \
    with_statement

import struct
import logging
import sys

slow_xor = False
imported = False

salsa20 = None
numpy = None

BLOCK_SIZE = 16384


def run_imports():
    global imported, slow_xor, salsa20, numpy
    if not imported:
        imported = True
        try:
            numpy = __import__('numpy')
        except ImportError:
            logging.error('can not import numpy, using SLOW XOR')
            logging.error('please install numpy if you use salsa20')
            slow_xor = True
        try:
            salsa20 = __import__('salsa20')
        except ImportError:
            logging.error('you have to install salsa20 before you use salsa20')
            sys.exit(1)


def numpy_xor(a, b):
    if slow_xor:
        return py_xor_str(a, b)
    dtype = numpy.byte
    if len(a) % 4 == 0:
        dtype = numpy.uint32
    elif len(a) % 2 == 0:
        dtype = numpy.uint16

    ab = numpy.frombuffer(a, dtype = dtype)
    bb = numpy.frombuffer(b, dtype = dtype)
    c = numpy.bitwise_xor(ab, bb)
    r = c.tostring()
    return r

# 返回两个字符串异或值
def py_xor_str(a, b):
    c = []
    if bytes == str:
        for i in range(0, len(a)):
            c.append(chr(ord(a[i]) ^ ord(b[i])))
        return ''.join(c)
    else:
        for i in range(0, len(a)):
            c.append(a[i] ^ b[i])
        return bytes(c)


class Salsa20Cipher(object):
    """a salsa20 CTR implemetation, provides m2crypto like cipher API"""

    def __init__(self, alg, key, iv, op, key_as_bytes = 0, d = None, salt = None,
                 i = 1, padding = 1):
        # 导入numpy
        run_imports()
        if alg != b'salsa20-ctr':
            raise Exception('unknown algorithm')
        self._key = key
        # little-endian解包出int64型作为nonce，nonce的作用是一个不重复的值，配合key使用。
        self._nonce = struct.unpack('<Q', iv)[0]
        self._pos = 0
        self._next_stream()

    def _next_stream(self):
        # 再次确保nonce是64位
        self._nonce &= 0xFFFFFFFFFFFFFFFF
        # BLOCK_SIZE: 16384 Bytes
        # self._stream是加密后的数据
        self._stream = salsa20.Salsa20_keystream(BLOCK_SIZE,
                                                 struct.pack('<Q',
                                                             self._nonce),    # 将key和nonce连接
                                                 self._key)
        # counter模式，自增。
        self._nonce += 1

    def update(self, data):
        results = []
        while True:
            # 剩下的未加密数据流长度
            remain = BLOCK_SIZE - self._pos
            cur_data = data[:remain]
            cur_data_len = len(cur_data)
            # 当前一轮的加密后的数据存放在cur_stream
            cur_stream = self._stream[self._pos:self._pos + cur_data_len]
            self._pos = self._pos + cur_data_len
            # 切掉已经加密的数据明文前面部分
            data = data[remain:]
            # 加上已经加密的密文
            results.append(numpy_xor(cur_data, cur_stream))

            # 这个是并发执行的，连续对不同的BLOCK的数据加密，速度较快
            if self._pos >= BLOCK_SIZE:
                self._next_stream()
                self._pos = 0
            # 没有数据可以加密
            if not data:
                break
            
        # 返回二进制的result
        return b''.join(results)


ciphers = {
    b'salsa20-ctr': (32, 8, Salsa20Cipher),
}


def test():
    from shadowsocks.crypto import util

    cipher = Salsa20Cipher(b'salsa20-ctr', b'k' * 32, b'i' * 8, 1)
    decipher = Salsa20Cipher(b'salsa20-ctr', b'k' * 32, b'i' * 8, 1)

    util.run_cipher(cipher, decipher)


if __name__ == '__main__':
    test()
