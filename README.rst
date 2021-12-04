==================
scottbrian-locking
==================

Intro
=====

The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

:Example: use SELock to coordinate access to a shared resource



>>> from scottbrian_locking.se_lock import SELock
>>> a_lock = SELock()

>>> # Get lock in exclusive mode
>>> with a_lock(SELock.EXCL):  # write to a
>>>     a = 1
>>>     print(a)

>>> # Get lock in shared mode
>>> with a_lock(SELock.SHARE):  # read a
>>>     print(a)




.. image:: https://img.shields.io/badge/security-bandit-yellow.svg
    :target: https://github.com/PyCQA/bandit
    :alt: Security Status

.. image:: https://readthedocs.org/projects/pip/badge/?version=stable
    :target: https://pip.pypa.io/en/stable/?badge=stable
    :alt: Documentation Status


Installation
============

Linux:

``pip install scottbrian-locking``


Development setup
=================

See tox.ini

Release History
===============

* 1.0.0
    * Initial release


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


