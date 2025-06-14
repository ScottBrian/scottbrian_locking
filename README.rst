==================
scottbrian-locking
==================

Intro
=====

The SELock is a shared/exclusive lock that you can use to coordinate
read and write access to a resource in a multithreaded application.

:Example: use SELock to coordinate access to a resource

>>> from scottbrian_locking import se_lock as sel
>>> a_lock = sel.SELock()
>>> # Get lock in exclusive mode
>>> with sel.SELockExcl(a_lock):
...     msg = 'lock obtained exclusive'
>>> print(msg)
lock obtained exclusive

>>> # Get lock in shared mode
>>> with sel.SELockShare(a_lock):
...     msg = 'lock obtained shared'
>>> print(msg)
lock obtained shared


.. image:: https://img.shields.io/badge/security-bandit-yellow.svg
    :target: https://github.com/PyCQA/bandit
    :alt: Security Status

.. image:: https://readthedocs.org/projects/pip/badge/?version=stable
    :target: https://pip.pypa.io/en/stable/?badge=stable
    :alt: Documentation Status


Installation
============

Windows:

``pip install scottbrian-locking``


Development setup
=================

See tox.ini

Release History
===============

* 1.0.0
    * Initial release

* 1.1.0
    * Add RELockObtain context manager
    * support python 3.11

* 2.0.0
    * Add obtain_tf to context manager
    * Add allow_recursive_obtain
    * Delete setup.cfg
    * Make consistent log and error messages
    * Support python 3.12
    * Drop support for python < 3.12

* 2.0.1
    * Fix documentation
        * change docs/source/index.rst
        * change docs/requirements.txt
        * change readthedoc.yml

* 2.0.2
    * Fix verify_lock to refresh lock_info
    * Fix thread name in release granted log message

* 2.1.0
    * Support python 3.13

Meta
====

Scott Tuttle

Distributed under the MIT license. See ``LICENSE`` for more information.


Contributing
============

1. Fork it (<https://github.com/yourname/yourproject/fork>)
2. Create your feature branch (`git checkout -b feature/fooBar`)
3. Commit your changes (`git commit -am 'Add some fooBar'`)
4. Push to the branch (`git push origin feature/fooBar`)
5. Create a new Pull Request


