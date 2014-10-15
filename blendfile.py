# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****
#
# (c) 2009, At Mind B.V. - Jeroen Bakker

# 06-10-2009:
#  jbakker - adding support for python 3.0
# 26-10-2009:
#  jbakker - adding caching of the SDNA records.
#  jbakker - adding caching for file block lookup
#  jbakker - increased performance for readstring
# 27-10-2009:
#  jbakker - remove FileBlockHeader class (reducing memory print,
#            increasing performance)
# 28-10-2009:
#  jbakker - reduce far-calls by joining setfield with encode and
#            getfield with decode
# 02-11-2009:
#  jbakker - python 3 compatibility added


import os
import struct
import logging
import gzip
import tempfile

log = logging.getLogger("blendfile")
FILE_BUFFER_SIZE = 1024 * 1024


# -----------------------------------------------------------------------------
# module global routines
#
# read routines
# open a filename
# determine if the file is compressed
# and returns a handle
def open_blend(filename, access="rb"):
    """Opens a blend file for reading or writing pending on the access
    supports 2 kind of blend files. Uncompressed and compressed.
    Known issue: does not support packaged blend files
    """
    handle = open(filename, access)
    magic = handle.read(7)
    if magic == b"BLENDER":
        log.debug("normal blendfile detected")
        handle.seek(0, os.SEEK_SET)
        bfile = BlendFile(handle)
        bfile.is_compressed = False
        bfile.filepath_orig = filename
        return bfile
    else:
        log.debug("gzip blendfile detected?")
        handle.close()
        log.debug("decompressing started")
        fs = gzip.open(filename, "rb")
        handle = tempfile.TemporaryFile()
        data = fs.read(FILE_BUFFER_SIZE)
        while data:
            handle.write(data)
            data = fs.read(FILE_BUFFER_SIZE)
        log.debug("decompressing finished")
        fs.close()
        log.debug("resetting decompressed file")
        handle.seek(os.SEEK_SET, 0)
        bfile = BlendFile(handle)
        bfile.is_compressed = True
        bfile.filepath_orig = filename
        return bfile


def align(offset, by):
    n = by - 1
    return (offset + n) & ~n


# -----------------------------------------------------------------------------
# module classes


class BlendFile:
    """
    Blend file.
    """
    __slots__ = (
        # file (result of open())
        "handle",
        # str (original name of the file path)
        "filepath_orig",
        # BlendFileHeader
        "header",
        # struct.Struct
        "block_header_struct",
        # FileBlockHeader
        "blocks",
        # DNACatalog
        "catalog",
        # int
        "code_index",
        # bool (did we make a change)
        "is_modified",
        # bool (is file gzipped)
        "is_compressed",
        )

    def __init__(self, handle):
        log.debug("initializing reading blend-file")
        self.handle = handle
        self.header = BlendFileHeader(handle)
        self.block_header_struct = self.header.create_block_header_struct()
        self.blocks = []
        self.code_index = {}

        block = BlendFileBlock(handle, self)
        while block.code != b'ENDB':
            if block.code == b'DNA1':
                self.catalog = DNACatalog(self.header, block, handle)
            else:
                handle.seek(block.size, os.SEEK_CUR)

            self.blocks.append(block)
            self.code_index.setdefault(block.code, []).append(block)

            block = BlendFileBlock(handle, self)
        self.is_modified = False
        self.blocks.append(block)

    def find_blocks_from_code(self, code):
        assert(type(code) == bytes)
        if code not in self.code_index:
            return []
        return self.code_index[code]

    def find_block_from_offset(self, offset):
        for block in self.blocks:
            if block.addr_old == offset:
                return block
        return None

    def close(self):
        """
        Close the blend file
        writes the blend file to disk if changes has happened
        """
        if not self.is_modified:
            self.handle.close()
        else:
            handle = self.handle
            if self.is_compressed:
                log.debug("close compressed blend file")
                handle.seek(os.SEEK_SET, 0)
                log.debug("compressing started")
                fs = gzip.open(self.filepath_orig, "wb")
                data = handle.read(FILE_BUFFER_SIZE)
                while data:
                    fs.write(data)
                    data = handle.read(FILE_BUFFER_SIZE)
                fs.close()
                log.debug("compressing finished")

            handle.close()


