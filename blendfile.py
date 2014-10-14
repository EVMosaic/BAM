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
FILE_BUFFER_SIZE=1024*1024
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
        res.compressed=False
        res.originalfilename=filename
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
        res.compressed=True
        res.originalfilename=filename
        return res

def closeBlendFile(afile):
    """close the blend file
    writes the blend file to disk if changes has happened"""
    handle = afile.handle
    if afile.compressed:
        log.debug("close compressed blend file")
        handle.seek(os.SEEK_SET, 0)
        log.debug("compressing started")
        fs = gzip.open(afile.originalfilename, "wb")
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
    stringw=""
    if len(astring) >= fieldlen:
        stringw=astring[0:fieldlen]
    else:
        stringw=astring+'\0'
    handle.write(stringw.encode())

######################################################
#    ReadString reads a String of given length from a file handle
######################################################
STRING=[]
for i in range(0, 2048):
    STRING.append(struct.Struct(str(i)+"s"))
                  
def ReadString(handle, length):
    st = STRING[length]
    return st.unpack(handle.read(st.size))[0].decode("iso-8859-1")

######################################################
#    ReadString0 reads a zero terminating String from a file handle
######################################################
ZEROTESTER = 0
if sys.version_info < (3, 0):
    ZEROTESTER="\0"

def ReadString0(data, offset):
    add = 0

    while data[offset+add]!=ZEROTESTER:
        add+=1
    if add < len(STRING):
        st = STRING[add]
        S=st.unpack_from(data, offset)[0].decode("iso-8859-1")
    else:
        S=struct.Struct(str(add)+"s").unpack_from(data, offset)[0].decode("iso-8859-1")
    return S

######################################################
#    ReadUShort reads an unsigned short from a file handle
######################################################
USHORT=[struct.Struct("<H"), struct.Struct(">H")]
def ReadUShort(handle, fileheader):
    us = USHORT[fileheader.LittleEndiannessIndex]
    return us.unpack(handle.read(us.size))[0]

######################################################
#    ReadUInt reads an unsigned integer from a file handle
######################################################
UINT=[struct.Struct("<I"), struct.Struct(">I")]
def ReadUInt(handle, fileheader):
    us = UINT[fileheader.LittleEndiannessIndex]
    return us.unpack(handle.read(us.size))[0]

def ReadInt(handle, fileheader):
    return struct.unpack(fileheader.StructPre+"i", handle.read(4))[0]
def ReadFloat(handle, fileheader):
    return struct.unpack(fileheader.StructPre+"f", handle.read(4))[0]

SSHORT=[struct.Struct("<h"), struct.Struct(">h")]
def ReadShort(handle, fileheader):
    us = SSHORT[fileheader.LittleEndiannessIndex]
    return us.unpack(handle.read(us.size))[0]

ULONG=[struct.Struct("<Q"), struct.Struct(">Q")]
def ReadULong(handle, fileheader):
    us = ULONG[fileheader.LittleEndiannessIndex]
    return us.unpack(handle.read(us.size))[0]


######################################################
#    ReadPointer reads an pointerfrom a file handle
#    the pointersize is given by the header (BlendFileHeader)
######################################################
def ReadPointer(handle, header):
    if header.PointerSize == 4:
        us = UINT[header.LittleEndiannessIndex]
        return us.unpack(handle.read(us.size))[0]
    if header.PointerSize == 8:
        us = ULONG[header.LittleEndiannessIndex]
        return us.unpack(handle.read(us.size))[0]
    
######################################################
#    Allign alligns the filehandle on 4 bytes
######################################################
def Allign(offset):
    trim = offset % 4
    if trim != 0:
        offset = offset + (4-trim)
    return offset

######################################################
# module classes
######################################################

######################################################
#    BlendFile
#   - Header (BlendFileHeader)
#   - Blocks (FileBlockHeader)
#   - Catalog (DNACatalog)
######################################################
class BlendFile:
    
    def __init__(self, handle):
        log.debug("initializing reading blend-file")
        self.handle=handle
        self.Header = BlendFileHeader(handle)
        self.BlockHeaderStruct = self.Header.CreateBlockHeaderStruct()
        self.Blocks = []
        self.CodeIndex = {}
        
        aBlock = BlendFileBlock(handle, self)
        while aBlock.Code != "ENDB":
            if aBlock.Code == "DNA1":
                self.Catalog = DNACatalog(self.Header, aBlock, handle)
            else:
                handle.read(aBlock.Size)
#                handle.seek(aBlock.Size, os.SEEK_CUR) does not work with py3.0!
                
            self.Blocks.append(aBlock)
            
            if aBlock.Code not in self.CodeIndex:
                self.CodeIndex[aBlock.Code] = []
            self.CodeIndex[aBlock.Code].append(aBlock)
                
            aBlock = BlendFileBlock(handle, self)
        self.Modified=False
        self.Blocks.append(aBlock)
        
    def FindBlendFileBlocksWithCode(self, code):
        if len(code) == 2:
            code = code
        if code not in self.CodeIndex:
            return []
        return self.CodeIndex[code]
    
    def FindBlendFileBlockWithOffset(self, offset):
        for block in self.Blocks:
            if block.OldAddress == offset:
                return block;
        return None;
    
    def close(self):
        if not self.Modified:
            self.handle.close()
        else:
            closeBlendFile(self)
        
