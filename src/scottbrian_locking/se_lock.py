"""Module se_lock.

========
SELock
========

The SELock is a shared/exclusive lock that you can use to coordinate
read and write access to a resource in a multithreaded application.

The SELock does not actually protect resources directly. Instead, the
SELock provide coordination by blocking threads when they request a lock
that is currently owned by another thread. That means the application
must ensure it appropriately requests the lock before attempting to read
from or write to a resource.

The application must first instatiate an SELock object that can be
accessed by the threads in the application. When a thread wants to read
from a resource, it requests the lock for shared mode. If the lock is
currently not held or is currently held in shared mode by other threads,
and no threads are waiting for the lock for exclusive mode,
the new request is granted immediately. For all other cases, the request
is queued and blocked until the lock become available.

When a thread wants to write to a resource, it requests the lock
in exclusive mode. If the lock is currently not held, the new request is
granted immediately. For all other cases, the request is queued and
blocked until the lock become available.

The application can instantiate a single lock to protect any number of
resources, or several locks for more granularity where each lock can
protect a single resource. The application design will need to consider
performance (more granularity may perform better) and
reliability (more granularity may lead to deadlock situtations).

The SELock provide two ways to use the lock:
    1) methods obtain_excl, obtain_share, and release
    2) context managers SELockExcl, SELockShare, and SELockObtain


:Example: use methods obtain_excl, obtain_share, and release to
          coordinate access to a resource

>>> from scottbrian_locking.se_lock import SELock
>>> a_lock = SELock()
>>> # Get lock in exclusive mode
>>> a_lock.obtain_excl()
>>> print('lock obtained in exclusive mode')
lock obtained in exclusive mode

>>> # release the lock
>>> a_lock.release()

>>> # Get lock in shared mode
>>> a_lock.obtain_share()
>>> print('lock obtained in shared mode')
lock obtained in shared mode

>>> # release the lock
>>> a_lock.release()


:Example: use SELockExcl and SELockShare context managers to coordinate
          access to a resource

>>> from scottbrian_locking.se_lock import (SELock, SELockExcl,
...                                         SELockShare)
>>> a_lock = SELock()
>>> # Get lock in exclusive mode
>>> with SELockExcl(a_lock):  # write access
...     msg = 'lock obtained exclusive'
>>> print(msg)
lock obtained exclusive

>>> # Get lock in shared mode
>>> with SELockShare(a_lock):  # read access
...     msg = 'lock obtained shared'
>>> print(msg)
lock obtained shared


:Example: use SELockObtain context managers to coordinate
          access to a resource

>>> from scottbrian_locking.se_lock import (SELock, SELockObtain,
...                                         SELockObtainMode)
>>> a_lock = SELock()
>>> # Get lock in exclusive mode
>>> with SELockObtain(a_lock, SELockObtainMode.Exclusive):  # write
...     msg = 'lock obtained exclusive'
>>> print(msg)
lock obtained exclusive

>>> # Get lock in shared mode
>>> with SELockObtain(a_lock, SELockObtainMode.Share):  # read
...     msg = 'lock obtained shared'
>>> print(msg)
lock obtained shared

"""

########################################################################
# Standard Library
########################################################################
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, StrEnum, auto
import logging
import threading
import time
from typing import Any, Final, NamedTuple, Optional, Type, TYPE_CHECKING, Union
from typing_extensions import TypeAlias

########################################################################
# Third Party
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence as call_seq
from scottbrian_utils.timer import Timer

########################################################################
# Local
########################################################################

########################################################################
# type aliases
########################################################################
OptIntFloat: TypeAlias = Optional[Union[int, float]]


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


class LockVerifyError(SELockError):
    """SELock exception for lock failed verify_lock request."""

    pass


class SELockInputError(SELockError):
    """SELock exception for input error."""

    pass


class SELockObtainTimeout(SELockError):
    """SELock exception for timeout on obtain request."""

    pass


class SELockOwnerNotAlive(SELockError):
    """SELock exception for lock owner not alive."""

    pass


class SELockAlreadyOwnedError(SELockError):
    """SELock exception for lock owner deadlocked with self."""

    pass


########################################################################
# SELockObtainMode
########################################################################
class SELockObtainMode(Enum):
    """Enum for SELockObtain to specify shared or exclusive control."""

    Share = auto()
    Exclusive = auto()


class LockItem(NamedTuple):
    """NamedTuple for the lock items returned by get_queue_items."""

    mode: SELockObtainMode
    event_flag: bool
    thread: threading.Thread


class LockInfo(NamedTuple):
    """NamedTuple for lock info returned by get_info"""

    queue: list[LockItem]
    owner_count: int
    excl_wait_count: int


