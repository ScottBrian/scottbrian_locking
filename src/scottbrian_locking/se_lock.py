"""Module se_lock.

========
SELock
========

The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

:Example: use SELock to coordinate access to a shared resource



>>> from scottbrian_locking.se_lock import SELock
>>> a_lock = SELock()
>>> # Get lock in exclusive mode
>>> with a_lock(SELock.EXCL):  # write to a
>>>     a = 1
>>>     print(f'under exclusive lock, a = {a} ')
>>> # Get lock in shared mode
>>> with a_lock(SELock.SHARE):  # read a
>>>     print(f'under shared lock, a = {a}')
under exclusive lock, a = 1
under shared lock, a = 1


The se_lock module contains:

    1) SELock class with methods:

       a. obtain_lock
       b. release_lock
    2) Error exception classes:

       a. IncorrectModeSpecified

    3) SELock context manager

"""
########################################################################
# Standard Library
########################################################################
import logging
import threading
from typing import (Any, Final, NamedTuple, Type, TYPE_CHECKING)

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################


logger = logging.getLogger(__name__)


########################################################################
# SELock class exceptions
########################################################################
class SELockError(Exception):
    """Base class for exceptions in this module."""
    pass


class IncorrectModeSpecified(SELockError):
    """SELock exception for an incorrect mode specification."""
    pass


class AttemptedReleaseOfUnownedLock(SELockError):
    """SELock exception for attempted release of unowned lock."""
    pass


class ReleaseDetectedBadOwnerCount(SELockError):
    """SELock exception for bad owner count."""
    pass


class SELockOwnerNotAlive(SELockError):
    """SELock exception for lock owner not alive."""
    pass


class AttemptedReleaseByExclusiveWaiter(SELockError):
    """SELock exception for attempted release by exclusive waiter."""
    pass


class AttemptedReleaseBySharedWaiter(SELockError):
    """SELock exception for attempted release by shared waiter."""
    pass


