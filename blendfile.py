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


######################################################
# Importing modules
######################################################
import os
import struct
import logging
import gzip
import tempfile
import sys

log = logging.getLogger("blendfile")
FILE_BUFFER_SIZE = 1024 * 1024


######################################################
# module global routines
######################################################
# read routines
# open a filename
# determine if the file is compressed
# and returns a handle
def openBlendFile(filename, access="rb"):
    """Opens a blend file for reading or writing pending on the access
    supports 2 kind of blend files. Uncompressed and compressed.
    Known issue: does not support packaged blend files
    """
    handle = open(filename, access)
    magic = ReadString(handle, 7)
    if magic == "BLENDER":
        log.debug("normal blendfile detected")
        handle.seek(0, os.SEEK_SET)
        res = BlendFile(handle)
        res.is_compressed = False
        res.filepath_orig = filename
        return res
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
        res = BlendFile(handle)
        res.is_compressed = True
        res.filepath_orig = filename
        return res


def closeBlendFile(afile):
    """close the blend file
    writes the blend file to disk if changes has happened"""
    handle = afile.handle
    if afile.is_compressed:
        log.debug("close compressed blend file")
        handle.seek(os.SEEK_SET, 0)
        log.debug("compressing started")
        fs = gzip.open(afile.filepath_orig, "wb")
        data = handle.read(FILE_BUFFER_SIZE)
        while data:
            fs.write(data)
            data = handle.read(FILE_BUFFER_SIZE)
        fs.close()
        log.debug("compressing finished")

    handle.close()


######################################################
#    Write a string to the file.
######################################################
def WriteString(handle, astring, fieldlen):
    assert(isinstance(astring, str))
    stringw = ""
    if len(astring) >= fieldlen:
        stringw = astring[0:fieldlen]
    else:
        stringw = astring + '\0'
    handle.write(stringw.encode('utf-8'))


def WriteBytes(handle, astring, fieldlen):
    assert(isinstance(astring, (bytes, bytearray)))
    stringw = b''
    if len(astring) >= fieldlen:
        stringw = astring[0:fieldlen]
    else:
        stringw = astring + b'\0'
    print(stringw)
    print(handle)
    handle.write(stringw)


######################################################
#    ReadString reads a String of given length from a file handle
######################################################
STRING = []
for i in range(0, 2048):
    STRING.append(struct.Struct(str(i) + "s"))


def ReadString(handle, length):
    st = STRING[length]
    return st.unpack(handle.read(st.size))[0].decode("iso-8859-1")

######################################################
#    ReadString0 reads a zero terminating String from a file handle
######################################################
ZEROTESTER = 0
if sys.version_info < (3, 0):
    ZEROTESTER = "\0"


def ReadString0(data, offset):
    add = 0

    while data[offset+add] != ZEROTESTER:
        add += 1
    if add < len(STRING):
        st = STRING[add]
        S = st.unpack_from(data, offset)[0].decode("iso-8859-1")
    else:
        S = struct.Struct(str(add) + "s").unpack_from(data, offset)[0].decode("iso-8859-1")
    return S

######################################################
#    ReadUShort reads an unsigned short from a file handle
######################################################
USHORT = [struct.Struct("<H"), struct.Struct(">H")]
def ReadUShort(handle, fileheader):
    us = USHORT[fileheader.endian_index]
    return us.unpack(handle.read(us.size))[0]


######################################################
#    ReadUInt reads an unsigned integer from a file handle
######################################################
UINT = [struct.Struct("<I"), struct.Struct(">I")]
def ReadUInt(handle, fileheader):
    us = UINT[fileheader.endian_index]
    return us.unpack(handle.read(us.size))[0]


def ReadInt(handle, fileheader):
    return struct.unpack(fileheader.endian_str + "i", handle.read(4))[0]


def ReadFloat(handle, fileheader):
    return struct.unpack(fileheader.endian_str + "f", handle.read(4))[0]


