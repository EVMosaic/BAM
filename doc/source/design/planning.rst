
##########
  Pipeline
##########

**The Story Tool**

*This is the over arching goal of the project.*

- Asset Management *Manage Files & Content*
- Project Management *Manage People & Tasks*
- Automated Tasks *Manage Geneated Content*


.. note::

   Design Goals

   ...this is a tool, not a framework,
   for anyone making animation(s) with Blender.


- Handle multiple projects.
- Foresee use of other tools (as well as Blender), in the work-flow.
- Support multi-site/distributed work-flow.
- Support **some** of the functionality in the Blender-Cloud.
- Design to **allow** for swappable modular components, even if we end up sticking with single technologies.



Asset Managment
===============

- Assets <-> Users
  - Revisions
  - Variations


Architecture Overview
---------------------

Server
^^^^^^

- File asset
- Tools (blend file packer, evaluate sequencer, visualize deps, automated tasks ...)
- Public API (web service), *communicates with client.*

Client
^^^^^^

- Interface GUI/CLI (Blender/Web-UI also)
- Tools (manage files on the client, cache.)
- Local files (models, images)


User Stories
------------


Layout Artist
^^^^^^^^^^^^^

Mathieu has to update the camera motion in an existing shot in layout stage.

Since he's in the middle of the project, he loads Blender and accesses the 'Recent Projects Menu'
Which shows an interface to open the file he's looking for.
In this case someone modified a prop, giving the message "Shader changed, by Pablo".
Which he updates because it only takes a few seconds.

Now he's able to edit the camera and save his work (exit Blender, reopen...etc)
When he's happy with the changes he opens the file menu **File -> BAM -> Commit Changes**

This prompts him with a dialog showing a list of the changed files.
He enters a commit message explaining the change and presses **Commit**.

a progress bar appears while the data is being uploaded.

He finally receives confirmation that the commit uploaded correctly.


Animator
^^^^^^^^

Hjalti opens the project management web site and finds he's been assigned a new shot to animate.

He opens Blender and selects **File -> BAM -> Load**,
this prompts him with a browser which he uses to locate the shot,
which he can easily identify by the name: ``shot_012_anim.blend``

He confirms the action, which shows a download progress bar which immediately loads the file in Blender.

He is presented with a low poly scene containing rigs with the characters in the shot and the props they interact with.
as well as a low resolution version of the environment.

He can work on the animation, and modify the file, and commit... *as Mathieu did*


Editor
^^^^^^

Mathieu is going through his daily review of the edit in Blender,

He opens the edit blend **File -> BAM -> Recent Files -> Edit**,

This shows the sequencer view with each shot as a strip,

He can add a new shot into the edit **Sequencer Header -> Add -> BAM Shot**

.. note::

   exactly how this is done is yet to be decieded,

   however the shots will be created and managed on the server (likely via a web-ui)

A popup will appear with a list of shots which can be selected to add.

At this point the sequencer can be used as usual,

**However** the clip in the sequencer is now **the** reference for length/timing of the shot,
its values are propagated to the server (*once committed*).


Implementation Details
----------------------

This document describes the layout for Blender pipeline.


Overview
^^^^^^^^

- Use SVN for internal storage.
- SVN repository is for internal storage (but keep usable as *last resort*)
- Support extracting single ``.blend`` file, and committing it back (without a full checkout),
  useful for remote artists.


SVN Commit Abstraction
^^^^^^^^^^^^^^^^^^^^^^

Motivation:

Artists need to be able to work on jobs without downloading entire repository.



Workflow:

- Select an asset to *checkout* (Likely via a web-ui/blender-ui).
- Download the asset and its dependencies (web/cli/blender-ui).
- Modify data locally (images, 3d... text... etc).
- Submit task back with commit log (blender-ui/cli/web?).
  (Server handles commit).



Technical details:

- Server handles SVN integration which is hidden from the client.
- The job submission and editing workflow is handled by client/server,
  Server creates binary blobs for the bundles,
  client handles download and create a usable directory for editing.
- Path remapping of ``.blend`` files must be handled
  (in both directions, likely using ``blendfile.py``).
- Use cache on client to avoid re-downloading the same resources.


Components
----------

Client
^^^^^^

- UI (list + checkout (remote assets), edit + commit (local assets))
  - CLI (command line tool for low level access, scripts TD can use... etc)
  - Blender/Integrated UI
  - Web-UI (browse assets, limited access).

- Tools
  - browse remote repo
  - downloader (simple zip)
  - checkout/commit workflow (check what to download, commit whats changed, manage cache internally avoid re-download)

- Data
  - Files/Assets (blend files, textures)
  - Cache (physics assets which can be regenerated on the server)


Server
^^^^^^

- Write blend file extractor / packager.
- Write online SVN browser.
- ... TODO



Project Management
==================

Use phabricator! DONE :D


Automated Tasks
===============


Components
----------

There are 2 types of tasks to be automated.

* User submitted tasks.
* Tasks generated by events such as commit hooks, finished rendering... etc.

Automated tasks are broken into 3 steps.

* Creation (API/CLI/GUI)
* Scheduling/queueing (Managed by the server)
* Execution/job management (Controlled via the server, though API's & UI's)


User Stories
------------

Heres a list of tasks we would expect the system to support

- Generating Renderfarm Preview
- Low resolution textures for animation
- High Resolution Simulation (hair, smoke)
- Final Render a Scene
- OpenGL Preview Every Shot
- Bundle a Blend file into a ZIP
- Synchronizing Data (SVN/Database... repositories... backups)
- Consistency checks (automated tasks to validate the state of the project)
- Blend file hygiene/lint (unused datablocks, images not used anywhere)
- Building Blender


Implementation
--------------

We plan to develop a very simple system leveraging existing technologies.


Dashboard
^^^^^^^^^

UI (web based), allows manual creation of tasks.


Server
^^^^^^

Backend connected to database and scheduler, managing & assigning jobs to workers.


Worker
^^^^^^

Simple client, exposes control of the machine via an API.
