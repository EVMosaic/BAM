#!/usr/bin/env python3

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


# ------------------
# Ensure module path
import os
import sys
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "exts"))
if path not in sys.path:
    sys.path.append(path)
del os, sys, path
# --------

# ------------------
# Ensure module path
import os
import sys
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if path not in sys.path:
    sys.path.append(path)
del os, sys, path
# --------


import os
CURRENT_DIR = os.path.normpath(os.path.dirname(__file__))
INDENT = "   "

import bam.cli

# start at this level
title_level = 2

title_chars = (
    '%',  # not from python docs!
    '#',
    '*',
    '=',
    '-',
    '^',
    '"',
    "'",  # not from python docs!
    )


def write_title(title, ch, double=False):
    ret = [""]
    line = ch * len(title)
    assert(len(ch) == 1)
    if double:
        ret.append(line)
    ret.append(title)
    ret.append(line)
    ret.append("")
    return ret


def text_unintend(text):
    text = text.lstrip("\n")
    text_newlines = text.split("\n")
    text_indent = len(text_newlines[0]) - len(text_newlines[0].lstrip(" \t"))
    return "\n".join([t[text_indent:] for t in text_newlines])


def options_as_rst(data):
    ret = []
    ret.extend([
        ".. list-table::",
        INDENT + ":widths: 2, 8",
        "",
        ])
    for c in data:
        c_name = c["name"]
        if isinstance(c_name, list):
            c_name = ", ".join(["``%s``" % w for w in c["name"]])
        c_metavar = c["metavar"]
        c_choices = c.get("choices")

        ret.extend([
            INDENT + "* - " + c_name + (" ``<%s>``" % c_metavar if c_metavar else ""),
            INDENT + "  - " + c["help"],
            ])
        if c_choices:
            ret.extend([
                "",
                INDENT + "    Possible choices: " + ", ".join(["``%s``" % w for w in c_choices])
                ])

        # print(c.keys())
    ret.append("")
    return ret


def subcommands_as_rst(data, commands, subcommands, level):
    # import IPython; IPython.embed()
    ret = []
    for c in data:
        name = c["name"]
        name_abbr = name.split(" ", 1)[0]
        if (subcommands is None) or (name_abbr in subcommands):
            commands_sub = commands + [name_abbr]
            ret.extend(write_title(" ".join(commands_sub[1:]), title_chars[level]))

            # ret.extend([".. program:: " + " ".join(commands_sub), ""])

            ret.extend([c["help"], ""])
            ret.extend(["::", "", INDENT + c["usage"], ""])
            ret.extend([text_unintend(c.get("description", "")), ""])

            ls = c.get("args")
            if ls:
                ret.extend(write_title("Positional arguments:", title_chars[level + 1]))
                ret.extend(options_as_rst(ls))

            ls = c.get("options")
            if ls:
                ret.extend(write_title("Options:", title_chars[level + 1]))
                # import IPython; IPython.embed()
                ret.extend(options_as_rst(c["options"]))

            ls = c.get("children")
            if ls:
                ret.extend(write_title("Subcommands:", title_chars[level + 1]))
                ret.extend(subcommands_as_rst(ls, commands_sub, None, level + 2))

            # ret.extend(["", "----", ""])
    return ret


def write_argparse_rst(title_level):
    program_root = "bam"

    parser = bam.cli.create_argparse()

    import sphinxarg.parser as sp
    data = sp.parse_parser(parser)

    # import pprint
    # pprint.pprint(data)

    with open(os.path.join(CURRENT_DIR, 'bam_cli_argparse.rst'), 'r', encoding='utf-8') as f:
        main_doc_split = f.read().split("\n")

    for i, l in enumerate(main_doc_split):
        l_strip = l.lstrip()
        if l_strip.startswith(".. %%"):
            # ".. %%(foo, bar)%%"  -->  ("foo", "bar")
            subcommands = tuple([w.strip() for w in l_strip[3:].strip("%()").split(",")])
            l = subcommands_as_rst(data["children"], [program_root], subcommands, title_level)
            main_doc_split[i] = "\n".join(l)

    return main_doc_split


def main():
    os.makedirs(os.path.join(CURRENT_DIR, "source", "reference"), exist_ok=True)
    with open(os.path.join(CURRENT_DIR, "source", "reference", "index.rst"), 'w') as f:
        ret = write_argparse_rst(3)
        f.write("\n".join(ret))


if __name__ == "__main__":
    main()