######################################################
#    BlendFileBlock
#   File=BlendFile
#   Header=FileBlockHeader
######################################################
class BlendFileBlock:
    def __init__(self, handle, afile):
        self.File = afile
        header = afile.Header

        bytes = handle.read(afile.BlockHeaderStruct.size)
        #header size can be 8, 20, or 24 bytes long
        #8: old blend files ENDB block (exception)
        #20: normal headers 32 bit platform
        #24: normal headers 64 bit platform
        if len(bytes)>15:

            blockheader = afile.BlockHeaderStruct.unpack(bytes)
            self.Code = blockheader[0].decode().split("\0")[0]
            if self.Code!="ENDB":
                self.Size = blockheader[1]
                self.OldAddress = blockheader[2]
                self.SDNAIndex = blockheader[3]
                self.Count = blockheader[4]
                self.FileOffset = handle.tell()
            else:
                self.Size = 0
                self.OldAddress = 0
                self.SDNAIndex = 0
                self.Count = 0
                self.FileOffset = 0
        else:
            blockheader = OLDBLOCK.unpack(bytes)
            self.Code = blockheader[0].decode().split("\0")[0]
            self.Size = 0
            self.OldAddress = 0
            self.SDNAIndex = 0
            self.Count = 0
            self.FileOffset = 0

    def Get(self, path):
        dnaIndex = self.SDNAIndex
        dnaStruct = self.File.Catalog.Structs[dnaIndex]
        self.File.handle.seek(self.FileOffset, os.SEEK_SET)
        return dnaStruct.GetField(self.File.Header, self.File.handle, path)

    def Set(self, path, value):
        dnaIndex = self.SDNAIndex
        dnaStruct = self.File.Catalog.Structs[dnaIndex]
        self.File.handle.seek(self.FileOffset, os.SEEK_SET)
        self.File.Modified=True
        return dnaStruct.SetField(self.File.Header, self.File.handle, path, value)

######################################################
#    BlendFileHeader allocates the first 12 bytes of a blend file
#    it contains information about the hardware architecture
#    Magic = str
#    PointerSize = int
#    LittleEndianness = bool
#    Version = int
######################################################
BLOCKHEADERSTRUCT={}
BLOCKHEADERSTRUCT["<4"] = struct.Struct("<4sIIII")
BLOCKHEADERSTRUCT[">4"] = struct.Struct(">4sIIII")
BLOCKHEADERSTRUCT["<8"] = struct.Struct("<4sIQII")
BLOCKHEADERSTRUCT[">8"] = struct.Struct(">4sIQII")
FILEHEADER = struct.Struct("7s1s1s3s")
OLDBLOCK=struct.Struct("4sI")
class BlendFileHeader:
    def __init__(self, handle):
        log.debug("reading blend-file-header")
        values = FILEHEADER.unpack(handle.read(FILEHEADER.size))
        self.Magic = values[0]
        tPointerSize = values[1].decode()
        if tPointerSize=="-":
            self.PointerSize=8
        elif tPointerSize=="_":
            self.PointerSize=4
        tEndianness = values[2].decode()
        if tEndianness=="v":
            self.LittleEndianness=True
            self.StructPre="<"
            self.LittleEndiannessIndex=0
        elif tEndianness=="V":
            self.LittleEndianness=False
            self.LittleEndiannessIndex=1
            self.StructPre=">"

        tVersion = values[3].decode()
        self.Version = int(tVersion)
        
    def CreateBlockHeaderStruct(self):
        return BLOCKHEADERSTRUCT[self.StructPre+str(self.PointerSize)]
        
######################################################
#    DNACatalog is a catalog of all information in the DNA1 file-block
#
#    Header=None
#    Names=None
#    Types=None
#    Structs=None
######################################################
class DNACatalog:

    def __init__(self, header, block, handle):
        log.debug("building DNA catalog")
        shortstruct = USHORT[header.LittleEndiannessIndex]
        shortstruct2 = struct.Struct(str(USHORT[header.LittleEndiannessIndex].format.decode()+'H'))
        intstruct = UINT[header.LittleEndiannessIndex]
        data = handle.read(block.Size)
        self.Names=[]
        self.Types=[]
        self.Structs=[]
        
        offset = 8;
        numberOfNames = intstruct.unpack_from(data, offset)[0]
        offset += 4
        
        log.debug("building #"+str(numberOfNames)+" names")
        for i in range(numberOfNames):
            tName = ReadString0(data, offset)
            offset = offset + len(tName) + 1
            self.Names.append(DNAName(tName))

        offset = Allign(offset)
        offset += 4
        numberOfTypes = intstruct.unpack_from(data, offset)[0]
        offset += 4
        log.debug("building #"+str(numberOfTypes)+" types")
        for i in range(numberOfTypes):
            tType = ReadString0(data, offset)
            self.Types.append([tType, 0, None])
            offset += len(tType)+1

        offset = Allign(offset)
        offset += 4
        log.debug("building #"+str(numberOfTypes)+" type-lengths")
        for i in range(numberOfTypes):
            tLen = shortstruct.unpack_from(data, offset)[0]
            offset = offset + 2
            self.Types[i][1] = tLen

        offset = Allign(offset)
        offset += 4
        
        numberOfStructures = intstruct.unpack_from(data, offset)[0]
        offset += 4
        log.debug("building #"+str(numberOfStructures)+" structures")
        for structureIndex in range(numberOfStructures):
            d = shortstruct2.unpack_from(data, offset)
            tType = d[0]
            offset += 4
            Type = self.Types[tType]
            structure = DNAStructure(Type)
            self.Structs.append(structure)

            numberOfFields = d[1]

            for fieldIndex in range(numberOfFields):
                d2 = shortstruct2.unpack_from(data, offset)
                fTypeIndex = d2[0]
                fNameIndex = d2[1]
                offset += 4
                fType = self.Types[fTypeIndex]
                fName = self.Names[fNameIndex]
                if fName.IsPointer or fName.IsMethodPointer:
                    fsize = header.PointerSize*fName.ArraySize
                else:
                    fsize = fType[1]*fName.ArraySize
                structure.Fields.append([fType, fName, fsize])

