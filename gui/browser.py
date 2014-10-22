#!/usr/bin/env python3
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import tkinter as tk

class PathHandle:
    """
    Manage storing path, cache json.
    """
    __slots__ = (
        "filepath",
        "json",
        "path",
        )
    def __init__(self):
        self.json = None
        # list of strings
        self.path = []

        self.filepath_set("gui.json")
        self.refresh()

    def refresh(self):
        with open(self.filepath, 'r') as fp:
            import json
            self.json = json.load(fp)
            print(self.json)

    def filepath_set(self, filepath):
        self.filepath = filepath

    def append_path(self, path_item):
        if path_item == "..":
            # maybe we should raise error
            if self.path:
                self.path.pop()

        else:
            self.path.append(path_item)

class Application(tk.Frame):
    def __init__(self, root):

        # local data
        self.item_list = []

        tk.Frame.__init__(self, root)

        self.canvas = tk.Canvas(root, borderwidth=0, background="#d9d9d9")
        self.frame = tk.Frame(self.canvas, background="#d9d9d9")
        self.vsb = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((4, 4), window=self.frame, anchor="nw", 
                                  tags="self.frame")

        self.frame.bind("<Configure>", self.OnFrameConfigure)

        self.path_handle = PathHandle()

        self.grid_members = []

        self.populate()


    def populate(self):
        '''Put in some fake data'''
        pass
        """
        for row in range(100):
            tk.Label(self.frame, text="%s" % row, width=3, borderwidth="1", 
                     relief="solid").grid(row=row, column=0)
            t="this is the second colum for row %s" %row
            tk.Label(self.frame, text=t).grid(row=row, column=1)
        """

        def calc_label_text():
            return "Path: " + "/".join(self.path_handle.path)

        def exec_path_folder(idname, but_path):
            self.path_handle.append_path(idname)
            print(self.path_handle.path)

            but_path.config(text=calc_label_text())
            # but_path.labelText = calc_label_text()
            # but_path.configure()

            self.configure()
            self.frame.configure()
            self.update()
            self.frame.update()
            print(dir(self.frame))
            # update!

        def exec_path_file(idname):
            # request the file?
            for b in self.grid_members:
                b.destroy()
            self.grid_members.clear()
            self.populate()



        def _():
            js = self.path_handle.json
            items = js.get("items_list")
            items.sort()
            if items is None:
                tk.Label(self, text="Empty")

            but_path = tk.Label(self.frame, text=calc_label_text())
            but_path.grid(row=0, column=1, sticky="nw")
            self.grid_members.append(but_path)

            row = 1
            import random
            random.shuffle(items)
            for name_short, name_full, item_type in [("..", "", "folder")] + items:
                print(name_short, name_full, item_type)
                if item_type == "folder":
                    but = tk.Label(self.frame, text="(/)", width=3, borderwidth="1", relief="solid")
                    but.grid(row=row, column=0)
                    self.grid_members.append(but)

                    def fn(idname=name_short, but_path=but_path): exec_path_folder(idname, but_path)

                    but = tk.Button(self.frame, text=name_short + "/", fg="green", command=fn)
                    but.grid(row=row, column=1, sticky="nw")
                    del fn

                    self.grid_members.append(but)
                    row += 1
            del name_short, name_full, item_type
            for name_short, name_full, item_type in items:
                print(name_short, name_full, item_type)
                if item_type == "file":
                    but = tk.Label(self.frame, text="(f)", width=3, borderwidth="1", relief="solid")
                    but.grid(row=row, column=0)
                    def fn(idname=name_short): exec_path_file(idname)
                    self.grid_members.append(but)


                    but = tk.Button(self.frame, text=name_short, fg="blue", command=fn)
                    but.grid(row=row, column=1, sticky="nw")
                    del fn

                    self.grid_members.append(but)
                    row += 1
            del name_short, name_full, item_type
            # import IPython; IPython.embed()

        _(); del _


    def OnFrameConfigure(self, event):
        '''Reset the scroll region to encompass the inner frame'''
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

root = tk.Tk()
app = Application(root).pack(side="top", fill="both", expand=True)
root.mainloop()

