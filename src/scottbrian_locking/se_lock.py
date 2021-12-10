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
>>> with SELockExcl(a_lock):  # write to a
...     a = 1
...     print(f'under exclusive lock, a = {a}')
under exclusive lock, a = 1

>>> # Get lock in shared mode
>>> with SELockShare(a_lock):  # read a
...     print(f'under shared lock, a = {a}')
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
from scottbrian_utils.diag_msg import get_formatted_call_sequence as call_seq

########################################################################
# Local
########################################################################


########################################################################
# SELock class exceptions
########################################################################
class SELockError(Exception):
    """Base class for exceptions in this module."""
    pass


class AttemptedReleaseByExclusiveWaiter(SELockError):
    """SELock exception for attempted release by exclusive waiter."""
    pass


class AttemptedReleaseBySharedWaiter(SELockError):
    """SELock exception for attempted release by shared waiter."""
    pass


class AttemptedReleaseOfUnownedLock(SELockError):
    """SELock exception for attempted release of unowned lock."""
    pass


class SELockOwnerNotAlive(SELockError):
    """SELock exception for lock owner not alive."""
    pass


########################################################################
# SELock Class
########################################################################
class SELock:
    """Provides a share/exclusive lock.

    The SELock class is used to coordinate read/write access to shared
    resources in a multi-threaded application.
    """

    class LockOwnerWaiter(NamedTuple):
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
        # the se_lock_lock is used to protect the owner_waiter_q
        self.se_lock_lock = threading.Lock()

        # When a request is made for the lock, a LockOwnerWaiter object
        # is placed on the owner_waiter_q and remains there until a
        # lock release is done. The LockOwnerWaiter contains the
        # requester thread and an event. If the requester needs to wait
        # for the lock, the event will be set to wake the requester as
        # soon as the lock is assigned to the requester. Other waiting
        # requesters will periodically test the owner thread to ensure
        # the owner is still alive.
        self.owner_wait_q: list[SELock.LockOwnerWaiter] = []
        self.owner_count = 0
        self.excl_wait_count = 0

        # add a logger for the SELock
        self.logger = logging.getLogger(__name__)

        # Set a flag to use to make it easier to determine whether debug
        # logging is enabled
        self.debug_logging_enabled = self.logger.isEnabledFor(logging.DEBUG)

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
        'SELock()'

        """
        if TYPE_CHECKING:
            __class__: Type[SELock]
        classname = self.__class__.__name__
        parms = ''  # placeholder for future parms

        return f'{classname}({parms})'

    # ####################################################################
    # # obtain
    # ####################################################################
    # def obtain(self, mode: int) -> None:
    #     """Method to obtain the SELock.
    #
    #     Args:
    #         mode: specifies whether to obtain the lock in shared mode
    #                 (mode=SELock.SHARE) or exclusive mode
    #                 (mode=SELock.EXCL)
    #
    #     Raises:
    #         IncorrectModeSpecified: For SELock obtain, the mode
    #                                 must be specified as either
    #                                 SELock.SHARE or SELock.EXCL.
    #
    #     """
    #     if mode not in (SELock.EXCL, SELock.SHARE):
    #         raise IncorrectModeSpecified(
    #             'For SELock obtain, the mode must be specified as '
    #             'either SELock.SHARE or SELock.EXCL')
    #     if mode == SELock.EXCL:
    #         self.obtain_excl()
    #     else:
    #         self.obtain_share()

        # with self.se_lock_lock:
        #
        #     wait_event = threading.Event()
        #     self.owner_wait_q.append(
        #         SELock.LockOwnerWaiter(mode=mode,
        #                                event=wait_event,
        #                                thread=threading.current_thread())
        #     )
        #     if self.owner_wait_q[0].thread is threading.current_thread():
        #         if mode == SELock.EXCL:
        #             mode_text = 'exclusive'
        #         else:
        #             mode_text = 'shared'
        #         if self.debug_logging_enabled:
        #             self.logger.debug(
        #                 f'SELock granted immediate {mode_text} control to '
        #                 f'{threading.current_thread().name}, '
        #                 f'caller {call_seq(latest=1, depth=2)}'
        #             )
        #         return
        #     if mode == SELock.SHARE:
        #         exclusive_waiter_found = False
        #         for item in self.owner_wait_q:
        #             if item.mode == SELock.EXCL:
        #                 exclusive_waiter_found = True
        #                 break
        #         if not exclusive_waiter_found:
        #             if self.debug_logging_enabled:
        #                 self.logger.debug(
        #                     'SELock granted immediate shared control to '
        #                     f'{threading.current_thread().name}, '
        #                     f'caller {call_seq(latest=1, depth=2)}'
        #                 )
        #             return
        #
        # self.wait_for_lock(wait_event=wait_event)

    ####################################################################
    # obtain_excl
    ####################################################################
    def obtain_excl(self) -> None:
        """Method to obtain the SELock."""
        with self.se_lock_lock:

            wait_event = threading.Event()
            self.owner_wait_q.append(
                SELock.LockOwnerWaiter(mode=SELock.EXCL,
                                       event=wait_event,
                                       thread=threading.current_thread())
            )
            # if self.owner_wait_q[0].thread is threading.current_thread():
            if self.owner_count == 0:
                self.owner_count = -1

                if self.debug_logging_enabled:
                    self.logger.debug(
                        f'SELock granted immediate exclusive control to '
                        f'{threading.current_thread().name}, '
                        f'caller {call_seq(latest=1, depth=2)}'
                    )
                return

            self.excl_wait_count += 1

        self.wait_for_lock(wait_event=wait_event)

    ####################################################################
    # obtain_share
    ####################################################################
    def obtain_share(self) -> None:
        """Method to obtain the SELock."""
        with self.se_lock_lock:

            wait_event = threading.Event()
            self.owner_wait_q.append(
                SELock.LockOwnerWaiter(mode=SELock.SHARE,
                                       event=wait_event,
                                       thread=threading.current_thread())
            )
            # if self.owner_wait_q[0].thread is threading.current_thread():
            if self.excl_wait_count == 0 <= self.owner_count:
                self.owner_count += 1
                if self.debug_logging_enabled:
                    self.logger.debug(
                        f'SELock granted immediate shared control to '
                        f'{threading.current_thread().name}, '
                        f'caller {call_seq(latest=1, depth=2)}'
                    )
                return
            # exclusive_waiter_found = False
            # for item in self.owner_wait_q:
            #     if item.mode == SELock.EXCL:
            #         exclusive_waiter_found = True
            #         break
            # if not exclusive_waiter_found:
            #     self.owner_count += 1
            #     if self.debug_logging_enabled:
            #         self.logger.debug(
            #             'SELock granted immediate shared control to '
            #             f'{threading.current_thread().name}, '
            #             f'caller {call_seq(latest=1, depth=2)}'
            #         )
            #     return

        self.wait_for_lock(wait_event=wait_event)

    ####################################################################
    # wait_for_lock
    ####################################################################

    def wait_for_lock(self,
                      wait_event: threading.Event) -> None:
        """Method to wait for the SELock.

        Args:
            wait_event: event to wait on that will be set by the current
                owner upon lock release

        Raises:
            SELockOwnerNotAlive: The owner of the SELock is not alive
                and will thus never release the lock.

        """
        while True:
            if wait_event.wait(timeout=10):
                return

            # we check first without holding the se_lock_lock
            if not self.owner_wait_q[0].thread.is_alive():
                # We need to confirm while holding the se_lock_lock
                # to cover the case where we get the current lock owner
                # thread and call the is_alive method and just as we
                # call the lock is released by the owner who then exits
                # and is no longer alive. Meanwhile, the lock has a new
                # owner (possibly us) who is alive. Getting the
                # se_lock_lock here ensures the current lock owner is
                # not allowed to do a release while we are checking
                # whether it is alive.
                with self.se_lock_lock:
                    if not self.owner_wait_q[0].thread.is_alive():
                        raise SELockOwnerNotAlive(
                            'The owner of the SELock is not alive and '
                            'will thus never release the lock. '
                            f'Owner thread = {self.owner_wait_q[0]}')

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
            excl_idx = -1  # init to indicate exclusive req not found
            item_idx = -1  # init to indicate req not found
            item_mode = SELock.EXCL
            for idx, item in enumerate(self.owner_wait_q):
                if (excl_idx == -1) and (item.mode == SELock.EXCL):
                    excl_idx = idx
                if item.thread is threading.current_thread():
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
            if item_mode == SELock.EXCL:
                self.owner_count = 0
            else:
                self.owner_count -= 1
            # Grant ownership to next waiter if lock now available.
            # If the released mode was exclusive, then we know we just
            # released the first item on the queue and that the new
            # first item was waiting and is now ready to wake up. If the
            # new first item is for exclusive control then it will be
            # the only item to be resumed. If the new first item is for
            # shared control, it and any subsequent shared items up to
            # the next exclusive item or end of queue will be resumed.
            # If the released item was holding the lock as shared,
            # there may be additional shared items that will need to be
            # released before we can resume any items. If the released
            # item is shared and is the last of the group, then the new
            # first item will be for exclusive control in which can we
            # will grant control by resuming it (unless the last of the
            # group was also the last on the queue).
            if self.owner_wait_q:
                if self.owner_wait_q[0].mode == SELock.EXCL:
                    # wake up the exclusive waiter
                    self.owner_wait_q[0].event.set()
                    self.owner_count = -1
                    self.excl_wait_count -= 1
                    return  # all done
                # If we are here, new first item is either a shared
                # owner or a shared waiter. If we just released an
                # exclusive item, then we know that the new first shared
                # item was waiting and we now need to resume it and any
                # subsequent shared items to grant shared control.
                # If we had instead just released a shared item, then we
                # know the new first shared item and any subsequent
                # shared items were already previously resumed with
                # shared control, meaning we have nothing to do.
                if item_mode == SELock.EXCL:  # exclusive was released
                    for item in self.owner_wait_q:
                        # if we come to an exclusive waiter, then we are
                        # done for now
                        if item.mode == SELock.EXCL:
                            return
                        # wake up shared waiter
                        item.event.set()
                        self.owner_count += 1


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
        # self.se_lock.obtain(SELock.SHARE)
        self.se_lock.obtain_share()

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
        # self.se_lock.obtain(SELock.EXCL)
        self.se_lock.obtain_excl()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        self.se_lock.release()