######################################################
#    DNAName is a C-type name stored in the DNA
#   Name=str
######################################################
class DNAName:

    def __init__(self, aName):
        self.Name = aName
        self.ShortName = self.DetermineShortName()
        self.IsPointer = self.DetermineIsPointer()
        self.IsMethodPointer = self.DetermineIsMethodPointer()
        self.ArraySize = self.DetermineArraySize()
        
    def AsReference(self, parent):
        if parent == None:
            Result = ""
        else:
            Result = parent+"."
            
        Result = Result + self.ShortName
        return Result

    def DetermineShortName(self):
        Result = self.Name;
        Result = Result.replace("*", "")
        Result = Result.replace("(", "")
        Result = Result.replace(")", "")
        Index = Result.find("[")
        if Index != -1:
            Result = Result[0:Index]
        self._SN = Result
        return Result
        
    def DetermineIsPointer(self):
        return self.Name.find("*")>-1

    def DetermineIsMethodPointer(self):
        return self.Name.find("(*")>-1

    def DetermineArraySize(self):
        Result = 1
        Temp = self.Name
        Index = Temp.find("[")

        while Index != -1:
            Index2 = Temp.find("]")
            Result*=int(Temp[Index+1:Index2])
            Temp = Temp[Index2+1:]
            Index = Temp.find("[")
        
        return Result

######################################################
#    DNAType is a C-type structure stored in the DNA
#
#    Type=DNAType
#    Fields=[DNAField]
######################################################
class DNAStructure:

    def __init__(self, aType):
        self.Type = aType
        aType[2] = self
        self.Fields=[]
        
    def GetField(self, header, handle, path):
        splitted = path.partition(".")
        name = splitted[0]
        rest = splitted[2]
        offset = 0;
        for field in self.Fields:
            fname = field[1]
            if fname.ShortName == name:
                handle.seek(offset, os.SEEK_CUR)
                ftype = field[0]
                if len(rest) == 0:
                    
                    if fname.IsPointer:
                        return ReadPointer(handle, header)
                    elif ftype[0]=="int":
                        return ReadInt(handle, header)
                    elif ftype[0]=="short":
                        return ReadShort(handle, header)
                    elif ftype[0]=="float":
                        return ReadFloat(handle, header)
                    elif ftype[0]=="char":
                        return ReadString(handle, fname.ArraySize)
                else:
                    return ftype[2].GetField(header, handle, rest)
        
            else:
                offset += field[2]

        return None
                            
    def SetField(self, header, handle, path, value):
        splitted = path.partition(".")
        name = splitted[0]
        rest = splitted[2]
        offset = 0;
        for field in self.Fields:
            fname = field[1]
            if fname.ShortName == name:
                handle.seek(offset, os.SEEK_CUR)
                ftype = field[0]
                if len(rest)==0:
                    if ftype[0]=="char":
                        return WriteString(handle, value, fname.ArraySize)
                else:
                    return ftype[2].SetField(header, handle, rest, value)
            else:
                offset += field[2]

        return None
                
            
        
######################################################
#    DNAField is a coupled DNAType and DNAName
#    Type=DNAType
#    Name=DNAName
######################################################
class DNAField:

    def __init__(self, aType, aName):
        self.Type = aType
        self.Name = aName
        
    def Size(self, header):
        if self.Name.IsPointer or self.Name.IsMethodPointer:
            return header.PointerSize*self.Name.ArraySize
        else:
            return self.Type.Size*self.Name.ArraySize

#determine the relative production location of a blender path.basename
def blendPath2AbsolutePath(productionFile, blenderPath):
    productionFileDir=os.path.dirname(productionFile)
    if blenderPath.startswith("//"):
        relpath=blenderPath[2:]
        abspath = os.path.join(productionFileDir, relpath)
        return abspath
        
    
    return blenderPath


