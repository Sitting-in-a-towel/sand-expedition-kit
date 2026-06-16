"""Minimal Odin Serializer binary format reader (TeamSirenix/odin-serializer BinaryDataReader).
Decodes SerializedScriptableObject `serializationData.SerializedBytes` blobs into Python dicts.
"""
import struct

# BinaryEntryType
INVALID = 0
NAMED_REF_NODE = 1
UNNAMED_REF_NODE = 2
NAMED_STRUCT_NODE = 3
UNNAMED_STRUCT_NODE = 4
END_OF_NODE = 5
START_ARRAY = 6
END_ARRAY = 7
PRIMITIVE_ARRAY = 8
NAMED_INTERNAL_REF = 9
UNNAMED_INTERNAL_REF = 10
NAMED_EXT_INDEX = 11
UNNAMED_EXT_INDEX = 12
NAMED_EXT_GUID = 13
UNNAMED_EXT_GUID = 14
EOS = 49
NAMED_EXT_STRING = 50
UNNAMED_EXT_STRING = 51
TYPE_NAME = 47
TYPE_ID = 48

PRIMS = {
    15: ('b', 1), 16: ('b', 1),        # sbyte
    17: ('B', 1), 18: ('B', 1),        # byte
    19: ('h', 2), 20: ('h', 2),        # short
    21: ('H', 2), 22: ('H', 2),        # ushort
    23: ('i', 4), 24: ('i', 4),        # int
    25: ('I', 4), 26: ('I', 4),        # uint
    27: ('q', 8), 28: ('q', 8),        # long
    29: ('Q', 8), 30: ('Q', 8),        # ulong
    31: ('f', 4), 32: ('f', 4),        # float
    33: ('d', 8), 34: ('d', 8),        # double
}
NAMED_CHAR, UNNAMED_CHAR = 37, 38
NAMED_STRING, UNNAMED_STRING = 39, 40
NAMED_GUID, UNNAMED_GUID = 41, 42
NAMED_BOOL, UNNAMED_BOOL = 43, 44
NAMED_NULL, UNNAMED_NULL = 45, 46
NAMED_DECIMAL, UNNAMED_DECIMAL = 35, 36