########################################################################
# SELock Class
########################################################################
class SELock:
    """Provides a share/exclusive lock.

    The SELock class is used to coordinate read/write access to
    resources in a multithreaded application.

    """

    class ReqType(StrEnum):
        """Enum class for request type."""

        Exclusive = "SELock exclusive obtain request"
        ExclusiveRecursive = "SELock exclusive recursive obtain request"
        Share = "SELock share obtain request"
        Release = "SELock release request"

    class _Mode(Enum):
        """Enum class for lock mode."""

        SHARE = auto()
        EXCL = auto()

    class _LockOwnerWaiter(NamedTuple):
        """NamedTuple for the lock request queue item."""

        req_type: "SELock.ReqType"
        mode: "SELock._Mode"
        event: threading.Event
        thread: threading.Thread

    @dataclass
    class _OwnerWaiterDesc:
        """_OwnerWaiterDesc contains owner_waiter_q search results."""

        excl_idx: int
        item_idx: int
        item_mode: "SELock._Mode"

    WAIT_TIMEOUT: Final[float] = 3.0

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

        # When a request is made for the lock, a _LockOwnerWaiter object
        # is placed on the owner_waiter_q and remains there until a
        # lock release is done. The _LockOwnerWaiter contains the
        # requester thread and an event. If the lock is immediately
        # available, the requester is given back control and the event
        # will never need to be posted. If, instead, the lock is not
        # yet available, we will wait on the event until the owner of
        # the lock does a release, at which time the waiting event will
        # be posted and the requester will then be given back control as
        # the new owner.
        self.owner_wait_q: list[SELock._LockOwnerWaiter] = []

        self.owner_index: dict[str, int] = defaultdict(int)

        # The owner count is used to indicate whether the lock is
        # currently owned, and the mode. A value of zero indicates that
        # the lock is currently not owned. A negative value indicates
        # that the lock is owned in exclusive mode with value being the
        # number of recursive obtains by the same thread (if recursive
        # requests were made). A value greater than zero indicates that
        # the lock is owned in shared mode with the value being the
        # number of requesters that own the lock.
        self.owner_count = 0

        # The exclusive wait count is used to indicate the number of
        # exclusive requesters that are currently waiting for the lock.
        # This is used to quickly determine whether a new shared
        # requester needs to wait (excl_wait_count is greater than zero)
        # or can be granted shared ownership along with other shared
        # owners (excl_wait_count is zero).
        self.excl_wait_count = 0

        # add a logger for the SELock
        self.logger = logging.getLogger(__name__)

        # Flag to quickly determine whether debug logging is enabled
        self.debug_logging_enabled = self.logger.isEnabledFor(logging.DEBUG)

    ####################################################################
    # len
    ####################################################################
    def __len__(self) -> int:
        """Return the number of items on the owner_wait_q.

        Returns:
            The number of entries on the owner_wait_q as an integer

        :Example: instantiate a se_lock and get the len

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> print(len(a_lock))
        0

        >>> a_lock.obtain_excl()
        >>> print(len(a_lock))
        1

        >>> a_lock.release()
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
            __class__: Type[SELock]  # noqa: F842
        classname = self.__class__.__name__
        parms = ""  # placeholder for future parms

        return f"{classname}({parms})"

    ####################################################################
    # obtain_excl
    ####################################################################
    def obtain_excl(self, timeout: OptIntFloat = None) -> None:
        """Method to obtain the SELock.

        Args:
            timeout: number of seconds that the request is allowed to
                wait for the lock before an error is raised

        Raises:
            SELockOwnerNotAlive: The owner of the SELock is not alive
                and will thus never release the lock. Unfortunately,
                this error is not detectable until a request is made,
                and raising it here makes the current requestor is an
                innocent bystander. The solution is to provide
                recovery processing for lock owners to ensure that
                resources are left in a known state and held locks are
                released when the owner thread suffers an error.
            SELockObtainTimeout: A lock obtain request has timed out
                waiting for the current owner thread to release the
                lock.

        .. # noqa: DAR402

        :Example: obtain an SELock in exclusive mode

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> a_lock.obtain_excl()
        >>> print('lock obtained in exclusive mode')
        lock obtained in exclusive mode

        """
        with self.se_lock_lock:
            # get a wait event to wait on lock if unavailable
            wait_event = threading.Event()
            self.owner_wait_q.append(
                SELock._LockOwnerWaiter(
                    req_type=SELock.ReqType.Exclusive,
                    mode=SELock._Mode.EXCL,
                    event=wait_event,
                    thread=threading.current_thread(),
                )
            )
            thread_name = threading.current_thread().name
            self.owner_index[thread_name] += 1
            if self.owner_index[thread_name] > 1:
                self._check_for_already_owned_error(req_type=SELock.ReqType.Exclusive)
            if self.owner_count == 0:  # if lock is free
                self.owner_count = -1  # indicate now owned exclusive

                if self.debug_logging_enabled:
                    self.logger.debug(
                        "SELock exclusive obtain request granted immediate exclusive "
                        f"control to thread {threading.current_thread().name}, "
                        f"call sequence: {call_seq(latest=1, depth=2)}"
                    )
                return

            # self._check_for_already_owned_error(req_type=SELock.ReqType.Exclusive)

            # lock not free, bump wait count while se_lock_lock held
            self.excl_wait_count += 1

        # we are in the queue, wait for lock to be granted to us
        self._wait_for_lock(
            wait_event=wait_event,
            req_type=SELock.ReqType.Exclusive,
            timeout=timeout,
        )

    ####################################################################
    # obtain_excl
    ####################################################################
    def obtain_excl_recursive(self, timeout: OptIntFloat = None) -> None:
        """Method to obtain the SELock recursive mode.

        Args:
            timeout: number of seconds that the request is allowed to
                wait for the lock before an error is raised

        Raises:
            SELockOwnerNotAlive: The owner of the SELock is not alive
                and will thus never release the lock. Unfortunately,
                this error is not detectable until a request is made,
                and raising it here makes the current requestor is an
                innocent bystander. The solution is to provide
                recovery processing for lock owners to ensure that
                resources are left in a known state and held locks are
                released when the owner thread suffers an error.
            SELockObtainTimeout: A lock obtain request has timed out
                waiting for the current owner thread to release the
                lock.

        .. # noqa: DAR402

        :Example: obtain an SELock in exclusive mode

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> a_lock.obtain_excl_recursive()
        >>> print('lock obtained in exclusive mode')
        lock obtained in exclusive mode

        """
        with self.se_lock_lock:
            if (
                self.owner_wait_q
                and self.owner_wait_q[0].thread is threading.current_thread()
                and self.owner_wait_q[0].mode == SELock._Mode.EXCL
            ):
                self.owner_count -= 1  # track recursive obtain
                if self.debug_logging_enabled:
                    self.logger.debug(
                        "SELock exclusive recursive obtain request continues "
                        "exclusive control with recursion depth increased to "
                        f"{abs(self.owner_count)} for thread "
                        f"{threading.current_thread().name}, "
                        f"call sequence: {call_seq(latest=1, depth=2)}"
                    )

                return

            # get a wait event to wait on lock if unavailable
            wait_event = threading.Event()
            self.owner_wait_q.append(
                SELock._LockOwnerWaiter(
                    req_type=SELock.ReqType.ExclusiveRecursive,
                    mode=SELock._Mode.EXCL,
                    event=wait_event,
                    thread=threading.current_thread(),
                )
            )
            thread_name = threading.current_thread().name
            self.owner_index[thread_name] += 1
            if self.owner_index[thread_name] > 1:
                self._check_for_already_owned_error(
                    req_type=SELock.ReqType.ExclusiveRecursive
                )
            if self.owner_count == 0:  # if lock is free
                self.owner_count = -1  # indicate now owned exclusive

                if self.debug_logging_enabled:
                    self.logger.debug(
                        "SELock exclusive recursive obtain request granted "
                        "immediate exclusive control with recursion depth of 1 for "
                        f"thread {threading.current_thread().name}, "
                        f"call sequence: {call_seq(latest=1, depth=2)}"
                    )
                return

            # self._check_for_already_owned_error(
            #     req_type=SELock.ReqType.ExclusiveRecursive
            # )

            # lock not free, bump wait count while se_lock_lock held
            self.excl_wait_count += 1

        # we are in the queue, wait for lock to be granted to us
        self._wait_for_lock(
            wait_event=wait_event,
            req_type=SELock.ReqType.ExclusiveRecursive,
            timeout=timeout,
        )

    ####################################################################
    # obtain_share
    ####################################################################
    def obtain_share(self, timeout: OptIntFloat = None) -> None:
        """Method to obtain the SELock.

        Args:
            timeout: number of seconds that the request is allowed to
                       wait for the lock before an error is raised

        Raises:
            SELockOwnerNotAlive: The owner of the SELock is not alive
                and will thus never release the lock. Unfortunately,
                this error is not detectable until a request is made,
                and raising it here makes the current requestor is an
                innocent bystander. The solution is to provide
                recovery processing for lock owners to ensure that
                resources are left in a known state and held locks are
                released when the owner thread suffers an error.
            SELockObtainTimeout: A lock obtain request has timed out
                waiting for the current owner thread to release the
                lock.

        .. # noqa: DAR402

        :Example: obtain an SELock in exclusive mode

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> a_lock.obtain_share()
        >>> print('lock obtained in shared mode')
        lock obtained in shared mode

        """
        with self.se_lock_lock:
            # get a wait event to wait on lock if unavailable
            wait_event = threading.Event()
            self.owner_wait_q.append(
                SELock._LockOwnerWaiter(
                    req_type=SELock.ReqType.Share,
                    mode=SELock._Mode.SHARE,
                    event=wait_event,
                    thread=threading.current_thread(),
                )
            )
            thread_name = threading.current_thread().name
            self.owner_index[thread_name] += 1
            if self.owner_index[thread_name] > 1:
                self._check_for_already_owned_error(req_type=SELock.ReqType.Share)

            # if no exclusive waiters, and lock is free or owned shared
            if self.excl_wait_count == 0 <= self.owner_count:
                self.owner_count += 1  # bump the share owner count

                if self.debug_logging_enabled:
                    self.logger.debug(
                        f"SELock share obtain request granted immediate shared control "
                        f"to thread {threading.current_thread().name}, "
                        f"call sequence: {call_seq(latest=1, depth=2)}"
                    )
                return

        # we are in the queue, wait for lock to be granted to us
        self._wait_for_lock(
            wait_event=wait_event,
            req_type=SELock.ReqType.Share,
            timeout=timeout,
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

        :Example: obtain an SELock in shared mode and release it

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> a_lock.obtain_share()
        >>> print('lock obtained in shared mode')
        lock obtained in shared mode

        >>> a_lock.release()
        >>> print('lock released')
        lock released

        """
        with self.se_lock_lock:
            owner_waiter_desc = self._find_owner_waiter(
                thread=threading.current_thread()
            )

            if owner_waiter_desc.item_idx == -1:  # if not found
                error_msg = (
                    "SELock release request for thread "
                    f"{threading.current_thread().name} raising "
                    "AttemptedReleaseOfUnownedLock because an entry on the "
                    "owner-waiter queue was not found for that thread. "
                    f"Request call sequence: {call_seq(latest=1, depth=2)}"
                )
                self.logger.error(error_msg)

                raise AttemptedReleaseOfUnownedLock(error_msg)

            if (
                owner_waiter_desc.item_idx != 0
                and owner_waiter_desc.item_mode == SELock._Mode.EXCL
            ):
                error_msg = (
                    "SELock release request for thread "
                    f"{threading.current_thread().name} raising "
                    "AttemptedReleaseByExclusiveWaiter because the entry found for "
                    "that thread was still waiting for exclusive control of the lock. "
                    f"Request call sequence: {call_seq(latest=1, depth=2)}"
                )
                self.logger.error(error_msg)

                raise AttemptedReleaseByExclusiveWaiter(error_msg)

            if (
                0 <= owner_waiter_desc.excl_idx < owner_waiter_desc.item_idx
                and owner_waiter_desc.item_mode == SELock._Mode.SHARE
            ):
                error_msg = (
                    "SELock release request for thread "
                    f"{threading.current_thread().name} raising "
                    "AttemptedReleaseBySharedWaiter because the entry found for that "
                    "thread was still waiting for shared control of the lock. "
                    f"Request call sequence: {call_seq(latest=1, depth=2)}"
                )
                self.logger.error(error_msg)

                raise AttemptedReleaseBySharedWaiter(error_msg)

            # release the lock
            if owner_waiter_desc.item_mode == SELock._Mode.EXCL:
                # if the lock was obtained non-recursively, bumping the
                # owner_count will bring it to zero. If, the lock was
                # obtained more than once recursively, bumping the
                # owner_count will make it less negative and possibly
                # zero.
                self.owner_count += 1
                if self.owner_count < 0:  # if not yet free
                    if self.debug_logging_enabled:
                        self.logger.debug(
                            "SELock release request continues "
                            "exclusive control with recursion depth reduced to "
                            f"{abs(self.owner_count)} for thread "
                            f"{threading.current_thread().name}, "
                            f"call sequence: {call_seq(latest=1, depth=2)}"
                        )
                    return  # exclusive owner still owns the lock
            else:
                self.owner_count -= 1
            del self.owner_wait_q[owner_waiter_desc.item_idx]

            # we never expect the owner_index to be greater than 1
            if self.owner_index[threading.current_thread().name] == 1:
                del self.owner_index[threading.current_thread().name]
            else:
                self.owner_index[threading.current_thread().name] -= 1

            if self.debug_logging_enabled:
                if owner_waiter_desc.item_mode == SELock._Mode.EXCL:
                    excl_share = "exclusive"
                else:
                    excl_share = "shared"
                self.logger.debug(
                    f"SELock release request removed {excl_share} control for thread "
                    f"{threading.current_thread().name}, "
                    f"call sequence: {call_seq(latest=1, depth=2)}"
                )
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
            # first item will be for exclusive control in which case we
            # will grant control by resuming it (unless the last of the
            # group was also the last on the queue).
            if self.owner_wait_q:
                if self.owner_wait_q[0].mode == SELock._Mode.EXCL:
                    # wake up the exclusive waiter
                    self.owner_wait_q[0].event.set()
                    self.owner_count = -1
                    self.excl_wait_count -= 1
                    if self.debug_logging_enabled:
                        self.logger.debug(
                            "SELock release request for thread "
                            f"{threading.current_thread().name} "
                            f"granted exclusive control to waiting "
                            f"thread {self.owner_wait_q[0].thread.name}, "
                            f"call sequence: {call_seq(latest=1, depth=2)}"
                        )
                    return  # all done

                # If we are here, new first item is either a shared
                # owner or a shared waiter. If we just released an
                # exclusive item, then we know that the new first shared
                # item was waiting and we now need to resume it and any
                # subsequent shared items to grant shared control.
                # If we had instead just released a shared item, then we
                # know the new first shared item and any subsequent
                # shared items were already previously granted shared
                # control, meaning we have nothing to do.

                # handle case where exclusive was released
                if owner_waiter_desc.item_mode == SELock._Mode.EXCL:
                    for item in self.owner_wait_q:
                        # if we come to an exclusive waiter, then we are
                        # done for now
                        if item.mode == SELock._Mode.EXCL:
                            return
                        # wake up shared waiter
                        item.event.set()
                        self.owner_count += 1
                        if self.debug_logging_enabled:
                            self.logger.debug(
                                f"SELock release request for thread "
                                f"{threading.current_thread().name} "
                                f"granted shared control to waiting "
                                f"thread {item.thread.name}, "
                                f"call sequence: {call_seq(latest=1, depth=2)}"
                            )

    ####################################################################
    # _wait_for_lock
    ####################################################################
    def _wait_for_lock(
        self,
        wait_event: threading.Event,
        req_type: ReqType,
        timeout: OptIntFloat = None,
    ) -> None:
        """Method to wait for the SELock.

        Args:
            wait_event: event to wait on that will be set by the current
                owner upon lock release
            req_type: type of lock request
            timeout: number of seconds that the request is allowed to
                       wait for the lock before an error is raised

        Raises:
            SELockOwnerNotAlive: The owner of the SELock is not alive
                and will thus never release the lock. Unfortunately,
                this error is not detectable until a request is made,
                and raising it here makes the current requestor is an
                innocent bystander. The solution is to provide
                recovery processing for lock owners to ensure that
                resources are left in a known state and held locks are
                released when the owner thread suffers an error.
            SELockObtainTimeout: A lock obtain request has timed out
                waiting for the current owner thread to release the
                lock.

        """
        # There are 2 timeout values used in this method. The timeout
        # arg passed in is the number of seconds that the caller of
        # obtain is giving us to get the lock. This value can be as
        # small or as large as the caller wants, and could even be
        # a value of None which means no time limit is to be used.
        # The second timeout value if the one used on the wait_event
        # when we wait for the lock. We want to wake up periodically to
        # check whether the lock owner is still alive and raise an error
        # if not. This timeout value is defined in WAIT_TIMEOUT and is
        # a fairly large value intended to only wake us up to check for
        # the rare case of the lock owner having failed and becoming not
        # alive. If the caller specified timeout value is smaller than
        # the WAIT_TIMEOUT value, we will use that on the wait_event
        # to ensure we are honoring the caller desired timeout value.
        # Note also that the timer.timeout value is the remaining time
        # for the caller specified timeout - it is reduced as needed as
        # we continue to loop checking the owner thread (unless it was
        # smaller than WAIT_TIMEOUT in which case we will timeout the
        # request the first time we check that current lock owner.
        timer = Timer(timeout=timeout)

        if self.debug_logging_enabled:
            self.logger.debug(
                f"{req_type} for thread {threading.current_thread().name} waiting "
                f"for SELock, {timeout=}, call sequence: {call_seq(latest=2, depth=2)}"
            )
        while True:
            remaining_time = timer.remaining_time()
            if remaining_time:
                timeout_value = min(remaining_time, SELock.WAIT_TIMEOUT)
            else:
                timeout_value = SELock.WAIT_TIMEOUT
            # wait for lock to be granted to us
            if wait_event.wait(timeout=timeout_value):
                return

            # we have waited long enough, check if owner still alive
            with self.se_lock_lock:
                # we need to check the wait_event again under the lock
                # to make sure we did not just now get the lock
                if wait_event.is_set():
                    return

                # We may have timed out by now if the caller specified a
                # timeout value, but we give priority to the owner
                # having become not alive and raise that error here
                # instead since that is likely the root cause of the
                # timeout.
                if not self.owner_wait_q[0].thread.is_alive():
                    error_msg = (
                        f"{req_type} for thread {threading.current_thread().name} "
                        "raising SELockOwnerNotAlive while waiting for a lock because "
                        f"the lock owner thread {self.owner_wait_q[0].thread} is not "
                        "alive and will thus never release the lock. "
                        f"Request call sequence: {call_seq(latest=2, depth=2)}"
                    )
                    self.logger.error(error_msg)

                    raise SELockOwnerNotAlive(error_msg)

                if timer.is_expired():
                    owner_waiter_desc = self._find_owner_waiter(
                        thread=threading.current_thread()
                    )

                    del self.owner_wait_q[owner_waiter_desc.item_idx]
                    if owner_waiter_desc.item_mode == SELock._Mode.EXCL:
                        self.excl_wait_count -= 1

                    error_msg = (
                        f"{req_type} for thread {threading.current_thread().name} "
                        "raising SELockObtainTimeout because the thread has timed out "
                        "waiting for the current owner thread "
                        f"{self.owner_wait_q[0].thread.name} to release the lock. "
                        f"Request call sequence: {call_seq(latest=2, depth=2)}"
                    )
                    self.logger.error(error_msg)

                    raise SELockObtainTimeout(error_msg)

    ####################################################################
    # _find_owner_waiter
    ####################################################################
    def _find_owner_waiter(self, thread: threading.Thread) -> _OwnerWaiterDesc:
        """Method to find the given thread on the owner_waiter_q.

        Args:
            thread: thread of the owner of waiter to search for

        Returns:
            An _OwnerWaiterDesc item that contain the index of the
            _LockOwnerWaiter item on the owner_waiter_q, the index of
            the first exclusive request on the owner_waiter_q that
            precedes the found item, and the mode of the found item.

        Notes:
            1) The se_lock_lock must be held when calling this method

        """
        excl_idx = -1  # init to indicate exclusive req not found
        item_idx = -1  # init to indicate req not found
        item_mode = SELock._Mode.EXCL
        for idx, item in enumerate(self.owner_wait_q):
            if (excl_idx == -1) and (item.mode == SELock._Mode.EXCL):
                excl_idx = idx
            if item.thread is thread:
                item_idx = idx
                item_mode = item.mode
                break

        return SELock._OwnerWaiterDesc(
            excl_idx=excl_idx, item_idx=item_idx, item_mode=item_mode
        )

    ####################################################################
    # _check_for_already_owned_error
    ####################################################################
    def _check_for_already_owned_error(self, req_type: ReqType) -> None:
        """Method to raise error if deadlock detected.

        Args:
            req_type: req_type: type of lock request

        Raises:
            SELockAlreadyOwnedError: The new request already owns
                the SELock and must not wait.

        Notes:
            1) The se_lock_lock must be held when calling this method

        """
        # we need to check all entries except the last which is where
        # the new request was just queued
        thread = threading.current_thread()
        thread_name = thread.name
        for idx in range(len(self.owner_wait_q) - 1):
            if self.owner_wait_q[idx].thread is thread:
                # remove the new request from the end of the queue
                self.owner_wait_q.pop()

                # we know the new count will be non-zero after the
                # decrement because we call this method when it is
                # greater than 1 - so, we know a del will not be needed
                self.owner_index[thread_name] -= 1

                error_msg = (
                    f"{req_type} for thread {thread_name} "
                    "raising SELockAlreadyOwnedError because the requestor "
                    "already owns the lock. "
                    f"Request call sequence: {call_seq(latest=2, depth=2)}"
                )
                self.logger.error(error_msg)

                raise SELockAlreadyOwnedError(error_msg)

    ####################################################################
    # get_info
    ####################################################################
    def get_info(self) -> LockInfo:
        """Return a list of the queue items.

        Returns:
            List of queue items.

        """
        with self.se_lock_lock:
            return LockInfo(
                queue=[
                    LockItem(
                        mode=(
                            SELockObtainMode.Share
                            if item.mode == SELock._Mode.SHARE
                            else SELockObtainMode.Exclusive
                        ),
                        event_flag=item.event.is_set(),
                        thread=item.thread,
                    )
                    for item in self.owner_wait_q
                ],
                owner_count=self.owner_count,
                excl_wait_count=self.excl_wait_count,
            )

    ####################################################################
    # verify_lock
    ####################################################################
    def verify_lock(
        self,
        exp_q: Optional[list[LockItem]] = None,
        exp_owner_count: Optional[int] = None,
        exp_excl_wait_count: Optional[int] = None,
        timeout: OptIntFloat = None,
        verify_structures: bool = True,
    ) -> None:
        """Verifies that the lock is in the specified state.

        Args:
            exp_q: list of LockItem objects that specify the expected
                owners and/or waiters of the lock. If not specified,
                the lock will be do a minimal verification to ensure
                the counts are reasonable.
            exp_owner_count: specifies the expected owner count. If
                specified, exp_q must also be specified.
            exp_excl_wait_count: specifies the expected exclusive wait
                count. If specified, exp_q must also be specified.
            timeout: A non-zero positive value specifies the time
                allowed for the lock to get into the specified state.
                If not specified or a value of zero or less is
                specified, the lock must already be in the specified
                state at entry. Note that *exp_q* must also be
                specified.
            verify_structures: If True, verify the lock structures

        Raises:
            LockVerifyError: the lock failed to verify, or failed to
                reach the expected state within the time specified for
                *timeout*.

        """
        if exp_q is None:
            if not verify_structures:
                error_msg = (
                    "lock_verify raising SELockInputError. Nothing was requested to "
                    f"be verified with {exp_q=} and {verify_structures=}. "
                    f"Request call sequence: {call_seq(latest=1, depth=2)}"
                )
                self.logger.error(error_msg)
                raise SELockInputError(error_msg)
            if (
                exp_owner_count is not None
                or exp_excl_wait_count is not None
                or timeout is not None
            ):
                error_msg = (
                    "lock_verify raising SELockInputError. exp_q must be "
                    "specified if any of exp_owner_count, exp_excl_wait_count, or "
                    f"timeout is specified. {exp_q=}, {exp_owner_count=}, "
                    f"{exp_excl_wait_count=}, {timeout=}. "
                    f"Request call sequence: {call_seq(latest=1, depth=2)}"
                )
                self.logger.error(error_msg)
                raise SELockInputError(error_msg)

        lock_info = self.get_info()

        if exp_q is not None:
            timer = Timer(timeout=timeout)
            while True:
                if (
                    exp_q == lock_info.queue
                    and (
                        exp_owner_count is None
                        or exp_owner_count == lock_info.owner_count
                    )
                    and (
                        exp_excl_wait_count is None
                        or exp_excl_wait_count == lock_info.excl_wait_count
                    )
                ):
                    break

                if timeout is None or timeout <= 0 or timer.is_expired():
                    error_msg = (
                        f"lock_verify raising LockVerifyError. {exp_q=} , "
                        f"{lock_info.queue=}, {exp_owner_count=}, "
                        f"{lock_info.owner_count=}, {exp_excl_wait_count=}, "
                        f"{lock_info.excl_wait_count=}, {timeout=}. "
                        f"Request call sequence: {call_seq(latest=1, depth=2)}"
                    )
                    self.logger.error(error_msg)
                    raise LockVerifyError(error_msg)
                time.sleep(0.1)
                lock_info = self.get_info()

        if verify_structures:
            calc_owner_count = 0
            calc_excl_wait_count = 0
            idx_of_first_excl_wait = -1
            idx_of_first_excl_event_flag = -1
            idx_of_first_share_event_flag = -1
            idx_of_first_share_wait = -1
            for idx, lock_item in enumerate(lock_info.queue):
                if lock_item.mode == SELockObtainMode.Exclusive:
                    if idx == 0:
                        calc_owner_count = -1
                    else:
                        if idx_of_first_excl_wait == -1:
                            idx_of_first_excl_wait = idx
                        calc_excl_wait_count += 1
                        if lock_item.event_flag and idx_of_first_excl_event_flag == -1:
                            idx_of_first_excl_event_flag = idx
                else:
                    if idx == 0:
                        calc_owner_count = 1
                    else:
                        if calc_owner_count > 0:
                            if idx_of_first_excl_wait == -1:
                                calc_owner_count += 1
                            else:
                                if idx_of_first_share_wait == -1:
                                    idx_of_first_share_wait = idx
                    if lock_item.event_flag and idx_of_first_share_event_flag == -1:
                        idx_of_first_share_event_flag = idx

            # note in the following code that the check for owner_count
            # being less than or equal to -1 is correct since a
            # recursive excl obtain will simply bump down the
            # owner count to track the recursive depth
            owner_count_error = not (
                (lock_info.owner_count <= calc_owner_count == -1)
                or (0 <= lock_info.owner_count == calc_owner_count)
            )
            wait_count_error = lock_info.excl_wait_count != calc_excl_wait_count
            excl_event_flag_error = idx_of_first_excl_event_flag > 0

            # the following code must ensure that idx_of_first_excl_wait
            # is greater than 0 since an idx_of_first_excl_wait of 0 is
            # not possible and a value of -1 indicates that there are no
            # excl lock waiters
            share_event_flag_error = (
                0 < idx_of_first_excl_wait < idx_of_first_share_event_flag
            ) or (lock_info.owner_count < 0 < idx_of_first_share_event_flag)

            if (
                owner_count_error
                or wait_count_error
                or excl_event_flag_error
                or share_event_flag_error
            ):
                error_msg = (
                    f"lock_verify raising LockVerifyError. {owner_count_error=}, "
                    f"{wait_count_error=}, {excl_event_flag_error=}, "
                    f"{share_event_flag_error=}, {exp_q=}, "
                    f"{lock_info.queue=}, {exp_owner_count=}, "
                    f"{lock_info.owner_count=}, {exp_excl_wait_count=}, "
                    f"{lock_info.excl_wait_count=}, {timeout=}, "
                    f"{calc_owner_count=}, {calc_excl_wait_count=}, "
                    f"{idx_of_first_excl_wait=}, {idx_of_first_excl_event_flag=}, "
                    f"{idx_of_first_share_wait=}, {idx_of_first_share_event_flag=}. "
                    f"Request call sequence: {call_seq(latest=1, depth=2)}"
                )
                self.logger.error(error_msg)
                raise LockVerifyError(error_msg)