class BlendFileBlock:
    """
    Instance of a struct.
    """
    __slots__ = (
        # BlendFile
        "file",
        "code",
        "size",
        "addr_old",
        "sdna_index",
        "count",
        "file_offset",
        )

    def __init__(self, handle, bfile):
        self.file = bfile

        data = handle.read(bfile.block_header_struct.size)
        # header size can be 8, 20, or 24 bytes long
        # 8: old blend files ENDB block (exception)
        # 20: normal headers 32 bit platform
        # 24: normal headers 64 bit platform
        if len(data) > 15:

            blockheader = bfile.block_header_struct.unpack(data)
            self.code = blockheader[0].partition(b'\0')[0]
            if self.code != b'ENDB':
                self.size = blockheader[1]
                self.addr_old = blockheader[2]
                self.sdna_index = blockheader[3]
                self.count = blockheader[4]
                self.file_offset = handle.tell()
            else:
                self.size = 0
                self.addr_old = 0
                self.sdna_index = 0
                self.count = 0
                self.file_offset = 0
        else:
            blockheader = OLDBLOCK.unpack(data)
            self.code = blockheader[0].partition(b'\0')[0]
            self.code = DNA_IO.read_data0(blockheader[0], 0)
            self.size = 0
            self.addr_old = 0
            self.sdna_index = 0
            self.count = 0
            self.file_offset = 0

    def get(self, path,
            use_nil=True, use_str=True):
        dna_struct = self.file.catalog.structs[self.sdna_index]
        self.file.handle.seek(self.file_offset, os.SEEK_SET)
        return dna_struct.field_get(self.file.header, self.file.handle, path,
                                    use_nil=use_nil, use_str=use_str)

    def set(self, path, value):
        dna_struct = self.file.catalog.structs[self.sdna_index]
        self.file.handle.seek(self.file_offset, os.SEEK_SET)
        self.file.is_modified = True
        return dna_struct.field_set(
                self.file.header, self.file.handle, path, value)

    # ----------------------
    # Python convenience API

    # dict like access
    def __getitem__(self, item):
        return self.get(item, use_str=False)

    def __setitem__(self, item, value):
        self.set(item, value)

    def keys(self):
        dna_struct = self.file.catalog.structs[self.sdna_index]
        return (s[1].name_short for s in dna_struct.fields)

    def values(self):
        return (self[k] for k in self.keys())

    def items(self):
        return ((k, self[k]) for k in self.keys())


# -----------------------------------------------------------------------------
# Read Magic
#
# magic = str
# pointer_size = int
# is_little_endian = bool
# version = int
BLOCKHEADERSTRUCT = {}
BLOCKHEADERSTRUCT["<4"] = struct.Struct("<4sIIII")
BLOCKHEADERSTRUCT[">4"] = struct.Struct(">4sIIII")
BLOCKHEADERSTRUCT["<8"] = struct.Struct("<4sIQII")
BLOCKHEADERSTRUCT[">8"] = struct.Struct(">4sIQII")
FILEHEADER = struct.Struct("7s1s1s3s")
OLDBLOCK = struct.Struct("4sI")


class BlendFileHeader:
    """
    BlendFileHeader allocates the first 12 bytes of a blend file
    it contains information about the hardware architecture
    """
    __slots__ = (
        # str
        "magic",
        # int 4/8
        "pointer_size",
        # bool
        "is_little_endian",
        # int
        "version",
        # str, used to pass to 'struct'
        "endian_str",
        # int, used to index common types
        "endian_index",
        )

    def __init__(self, handle):
        log.debug("reading blend-file-header")
        values = FILEHEADER.unpack(handle.read(FILEHEADER.size))
        self.magic = values[0]
        pointer_size_id = values[1]
        if pointer_size_id == b'-':
            self.pointer_size = 8
        elif pointer_size_id == b'_':
            self.pointer_size = 4
        else:
            assert(0)
        endian_id = values[2]
        if endian_id == b'v':
            self.is_little_endian = True
            self.endian_str = "<"
            self.endian_index = 0
        elif endian_id == b'V':
            self.is_little_endian = False
            self.endian_index = 1
            self.endian_str = ">"
        else:
            assert(0)

        version_id = values[3]
        self.version = int(version_id)

    def create_block_header_struct(self):
        return BLOCKHEADERSTRUCT[self.endian_str + str(self.pointer_size)]