class OdinReader:
    def __init__(self, data: bytes):
        self.d = data
        self.p = 0
        self.types = {}  # id -> type name

    def u8(self):
        v = self.d[self.p]; self.p += 1; return v

    def i32(self):
        v = struct.unpack_from('<i', self.d, self.p)[0]; self.p += 4; return v

    def i64(self):
        v = struct.unpack_from('<q', self.d, self.p)[0]; self.p += 8; return v

    def prim(self, fmt, size):
        v = struct.unpack_from('<' + fmt, self.d, self.p)[0]; self.p += size; return v

    def string(self):
        flag = self.u8()
        n = self.i32()
        if flag == 0:
            s = self.d[self.p:self.p + n].decode('ascii', 'replace'); self.p += n
        else:
            s = self.d[self.p:self.p + 2 * n].decode('utf-16-le', 'replace'); self.p += 2 * n
        return s

    def read_type(self):
        e = self.u8()
        if e == TYPE_NAME:
            tid = self.i32()
            name = self.string()
            self.types[tid] = name
            return name
        elif e == TYPE_ID:
            tid = self.i32()
            return self.types.get(tid, f'typeid:{tid}')
        else:
            raise ValueError(f'expected type entry, got {e} at {self.p - 1}')

    def read_document(self):
        """Top level: sequence of named values until EOS."""
        out = {}
        while self.p < len(self.d):
            e = self.d[self.p]
            if e == EOS:
                break
            name, val = self.read_entry()
            out[name if name is not None else f'@{len(out)}'] = val
        return out

    def read_entry(self):
        """Returns (name_or_None, value)."""
        e = self.u8()
        if e == NAMED_REF_NODE:
            name = self.string()
            return name, self.read_node(ref=True)
        if e == UNNAMED_REF_NODE:
            return None, self.read_node(ref=True)
        if e == NAMED_STRUCT_NODE:
            name = self.string()
            return name, self.read_node(ref=False)
        if e == UNNAMED_STRUCT_NODE:
            return None, self.read_node(ref=False)
        if e in PRIMS:
            name = self.string() if e % 2 == 1 else None
            fmt, size = PRIMS[e]
            return name, self.prim(fmt, size)
        if e in (NAMED_BOOL, UNNAMED_BOOL):
            name = self.string() if e == NAMED_BOOL else None
            return name, bool(self.u8())
        if e in (NAMED_STRING, UNNAMED_STRING):
            name = self.string() if e == NAMED_STRING else None
            return name, self.string()
        if e in (NAMED_CHAR, UNNAMED_CHAR):
            name = self.string() if e == NAMED_CHAR else None
            v = struct.unpack_from('<H', self.d, self.p)[0]; self.p += 2
            return name, chr(v)
        if e in (NAMED_NULL, UNNAMED_NULL):
            name = self.string() if e == NAMED_NULL else None
            return name, None
        if e in (NAMED_GUID, UNNAMED_GUID):
            name = self.string() if e == NAMED_GUID else None
            raw = self.d[self.p:self.p + 16]; self.p += 16
            return name, raw.hex()
        if e in (NAMED_DECIMAL, UNNAMED_DECIMAL):
            name = self.string() if e == NAMED_DECIMAL else None
            raw = self.d[self.p:self.p + 16]; self.p += 16
            return name, raw.hex()
        if e in (NAMED_INTERNAL_REF, UNNAMED_INTERNAL_REF):
            name = self.string() if e == NAMED_INTERNAL_REF else None
            return name, {'$iref': self.i32()}
        if e in (NAMED_EXT_INDEX, UNNAMED_EXT_INDEX):
            name = self.string() if e == NAMED_EXT_INDEX else None
            return name, {'$extIndex': self.i32()}
        if e in (NAMED_EXT_GUID, UNNAMED_EXT_GUID):
            name = self.string() if e == NAMED_EXT_GUID else None
            raw = self.d[self.p:self.p + 16]; self.p += 16
            return name, {'$extGuid': raw.hex()}
        if e in (NAMED_EXT_STRING, UNNAMED_EXT_STRING):
            name = self.string() if e == NAMED_EXT_STRING else None
            return name, {'$extStr': self.string()}
        if e == START_ARRAY:
            self.p -= 1
            return None, self.read_array()
        if e == PRIMITIVE_ARRAY:
            self.p -= 1
            return None, self.read_prim_array()
        raise ValueError(f'unknown entry {e} at offset {self.p - 1}')

    def read_node(self, ref):
        node = {}
        # peek: type entry present?
        nxt = self.d[self.p]
        if nxt in (TYPE_NAME, TYPE_ID):
            node['$type'] = self.read_type()
        if ref:
            node['$id'] = self.i32()
        # children until EndOfNode
        i = 0
        while True:
            e = self.d[self.p]
            if e == END_OF_NODE:
                self.p += 1
                break
            if e == EOS:
                break
            if e == START_ARRAY:
                self.p += 1
                node['$items'] = self.read_array_body()
                continue
            if e == PRIMITIVE_ARRAY:
                node['$items'] = self.read_prim_array()
                continue
            name, val = self.read_entry()
            node[name if name is not None else f'@{i}'] = val
            i += 1
        return node

    def read_array(self):
        e = self.u8()
        assert e == START_ARRAY
        return self.read_array_body()

    def read_array_body(self):
        n = self.i64()
        items = []
        while True:
            e = self.d[self.p]
            if e == END_ARRAY:
                self.p += 1
                break
            _, val = self.read_entry()
            items.append(val)
        return items

    def read_prim_array(self):
        e = self.u8()
        assert e == PRIMITIVE_ARRAY
        count = self.i32()
        per = self.i32()
        raw = self.d[self.p:self.p + count * per]
        self.p += count * per
        return {'$primArray': raw.hex(), 'count': count, 'elemSize': per}


def decode(serialized_bytes):
    b = bytes(x & 0xFF for x in serialized_bytes)
    return OdinReader(b).read_document()


if __name__ == '__main__':
    import sys, json
    src, asset_name, out = sys.argv[1], sys.argv[2], sys.argv[3]
    d = json.load(open(src, encoding='utf-8'))
    o = next(x for x in d if x['data'].get('m_Name') == asset_name)
    doc = decode(o['data']['serializationData']['SerializedBytes'])
    json.dump(doc, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('wrote', out)