########################################################################
# SELock Context Manager for Shared Control
########################################################################
class SELockShare:
    """Context manager for shared control."""

    def __init__(
        self, se_lock: SELock, obtain_tf: bool = True, timeout: OptIntFloat = None
    ) -> None:
        """Initialize shared lock context manager.

        Args:
            se_lock: instance of SELock
            obtain_tf: allows the obtain request to be conditional to
                allow coding the with statement and then getting or not
                getting the lock as dynamically required
            timeout: number of seconds that the request is allowed to
                wait for the lock before an error is raised

        Raises:
            SELockOwnerNotAlive: The owner of the SELock is not alive
                and will thus never release the lock. Unfortunately,
                this error is not detectable until a request is made,
                and raising it here makes the current requestor is an
                innocent bystander. The solution is to provide
                recovery processing for lock owners to ensure that
                resources are left in a known state and held locks are
                released when the owner thread suffers an error.
            SELockObtainTimeout: A lock obtain request has timed out
                waiting for the current owner thread to release the
                lock.

        .. # noqa: DAR402

        :Example: obtain an SELock in shared mode

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in shared mode
        >>> with SELockShare(a_lock):
        ...     msg = 'lock obtained shared'
        >>> print(msg)
        lock obtained shared

        :Example: obtain an SELock in shared mode conditionally

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in shared mode conditionally
        >>> condition_var = True
        >>> with SELockShare(a_lock, obtain_tf=condition_var):
        ...     if condition_var:
        ...         msg = 'lock obtained shared'
        ...     else:
        ...         msg = 'lock not obtained'
        >>> print(msg)
        lock obtained shared

        :Example: obtain an SELock in shared mode conditionally

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in shared mode conditionally
        >>> condition_var = False
        >>> with SELockShare(a_lock, obtain_tf=condition_var):
        ...     if condition_var:
        ...         msg = 'lock obtained shared'
        ...     else:
        ...         msg = 'lock not obtained'
        >>> print(msg)
        lock not obtained

        """
        self.se_lock = se_lock
        self.obtain_tf = obtain_tf
        self.timeout = timeout

    def __enter__(self) -> None:
        """Context manager enter method."""
        if self.obtain_tf:
            self.se_lock.obtain_share(timeout=self.timeout)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        if self.obtain_tf:
            self.se_lock.release()


