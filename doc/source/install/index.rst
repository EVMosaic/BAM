Installation and requirements
#############################

How to get the system up and running.

Webservice
==========

The web-service is a simple web app based on the Flask framework, plus a few extensions.
In order to get it up and running.

- Create a virtual environment
- Activate the virtual environment
- Install dependencies with ``pip3 install -r requirements.txt``
- Run the service

To learn about the web-service usage, check out the proper (non existing) section.


Client
======

In order to use the `bam` command in your terminal, you can add this file in any of
your BIN paths and call it `bam`. Don't forget to give it +x permissions. ::

    #!/bin/sh
    exec python3 /absolute/path/to/bam/bam_cli.py "$@"

As you can see, the file links to your bam.py file, so make sure that one is right!