SSHORT = [struct.Struct("<h"), struct.Struct(">h")]
def ReadShort(handle, fileheader):
    us = SSHORT[fileheader.endian_index]
    return us.unpack(handle.read(us.size))[0]


ULONG = [struct.Struct("<Q"), struct.Struct(">Q")]
def ReadULong(handle, fileheader):
    us = ULONG[fileheader.endian_index]
    return us.unpack(handle.read(us.size))[0]


######################################################
#    ReadPointer reads an pointerfrom a file handle
#    the pointersize is given by the header (BlendFileHeader)
######################################################
def ReadPointer(handle, header):
    if header.pointer_size == 4:
        us = UINT[header.endian_index]
        return us.unpack(handle.read(us.size))[0]
    if header.pointer_size == 8:
        us = ULONG[header.endian_index]
        return us.unpack(handle.read(us.size))[0]


######################################################
#    Align alligns the filehandle on 4 bytes
######################################################
def align(offset, by):
    n = by - 1
    return (offset + n) & ~n


######################################################
# module classes
######################################################


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
        while block.code != "ENDB":
            if block.code == "DNA1":
                self.catalog = DNACatalog(self.header, block, handle)
            else:
                handle.seek(block.size, os.SEEK_CUR)

            self.blocks.append(block)
            self.code_index.setdefault(block.code, []).append(block)

            block = BlendFileBlock(handle, self)
        self.is_modified = False
        self.blocks.append(block)

    def find_blocks_from_code(self, code):
        if len(code) == 2:
            code = code
        if code not in self.code_index:
            return []
        return self.code_index[code]

    def find_block_from_offset(self, offset):
        for block in self.blocks:
            if block.addr_old == offset:
                return block
        return None

    def close(self):
        if not self.is_modified:
            self.handle.close()
        else:
            closeBlendFile(self)


class BlendFileBlock:
    """
    Instance of a struct.
    """
    __slots__ = (
        # file handle
        "file",
        "code",
        "size",
        "addr_old",
        "sdna_index",
        "count",
        "file_offset",
        )
    def __init__(self, handle, afile):
        self.file = afile
        header = afile.header

        data = handle.read(afile.block_header_struct.size)
        # header size can be 8, 20, or 24 bytes long
        # 8: old blend files ENDB block (exception)
        # 20: normal headers 32 bit platform
        # 24: normal headers 64 bit platform
        if len(data) > 15:

            blockheader = afile.block_header_struct.unpack(data)
            self.code = blockheader[0].decode().split("\0")[0]
            if self.code != "ENDB":
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
            self.code = blockheader[0].decode().split("\0")[0]
            self.size = 0
            self.addr_old = 0
            self.sdna_index = 0
            self.count = 0
            self.file_offset = 0

    def get(self, path):
        dna_index = self.sdna_index
        dna_struct = self.file.catalog.structs[dna_index]
        self.file.handle.seek(self.file_offset, os.SEEK_SET)
        return dna_struct.field_get(self.file.header, self.file.handle, path)

    def set(self, path, value):
        dna_index = self.sdna_index
        dna_struct = self.file.catalog.structs[dna_index]
        self.file.handle.seek(self.file_offset, os.SEEK_SET)
        self.file.is_modified = True
        return dna_struct.field_set(self.file.header, self.file.handle, path, value)