########################################################################
# SELock Context Manager for Exclusive Control
########################################################################
class SELockExcl:
    """Context manager for exclusive control."""

    def __init__(
        self,
        se_lock: SELock,
        obtain_tf: bool = True,
        allow_recursive_obtain: bool = False,
        timeout: OptIntFloat = None,
    ) -> None:
        """Initialize exclusive lock context manager.

        Args:
            se_lock: instance of SELock
            obtain_tf: allows the obtain to be conditional to allow
                coding the with statement and then getting or not
                getting the lock as dynamically required
            allow_recursive_obtain: if lock is already owned by the
                requesting thread, simply bump the ownership count
            timeout: number of seconds that the request is allowed to
                       wait for the lock before an error is raised

        Raises:
            SELockOwnerNotAlive: The owner of the SELock is not alive
                and will thus never release the lock. Unfortunately,
                this error is not detectable until a request is made,
                and raising it here makes the current requestor is an
                innocent bystander. The solution is to provide
                recovery processing for lock owners to ensure that
                resources are left in a known state and held locks are
                released when the owner thread suffers an error.
            SELockObtainTimeout: A lock obtain request has timed out
                waiting for the current owner thread to release the
                lock.

        .. # noqa: DAR402

        :Example: obtain an SELock in exclusive mode

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in exclusive mode
        >>> with SELockExcl(a_lock):
        ...     msg = 'lock obtained exclusive'
        >>> print(msg)
        lock obtained exclusive

        :Example: obtain an SELock in exclusive mode conditionally

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in exclusive mode conditionally
        >>> condition_var = True
        >>> with SELockExcl(a_lock, obtain_tf=condition_var):
        ...     if condition_var:
        ...         msg = 'lock obtained exclusive'
        ...     else:
        ...         msg = 'lock not obtained'
        >>> print(msg)
        lock obtained exclusive

        :Example: obtain an SELock in exclusive mode conditionally

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in exclusive mode conditionally
        >>> condition_var = False
        >>> with SELockExcl(a_lock, obtain_tf=condition_var):
        ...     if condition_var:
        ...         msg = 'lock obtained exclusive'
        ...     else:
        ...         msg = 'lock not obtained'
        >>> print(msg)
        lock not obtained

        """
        self.se_lock = se_lock
        self.obtain_tf = obtain_tf
        self.allow_recursive_obtain = allow_recursive_obtain
        self.timeout = timeout

    def __enter__(self) -> None:
        """Context manager enter method."""
        if self.obtain_tf:
            if self.allow_recursive_obtain:
                self.se_lock.obtain_excl_recursive(timeout=self.timeout)
            else:
                self.se_lock.obtain_excl(timeout=self.timeout)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        if self.obtain_tf:
            self.se_lock.release()