########################################################################
# SELock Class
########################################################################
class SELock:
    """Provides a share/exclusive lock.

    The SELock class is used to coordinate read/write access to shared
    resources in a multi-threaded application.
    """

    class LockWaiter(NamedTuple):
        """NamedTuple for the lock request queue item."""
        mode: int
        event: threading.Event
        thread: threading.Thread

    SHARE: Final[int] = 1
    EXCL: Final[int] = 2

    RC_OK: Final[int] = 0

    ####################################################################
    # init
    ####################################################################
    def __init__(self) -> None:
        """Initialize an instance of the SELock class.

        :Example: instantiate an SELock

        >>> from scottbrian_locking.se_lock import SELock
        >>> se_lock = SELock()
        >>> print(se_lock)
        SELock()

        """
        ################################################################
        # Set vars
        ################################################################
        # the se_lock_lock is used to protect the owner_count which is
        # the actual locking mechanism
        self.se_lock_lock = threading.Lock()

        # the owner count is the lock mechanism:
        # A value of 0 means the lock is free.
        # A value greater than zero means the lock is held shared by
        # the number of threads indicated in the value.
        # A value of -1 means the lock is held exclusive.
        self.owner_count = 0

        # when a request is blocked for the lock, it is represented on
        # the owner_wait_q until the lock is available
        self.owner_wait_q: list[SELock.LockWaiter] = []

    ####################################################################
    # len
    ####################################################################
    def __len__(self) -> int:
        """Return the number of items in the owner_wait_q.

        Returns:
            The number of entries in the owner_wait_q as an integer

        :Example: instantiate a se_lock and get the len

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> print(len(a_lock))
        0

        """
        return len(self.owner_wait_q)

    ####################################################################
    # repr
    ####################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate a SELock and call repr on the instance

         >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> repr(a_lock)
        SELock()

        """
        if TYPE_CHECKING:
            __class__: Type[SELock]
        classname = self.__class__.__name__
        parms = ''  # placeholder for future parms

        return f'{classname}({parms})'

    ####################################################################
    # obtain
    ####################################################################
    def obtain(self, mode: int) -> None:
        """Method to obtain the SELock.

        Args:
            mode: specifies whether to obtain the lock in shared mode
                    (mode=SELock.SHARE) or exclusive mode
                    (mode=SELock.EXCL)

        Raises:
            IncorrectModeSpecified: For SELock obtain, the mode
                                    must be specified as either
                                    SELock.SHARE or SELock.EXCL.

        """
        with self.se_lock_lock:
            # if mode == SELock.EXCL:
            #     if self.owner_count == 0:
            #         self.owner_count = -1
            #         return
            # elif mode == SELock.SHARE:  # obtain share mode
            #     if ((self.owner_count == 0)
            #             or ((self.owner_count > 0) and (not self.owner_wait_q))):
            #         self.owner_count += 1
            #         return
            # else:
            #     raise IncorrectModeSpecified('For SELock obtain, the mode '
            #                                  'must be specified as either '
            #                                  'SELock.SHARE or SELock.EXCL')

            if mode not in (SELock.EXCL, SELock.SHARE):
                raise IncorrectModeSpecified(
                    'For SELock obtain, the mode must be specified as ' 
                    'either SELock.SHARE or SELock.EXCL')
            wait_event = threading.Event()
            self.owner_wait_q.append(
                SELock.LockWaiter(mode=mode,
                                  event=wait_event,
                                  thread=threading.current_thread())
            )
            if self.owner_wait_q[0].thread == threading.current_thread():
                return
            if mode == SELock.SHARE:
                exclusive_waiter_found = False
                for item in self.owner_wait_q:
                    if item.mode == SELock.EXCL:
                        exclusive_waiter_found = True
                        break
                if not exclusive_waiter_found:
                    return

        self.wait_for_lock(wait_event=wait_event)

    ####################################################################
    # wait_for_lock
    ####################################################################

    def wait_for_lock(self,
                      wait_event: threading.Event) -> None:
        """Method to wait for the SELock.

        Raises:
            SELockOwnerNotAlive:
              The owner of the SELock is not alive and will
              thus never release the lock.

        """
        while True:
            if wait_event.wait(timeout=10):
                return
            if not self.owner_wait_q[0].thread.is_alive():
                raise SELockOwnerNotAlive(
                    'The owner of the SELock is not alive and will '
                    'thus never release the lock.'
                )


    ####################################################################
    # release
    ####################################################################
    def release(self) -> None:
        """Method to release the SELock.

        Raises:
            AttemptedReleaseOfUnownedLock: A release of the SELock was
              attempted by thread {threading.current_thread()} but an
              entry on the owner-waiter queue was not found for that
              thread.
            AttemptedReleaseByExclusiveWaiter: A release of the SELock
              was attempted by thread {threading.current_thread()} but
              the entry found was still waiting for exclusive control
              of the lock.
            AttemptedReleaseBySharedWaiter: A release of the SELock was
              attempted by thread {threading.current_thread()} but the
              entry found was still waiting for shared control of the
              lock.
        """
        with self.se_lock_lock:
            # The owner_count is -1 if owned exclusive, or > 0 if owned
            # shared. The owner count should not be zero here since we
            # are releasing the lock.
            # if self.owner_count == 0:
            #     raise AttemptedReleaseOfUnownedLock(
            #         'A release of the SELock was attempted when the '
            #         'owner count was zero which indicates no owners '
            #         'currently hold the lock.')
            #
            # if self.owner_count > 0:
            #     self.owner_count -= 1  # one less shared owner
            # elif self.owner_count == -1:  # owned exclusive
            #     self.owner_count = 0
            # else:  # any other value is an error
            #     raise ReleaseDetectedBadOwnerCount(
            #         'An attempted release of the SELock discovered an '
            #         f'owner count of {self.owner_count} which is not a '
            #         'valid value.'
            #     )
            #
            # # if lock now free, handle any waiters
            # if (self.owner_count == 0) and self.owner_wait_q:
            #     if self.owner_wait_q[0].mode == SELock.EXCL:
            #         waiter = self.owner_wait_q.pop(0)
            #         self.owner_count = -1
            #         waiter.event.set()  # wake up the exclusive waiter
            #         return  # all done
            #     # if we are here, we have one of more share waiters
            #     while self.owner_wait_q:
            #         # if we come to an exclusive waiter, then we are
            #         # done for now
            #         if self.owner_wait_q[0].mode == SELock.EXCL:
            #             return
            #         waiter = self.owner_wait_q.pop(0)
            #         self.owner_count += 1
            #         waiter.event.set()  # wake up shared waiter

            excl_idx = -1
            item_idx = -1
            item_mode = SELock.EXCL
            for idx, item in enumerate(self.owner_wait_q):
                if (excl_idx == -1) and (item.mode == SELock.EXCL):
                    excl_idx = idx
                if item.thread == threading.current_thread():
                    item_idx = idx
                    item_mode = item.mode
                    break

            if item_idx == -1:  # if not found
                raise AttemptedReleaseOfUnownedLock(
                    'A release of the SELock was attempted by thread '
                    f'{threading.current_thread()} but an entry on the '
                    'owner-waiter queue was not found for that thread.')

            if item_idx != 0 and item_mode == SELock.EXCL:
                raise AttemptedReleaseByExclusiveWaiter(
                    'A release of the SELock was attempted by thread '
                    f'{threading.current_thread()} but the entry '
                    'found was still waiting for exclusive control of '
                    'the lock.')

            if (0 <= excl_idx < item_idx
                    and item_mode == SELock.SHARE):
                raise AttemptedReleaseBySharedWaiter(
                    'A release of the SELock was attempted by thread '
                    f'{threading.current_thread()} but the entry '
                    'found was still waiting for shared control of '
                    'the lock.')

            # release the lock
            del self.owner_wait_q[item_idx]

            # Grant ownership to next water if lock now available.
            # If the released mode was exclusive, then we know we just
            # released the first item on the queue and that the new
            # first is waiting and is now ready to wake up. If the new
            # first item if for exclusive control, only the first item
            # is resumed. If the first item is for shared control, it
            # and any subsequent shared items will be resumed.
            # If the released item was holding the lock as shared,
            # there may be additional shared items that will need to be
            # released before we can resume any items. If the released
            # item is shared and is the last of the group, then the new
            # first item will be for exclusive control in which can we
            # will grant control by resuming it.
            if self.owner_wait_q:
                if self.owner_wait_q[0].mode == SELock.EXCL:
                    # wake up the exclusive waiter
                    self.owner_wait_q[0].event.set()
                    return  # all done
                # If we are here, new first item is shared owner or
                # waiter. If we released exclusive, then we need to
                # resume one or more shared waiters. If we release
                # shared item, then we have no resumes to do yet.
                if item_mode == SELock.EXCL:
                    for item in self.owner_wait_q:
                        # if we come to an exclusive waiter, then we are
                        # done for now
                        if item.mode == SELock.EXCL:
                            return
                        # wake up shared waiter
                        item.event.set()

########################################################################
# SELock Context Manager for Shared Control
########################################################################
class SELockShare:
    """Class for SELockShared."""
    def __init__(self, se_lock: SELock) -> None:
        """Initialize shared lock context manager.

        Args:
            se_lock: instance of SELock

        """
        self.se_lock = se_lock

    def __enter__(self) -> None:
        """Context manager enter method."""
        self.se_lock.obtain(SELock.SHARE)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        self.se_lock.release()


########################################################################
# SELock Context Manager for Exclusive Control
########################################################################
class SELockExcl:
    """Class for SELockExcl."""

    def __init__(self, se_lock: SELock) -> None:
        """Initialize exclusive lock context manager.

        Args:
            se_lock: instance of SELock

        """
        self.se_lock = se_lock

    def __enter__(self) -> None:
        """Context manager enter method."""
        self.se_lock.obtain(SELock.EXCL)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        self.se_lock.release()