######################################################
#    magic = str
#    pointer_size = int
#    is_little_endian = bool
#    version = int
######################################################
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
        pointer_size_id = values[1].decode()
        if pointer_size_id == "-":
            self.pointer_size = 8
        elif pointer_size_id == "_":
            self.pointer_size = 4
        else:
            assert(0)
        endian_id = values[2].decode()
        if endian_id == "v":
            self.is_little_endian = True
            self.endian_str = "<"
            self.endian_index = 0
        elif endian_id == "V":
            self.is_little_endian = False
            self.endian_index = 1
            self.endian_str = ">"
        else:
            assert(0)

        tVersion = values[3].decode()
        self.version = int(tVersion)

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
        "structs",
        )

    def __init__(self, header, block, handle):
        log.debug("building DNA catalog")
        shortstruct = USHORT[header.endian_index]
        shortstruct2 = struct.Struct(str(USHORT[header.endian_index].format.decode() + 'H'))
        intstruct = UINT[header.endian_index]
        data = handle.read(block.size)
        self.names = []
        self.types = []
        self.structs = []

        offset = 8
        names_len = intstruct.unpack_from(data, offset)[0]
        offset += 4

        log.debug("building #%d names" % names_len)
        for i in range(names_len):
            tName = ReadString0(data, offset)
            offset = offset + len(tName) + 1
            self.names.append(DNAName(tName))
        del names_len

        offset = align(offset, 4)
        offset += 4
        types_len = intstruct.unpack_from(data, offset)[0]
        offset += 4
        log.debug("building #"+str(types_len)+" types")
        for i in range(types_len):
            tType = ReadString0(data, offset)
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
            structure = DNAStructure(dna_type)
            self.structs.append(structure)

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
                structure.fields.append([fType, fName, fsize])


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
        "_SN",  # TODO, investigate why this is needed!
        )

    def __init__(self, aName):
        self.name = aName
        self.name_short = self.calc_name_short()
        self.is_pointer = self.calc_is_pointer()
        self.is_method_pointer = self.calc_is_method_pointer()
        self.array_size = self.calc_array_size()

    def as_reference(self, parent):
        if parent is None:
            result = ""
        else:
            result = parent + "."

        result = result + self.name_short
        return result

    def calc_name_short(self):
        result = self.name
        result = result.replace("*", "")
        result = result.replace("(", "")
        result = result.replace(")", "")
        index = result.find("[")
        if index != -1:
            result = result[:index]
        self._SN = result
        return result

    def calc_is_pointer(self):
        return self.name.find("*") > -1

    def calc_is_method_pointer(self):
        return self.name.find("(*") > -1

    def calc_array_size(self):
        result = 1
        temp = self.name
        index = temp.find("[")

        while index != -1:
            index_2 = temp.find("]")
            result *= int(temp[index + 1:index_2])
            temp = temp[index_2 + 1:]
            index = temp.find("[")

        return result


class DNAStructure:
    """
    DNAType is a C-type structure stored in the DNA
    """
    __slots__ = (
        "dna_type",
        "fields",
        )

    def __init__(self, aType):
        self.dna_type = aType
        aType[2] = self
        self.fields = []

    def field_get(self, header, handle, path):
        splitted = path.partition(".")
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
                        return ReadPointer(handle, header)
                    elif ftype[0] == "int":
                        return ReadInt(handle, header)
                    elif ftype[0] == "short":
                        return ReadShort(handle, header)
                    elif ftype[0] == "float":
                        return ReadFloat(handle, header)
                    elif ftype[0] == "char":
                        return ReadString(handle, fname.array_size)
                else:
                    return ftype[2].field_get(header, handle, rest)

            else:
                offset += field[2]

        return None

    def field_set(self, header, handle, path, value):
        splitted = path.partition(".")
        name = splitted[0]
        rest = splitted[2]
        offset = 0
        for field in self.fields:
            fname = field[1]
            if fname.name_short == name:
                handle.seek(offset, os.SEEK_CUR)
                ftype = field[0]
                if len(rest) == 0:
                    if ftype[0] == "char":
                        if type(value) is str:
                            return WriteString(handle, value, fname.array_size)
                        else:
                            return WriteBytes(handle, value, fname.array_size)
                else:
                    return ftype[2].field_set(header, handle, rest, value)
            else:
                offset += field[2]

        return None


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


# determine the relative production location of a blender path.basename
def blendPath2AbsolutePath(productionFile, blenderPath):
    productionFileDir = os.path.dirname(productionFile)
    if blenderPath.startswith("//"):
        relpath = blenderPath[2:]
        abspath = os.path.join(productionFileDir, relpath)
        return abspath

    return blenderPath