class DNACatalog:
    """
    DNACatalog is a catalog of all information in the DNA1 file-block
    """
    __slots__ = (
        "header",
        "names",
        "types",
        # DNAStruct[]
        "structs",
        )

    def __init__(self, header, block, handle):
        log.debug("building DNA catalog")
        shortstruct = DNA_IO.USHORT[header.endian_index]
        shortstruct2 = struct.Struct(str(DNA_IO.USHORT[header.endian_index].format.decode() + 'H'))
        intstruct = DNA_IO.UINT[header.endian_index]
        data = handle.read(block.size)
        self.names = []
        self.types = []
        self.structs = []

        offset = 8
        names_len = intstruct.unpack_from(data, offset)[0]
        offset += 4

        log.debug("building #%d names" % names_len)
        for i in range(names_len):
            tName = DNA_IO.read_data0(data, offset)
            offset = offset + len(tName) + 1
            self.names.append(DNAName(tName))
        del names_len

        offset = align(offset, 4)
        offset += 4
        types_len = intstruct.unpack_from(data, offset)[0]
        offset += 4
        log.debug("building #%d types" % types_len)
        for i in range(types_len):
            tType = DNA_IO.read_data0(data, offset)
            # None will be replaced by the DNAStruct, below
            self.types.append([tType, 0, None])
            offset += len(tType) + 1

        offset = align(offset, 4)
        offset += 4
        log.debug("building #%d type-lengths" % types_len)
        for i in range(types_len):
            tLen = shortstruct.unpack_from(data, offset)[0]
            offset = offset + 2
            self.types[i][1] = tLen
        del types_len

        offset = align(offset, 4)
        offset += 4

        structs_len = intstruct.unpack_from(data, offset)[0]
        offset += 4
        log.debug("building #%d structures" % structs_len)
        for struct_index in range(structs_len):
            d = shortstruct2.unpack_from(data, offset)
            struct_type_index = d[0]
            offset += 4
            dna_type = self.types[struct_type_index]
            dna_struct = DNAStruct()
            dna_type[2] = dna_struct
            self.structs.append(dna_struct)

            fields_len = d[1]

            for field_index in range(fields_len):
                d2 = shortstruct2.unpack_from(data, offset)
                field_type_index = d2[0]
                field_name_index = d2[1]
                offset += 4
                fType = self.types[field_type_index]
                fName = self.names[field_name_index]
                if fName.is_pointer or fName.is_method_pointer:
                    fsize = header.pointer_size * fName.array_size
                else:
                    fsize = fType[1] * fName.array_size
                dna_struct.fields.append([fType, fName, fsize])


class DNAName:
    """
    DNAName is a C-type name stored in the DNA
    """
    __slots__ = (
        "name",
        "name_short",
        "is_pointer",
        "is_method_pointer",
        "array_size",
        )

    def __init__(self, aName):
        self.name = aName
        self.name_short = self.calc_name_short()
        self.is_pointer = self.calc_is_pointer()
        self.is_method_pointer = self.calc_is_method_pointer()
        self.array_size = self.calc_array_size()

    def as_reference(self, parent):
        if parent is None:
            result = b''
        else:
            result = parent + b'.'

        result = result + self.name_short
        return result

    def calc_name_short(self):
        result = self.name
        result = result.replace(b'*', b'')
        result = result.replace(b'(', b'')
        result = result.replace(b')', b'')
        index = result.find(b'[')
        if index != -1:
            result = result[:index]
        return result

    def calc_is_pointer(self):
        return (b'*' in self.name)

    def calc_is_method_pointer(self):
        return (b'(*' in self.name)

    def calc_array_size(self):
        result = 1
        temp = self.name
        index = temp.find(b'[')

        while index != -1:
            index_2 = temp.find(b']')
            result *= int(temp[index + 1:index_2])
            temp = temp[index_2 + 1:]
            index = temp.find(b'[')

        return result


class DNAStruct:
    """
    DNAType is a C-type structure stored in the DNA
    """
    __slots__ = (
        "dna_type",
        "fields",
        )

    def __init__(self):
        self.fields = []

    def field_get(self, header, handle, path,
                  use_nil=True, use_str=True):
        assert(type(path) == bytes)
        splitted = path.partition(b'.')
        name = splitted[0]
        rest = splitted[2]
        offset = 0
        for field in self.fields:
            fname = field[1]
            if fname.name_short == name:
                handle.seek(offset, os.SEEK_CUR)
                ftype = field[0]
                if len(rest) == 0:

                    if fname.is_pointer:
                        return DNA_IO.read_pointer(handle, header)
                    elif ftype[0] == b'int':
                        return DNA_IO.read_int(handle, header)
                    elif ftype[0] == b'short':
                        return DNA_IO.read_short(handle, header)
                    elif ftype[0] == b'float':
                        return DNA_IO.read_float(handle, header)
                    elif ftype[0] == b'char':
                        if use_str:
                            if use_nil:
                                return DNA_IO.read_string0(handle, fname.array_size)
                            else:
                                return DNA_IO.read_string(handle, fname.array_size)
                        else:
                            if use_nil:
                                return DNA_IO.read_bytes0(handle, fname.array_size)
                            else:
                                return DNA_IO.read_bytes(handle, fname.array_size)

                else:
                    return ftype[2].field_get(header, handle, rest,
                                              use_nil=use_nil, use_str=use_str)

            else:
                offset += field[2]

        return None

    def field_set(self, header, handle, path, value):
        assert(type(path) == bytes)
        splitted = path.partition(b'.')
        name = splitted[0]
        rest = splitted[2]
        offset = 0
        for field in self.fields:
            fname = field[1]
            if fname.name_short == name:
                handle.seek(offset, os.SEEK_CUR)
                ftype = field[0]
                if len(rest) == 0:
                    if ftype[0] == b'char':
                        if type(value) is str:
                            return DNA_IO.write_string(handle, value, fname.array_size)
                        else:
                            return DNA_IO.write_bytes(handle, value, fname.array_size)
                else:
                    return ftype[2].field_set(header, handle, rest, value)
            else:
                offset += field[2]

        return None


