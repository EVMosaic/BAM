User manual
###########

Using BAM is easy and fun! Provided that:

- you know how to use the command line of your os
- have some experience of how versioning systems work

Actually, this is not true, and in this guide we will explain to use BAM client from scracth.

.. hint:: Do not try to follow this page as a step-by-step tutorial, since its content might 
    be not completely coherent. The purpose of this manual is simply to explain the bam 
    workflow from the artist point of view.


Project Initialization
======================

In order to start working, we need to initialize a *project folder*. This operation should
be done only once. To create a project folder we need to open our terminal, and go to the
location where we want to store the project folder. Then we can type::

    bam init http://bam:5000/gooseberry

This command creates a ``gooseberry`` folder, containing information about the project. If
we enter the folder and use the ``ls`` comand command, we notice that it is empty, but if
we use the ``bam ls`` command we see a directory listing. This listing is provided by the
project server on the fly and it allows us to browse its content without having a local copy
on our machine.

The project folder can be moved anywhere, at any time. The exact ``bam init`` syntax is
available in the reference section.


Session creation
================

Once the project has been initialized and we are able to browse it remotely, we can proceed
checking out a file from it. For example we can type::

    bam co libs/envs/jungle/jungle_opening.blend

This creates a ``jungle_opening`` folder inside of our ``gooseberry`` project folder, which
will contain the ``jungle_opening.blend``, along with all its dependencies (library files,
textures, etc.) organized as follows. ::

    jungle_opening.blend
    relative/maps/path/map.png
    _absolute/maps/path/map.png

As we can see, folders starting with the ``_`` character map to an absolute path on the server,
while the other folders are relative to the file that was used to create the session.


Editing
=======

At this point we can edit any file in the session, and the system will keep track of our changes.
Currently we can:

- add new files to the session
- delete files
- edit files

We can not:

- rename files

In order to check what is the status of our edits, we can use ``bam st``, which will print a list
of edited, added and deleted files.

.. note:: Sessions are meant to create a contained and controlled working environment. We should
    never, ever refer to content that is outside of a session folder.


Committing changes
==================

Once we are happy with the changes we made to the session, we can sent id back to the server, which
will take care of versioning and merging it back into the project.
To commit a change, simply type::

    bam ci -m 'Updated trees'

If you are outside the session folder, you have to specify it::

    bam ci jungle_opening -m 'Updated trees'

After committing, we can keep working in the same session, and do further commits.


Updatding and existing session
==============================

It is possible to update and existing session by running::

    bam update

Make sure you have committed your files before updating.