########################################################################
# SELock Context Manager for Exclusive or Share Control
########################################################################
class SELockObtain:
    """Context manager for shared or exclusive control."""

    def __init__(
        self,
        se_lock: SELock,
        obtain_mode: SELockObtainMode,
        obtain_tf: bool = True,
        allow_recursive_obtain: bool = False,
        timeout: OptIntFloat = None,
    ) -> None:
        """Initialize shared or exclusive lock context manager.

        Args:
            se_lock: instance of SELock
            obtain_mode: specifies the lock mode required as Share or
                Exclusive
            obtain_tf: allows the obtain to be conditional to allow
                coding the with statement and then getting or not
                getting the lock as dynamically required
            allow_recursive_obtain: if lock is already owned by the
                requesting thread, simply bump the ownership count
            timeout: number of seconds that the request is allowed to
                       wait for the lock before an error is raised

        Raises:
            SELockOwnerNotAlive: The owner of the SELock is not alive
                and will thus never release the lock. Unfortunately,
                this error is not detectable until a request is made,
                and raising it here makes the current requestor is an
                innocent bystander. The solution is to provide
                recovery processing for lock owners to ensure that
                resources are left in a known state and held locks are
                released when the owner thread suffers an error.
            SELockObtainTimeout: A lock obtain request has timed out
                waiting for the current owner thread to release the
                lock.

        .. # noqa: DAR402

        :Example: obtain an SELock in exclusive mode

        >>> from scottbrian_locking.se_lock import (SELock,
        ...                                         SELockObtain,
        ...                                         SELockObtainMode)
        >>> a_lock = SELock()
        >>> # Get lock in exclusive mode
        >>> with SELockObtain(a_lock,
        ...                   obtain_mode=SELockObtainMode.Exclusive):
        ...     msg = 'lock obtained exclusive'
        >>> print(msg)
        lock obtained exclusive

        :Example: obtain an SELock in shared mode

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in shared mode
        >>> with SELockObtain(a_lock,
        ...                   obtain_mode=SELockObtainMode.Share):
        ...     msg = 'lock obtained shared'
        >>> print(msg)
        lock obtained shared

        :Example: obtain an SELock in exclusive mode conditionally

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in exclusive mode conditionally
        >>> condition_var = True
        >>> with SELockObtain(a_lock,
        ...                   obtain_mode=SELockObtainMode.Exclusive,
        ...                   obtain_tf=condition_var):
        ...     if condition_var:
        ...         msg = 'lock obtained exclusive'
        ...     else:
        ...         msg = 'lock was not obtained'
        >>> print(msg)
        lock obtained exclusive

        :Example: obtain an SELock in exclusive mode conditionally

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in exclusive mode conditionally
        >>> condition_var = False
        >>> with SELockObtain(a_lock,
        ...                   obtain_mode=SELockObtainMode.Exclusive,
        ...                   obtain_tf=condition_var):
        ...     if condition_var:
        ...         msg = 'lock obtained exclusive'
        ...     else:
        ...         msg = 'lock was not obtained'
        >>> print(msg)
        lock was not obtained

        :Example: obtain an SELock in shared mode conditionally

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in shared mode conditionally
        >>> condition_var = True
        >>> with SELockObtain(a_lock,
        ...                   obtain_mode=SELockObtainMode.Share,
        ...                   obtain_tf=condition_var):
        ...     if condition_var:
        ...         msg = 'lock obtained shared'
        ...     else:
        ...         msg = 'lock was not obtained'
        >>> print(msg)
        lock obtained shared

        :Example: obtain an SELock in shared mode conditionally

        >>> from scottbrian_locking.se_lock import SELock
        >>> a_lock = SELock()
        >>> # Get lock in shared mode conditionally
        >>> condition_var = False
        >>> with SELockObtain(a_lock,
        ...                   obtain_mode=SELockObtainMode.Share,
        ...                   obtain_tf=condition_var):
        ...     if condition_var:
        ...         msg = 'lock obtained shared'
        ...     else:
        ...         msg = 'lock was not obtained'
        >>> print(msg)
        lock was not obtained

        """
        self.se_lock = se_lock
        self.obtain_mode = obtain_mode
        self.obtain_tf = obtain_tf
        self.allow_recursive_obtain = allow_recursive_obtain
        self.timeout = timeout

    def __enter__(self) -> None:
        """Context manager enter method."""
        if self.obtain_tf:
            if self.obtain_mode == SELockObtainMode.Share:
                self.se_lock.obtain_share(timeout=self.timeout)
            else:
                if self.allow_recursive_obtain:
                    self.se_lock.obtain_excl_recursive(timeout=self.timeout)
                else:
                    self.se_lock.obtain_excl(timeout=self.timeout)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        if self.obtain_tf:
            self.se_lock.release()