class DNA_IO:
    """
    Module like class, for read-write utility functions.

    Only stores static methods & constants.
    """

    __slots__ = ()

    # Methods for read/write,
    # these are only here to avoid clogging global-namespace

    @staticmethod
    def write_string(handle, astring, fieldlen):
        assert(isinstance(astring, str))
        stringw = ""
        if len(astring) >= fieldlen:
            stringw = astring[0:fieldlen]
        else:
            stringw = astring + '\0'
        handle.write(stringw.encode('utf-8'))

    @staticmethod
    def write_bytes(handle, astring, fieldlen):
        assert(isinstance(astring, (bytes, bytearray)))
        stringw = b''
        if len(astring) >= fieldlen:
            stringw = astring[0:fieldlen]
        else:
            stringw = astring + b'\0'
        print(stringw)
        print(handle)
        handle.write(stringw)

    _STRING = [struct.Struct("%ds" % i) for i in range(0, 2048)]

    @staticmethod
    def _string_struct(length):
        if length < len(DNA_IO._STRING):
            st = DNA_IO._STRING[length]
        else:
            st = struct.Struct("%ds" % length)
        return st

    @staticmethod
    def read_bytes(handle, length):
        st = DNA_IO._string_struct(length)
        data = st.unpack(handle.read(st.size))[0]
        return data

    @staticmethod
    def read_bytes0(handle, length):
        st = DNA_IO._string_struct(length)
        data = st.unpack(handle.read(st.size))[0]
        return DNA_IO.read_data0(data, 0)

    @staticmethod
    def read_string(handle, length):
        return DNA_IO.read_bytes(handle, length).decode('utf-8')

    @staticmethod
    def read_string0(handle, length):
        return DNA_IO.read_bytes0(handle, length).decode('utf-8')

    @staticmethod
    def read_data0(data, offset):
        """
        Reads a zero terminating String from a file handle
        """
        add = data.find(b'\0', offset) - offset
        st = DNA_IO._string_struct(add)
        return st.unpack_from(data, offset)[0]

    USHORT = struct.Struct("<H"), struct.Struct(">H")

    @staticmethod
    def read_ushort(handle, fileheader):
        st = DNA_IO.USHORT[fileheader.endian_index]
        return st.unpack(handle.read(st.size))[0]

    UINT = struct.Struct("<I"), struct.Struct(">I")

    @staticmethod
    def read_uint(handle, fileheader):
        st = DNA_IO.UINT[fileheader.endian_index]
        return st.unpack(handle.read(st.size))[0]

    SINT = struct.Struct("<i"), struct.Struct(">i")

    @staticmethod
    def read_int(handle, fileheader):
        st = DNA_IO.SINT[fileheader.endian_index]
        return st.unpack(handle.read(st.size))[0]

    @staticmethod
    def read_float(handle, fileheader):
        return struct.unpack(fileheader.endian_str + "f", handle.read(4))[0]

    SSHORT = struct.Struct("<h"), struct.Struct(">h")

    @staticmethod
    def read_short(handle, fileheader):
        st = DNA_IO.SSHORT[fileheader.endian_index]
        return st.unpack(handle.read(st.size))[0]

    ULONG = struct.Struct("<Q"), struct.Struct(">Q")

    @staticmethod
    def read_ulong(handle, fileheader):
        st = DNA_IO.ULONG[fileheader.endian_index]
        return st.unpack(handle.read(st.size))[0]

    @staticmethod
    def read_pointer(handle, header):
        """
        reads an pointer from a file handle
        the pointer size is given by the header (BlendFileHeader)
        """
        if header.pointer_size == 4:
            st = DNA_IO.UINT[header.endian_index]
            return st.unpack(handle.read(st.size))[0]
        if header.pointer_size == 8:
            st = DNA_IO.ULONG[header.endian_index]
            return st.unpack(handle.read(st.size))[0]


class DNAField:
    """
    DNAField is a coupled DNAType and DNAName
    """
    __slots__ = (
        "name",
        "dna_type",
        )

    def __init__(self, dna_type, name):
        self.dna_type = dna_type
        self.name = name

    def size(self, header):
        if self.name.is_pointer or self.name.is_method_pointer:
            return header.pointer_size * self.name.array_size
        else:
            return self.dna_type.size * self.name.array_size
