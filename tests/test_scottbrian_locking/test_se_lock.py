"""test_se_lock.py module."""

########################################################################
# Standard Library
########################################################################
from dataclasses import dataclass
from enum import Enum, auto
import logging
import re
import threading
import time
from typing import Any, cast, Optional

########################################################################
# Third Party
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence as call_seq
from scottbrian_utils.flower_box import print_flower_box_msg as flowers
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.msgs import Msgs
from scottbrian_utils.stop_watch import StopWatch
import pytest

########################################################################
# Local
########################################################################
from scottbrian_locking.se_lock import (
    SELock,
    SELockShare,
    SELockExcl,
    SELockObtain,
    LockItem,
)
from scottbrian_locking.se_lock import (
    AttemptedReleaseByExclusiveWaiter,
    AttemptedReleaseBySharedWaiter,
    AttemptedReleaseOfUnownedLock,
    LockVerifyError,
    SELockInputError,
    SELockObtainTimeout,
    SELockOwnerNotAlive,
    SELockObtainMode,
)

########################################################################
# Set up logging
########################################################################
logger = logging.getLogger(__name__)
logger.debug("about to start the tests")


########################################################################
# SELock test exceptions
########################################################################
class ErrorTstSELock(Exception):
    """Base class for exception in this module."""

    pass


class InvalidRouteNum(ErrorTstSELock):
    """InvalidRouteNum exception class."""

    pass


class InvalidModeNum(ErrorTstSELock):
    """InvalidModeNum exception class."""

    pass


class BadRequestStyleArg(ErrorTstSELock):
    """BadRequestStyleArg exception class."""

    pass


class ContextArg(Enum):
    """ContextArg used to select which for of obtain lock to use."""

    NoContext = auto()
    ContextExclShare = auto()
    ContextObtain = auto()


########################################################################
# number_requests_arg fixture
########################################################################
number_requests_arg_list = [0, 1, 2, 3]


@pytest.fixture(params=number_requests_arg_list)  # type: ignore
def num_share_requests1_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=number_requests_arg_list)  # type: ignore
def num_share_requests2_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=number_requests_arg_list)  # type: ignore
def num_excl_requests1_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=number_requests_arg_list)  # type: ignore
def num_excl_requests2_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# release_position_arg fixture
########################################################################
release_position_arg_list = [0, 1, 2]


@pytest.fixture(params=release_position_arg_list)  # type: ignore
def release_position_arg(request: Any) -> int:
    """Using different release positions.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# use_context_arg fixture
########################################################################
use_context_arg_list = [0, 1, 2, 3]


@pytest.fixture(params=use_context_arg_list)  # type: ignore
def use_context_arg(request: Any) -> int:
    """Use context lock obtain.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# use_context2_arg fixture
########################################################################
use_context2_arg_list = [0, 1, 2, 3]


@pytest.fixture(params=use_context2_arg_list)  # type: ignore
def use_context2_arg(request: Any) -> int:
    """Use context lock obtain.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# verify_lock
########################################################################
# def verify_lock(
#     lock: SELock,
#     exp_q: list[tuple[SELockObtainMode, threading.Thread, bool]],
#     exp_owner_count: int,
#     exp_excl_wait_count: int,
# ) -> None:
#     lock_info = lock.get_info()
#     assert len(lock_info.queue) == len(exp_q)
#     for idx, item in enumerate(lock_info.queue):
#         assert item.mode == exp_q[idx][0]
#         assert item.thread is exp_q[idx][1]
#         assert item.event_flag == exp_q[idx][2]
#     assert lock_info.owner_count == exp_owner_count
#     assert lock_info.excl_wait_count == exp_excl_wait_count


########################################################################
# TestSELockBasic class to test SELock methods
########################################################################
class TestSELockErrors:
    """TestSELock class."""

    ####################################################################
    # test_lock_verify_bad_input
    ####################################################################
    def test_lock_verify_bad_input(self) -> None:
        """Test lock_verify with bad input."""
        ################################################################
        # SELockInputError
        ################################################################
        a_lock = SELock()
        error_msg = (
            "lock_verify raising SELockInputError. Nothing was requested to "
            "be verified with exp_q=None and verify_structures=False."
        )
        with pytest.raises(SELockInputError, match=error_msg):
            a_lock.verify_lock(verify_structures=False)

        with pytest.raises(SELockInputError, match=error_msg):
            a_lock.verify_lock(exp_q=None, verify_structures=False)

        error_msg = (
            "lock_verify raising SELockInputError. exp_q must be "
            "specified if any of exp_owner_count, exp_excl_wait_count, or "
            "timeout is specified. exp_q=None, exp_owner_count=0, "
            "exp_excl_wait_count=None, timeout=None."
        )

        with pytest.raises(SELockInputError, match=error_msg):
            a_lock.verify_lock(exp_owner_count=0)

        error_msg = (
            "lock_verify raising SELockInputError. exp_q must be "
            "specified if any of exp_owner_count, exp_excl_wait_count, or "
            "timeout is specified. exp_q=None, exp_owner_count=None, "
            "exp_excl_wait_count=0, timeout=None."
        )

        with pytest.raises(SELockInputError, match=error_msg):
            a_lock.verify_lock(exp_excl_wait_count=0)

        error_msg = (
            "lock_verify raising SELockInputError. exp_q must be "
            "specified if any of exp_owner_count, exp_excl_wait_count, or "
            "timeout is specified. exp_q=None, exp_owner_count=None, "
            "exp_excl_wait_count=None, timeout=0."
        )

        with pytest.raises(SELockInputError, match=error_msg):
            a_lock.verify_lock(timeout=0)

        for exp_owner_count in (None, 0):
            for exp_excl_wait_count in (None, 0):
                for timeout in (None, 0):
                    error_msg = (
                        "lock_verify raising SELockInputError. exp_q must be "
                        "specified if any of exp_owner_count, exp_excl_wait_count, or "
                        f"timeout is specified. exp_q=None, {exp_owner_count=}, "
                        f"{exp_excl_wait_count=}, {timeout=}."
                    )
                    if not (
                        exp_owner_count is None
                        and exp_excl_wait_count is None
                        and timeout is None
                    ):
                        with pytest.raises(SELockInputError, match=error_msg):
                            a_lock.verify_lock(
                                exp_owner_count=exp_owner_count,
                                exp_excl_wait_count=exp_excl_wait_count,
                                timeout=timeout,
                            )
                        with pytest.raises(SELockInputError, match=error_msg):
                            a_lock.verify_lock(
                                exp_owner_count=exp_owner_count,
                                exp_excl_wait_count=exp_excl_wait_count,
                                timeout=timeout,
                                verify_structures=True,
                            )

                        error_msg = (
                            "lock_verify raising SELockInputError. Nothing was "
                            "requested to be verified with exp_q=None and "
                            "verify_structures=False."
                        )
                        with pytest.raises(SELockInputError, match=error_msg):
                            a_lock.verify_lock(
                                exp_owner_count=exp_owner_count,
                                exp_excl_wait_count=exp_excl_wait_count,
                                timeout=timeout,
                                verify_structures=False,
                            )

        ################################################################
        # all other combinations should not produce an error
        ################################################################

        a_lock.verify_lock()
        a_lock.verify_lock(exp_q=[])
        a_lock.verify_lock(exp_q=[], verify_structures=False)
        a_lock.verify_lock(verify_structures=True)
        a_lock.verify_lock(exp_q=[], verify_structures=True)

        a_lock.verify_lock(exp_q=[], exp_owner_count=0)
        a_lock.verify_lock(exp_q=[], exp_owner_count=0, verify_structures=False)
        a_lock.verify_lock(exp_q=[], exp_owner_count=0, verify_structures=True)

        a_lock.verify_lock(exp_q=[], exp_excl_wait_count=0)
        a_lock.verify_lock(exp_q=[], exp_excl_wait_count=0, verify_structures=False)
        a_lock.verify_lock(exp_q=[], exp_excl_wait_count=0, verify_structures=True)

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)
        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, exp_excl_wait_count=0, verify_structures=False
        )
        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, exp_excl_wait_count=0, verify_structures=True
        )

        a_lock.verify_lock(exp_q=[], timeout=1)
        a_lock.verify_lock(exp_q=[], timeout=1, verify_structures=False)
        a_lock.verify_lock(exp_q=[], timeout=1, verify_structures=True)

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, timeout=1)
        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, timeout=1, verify_structures=False
        )
        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, timeout=1, verify_structures=True
        )

        a_lock.verify_lock(exp_q=[], exp_excl_wait_count=0, timeout=1)
        a_lock.verify_lock(
            exp_q=[], exp_excl_wait_count=0, timeout=1, verify_structures=False
        )
        a_lock.verify_lock(
            exp_q=[], exp_excl_wait_count=0, timeout=1, verify_structures=True
        )

        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, exp_excl_wait_count=0, timeout=1
        )
        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
            timeout=1,
            verify_structures=False,
        )
        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
            timeout=1,
            verify_structures=True,
        )

        for exp_owner_count in (None, 0):
            for exp_excl_wait_count in (None, 0):
                for timeout in (None, 0, 1):
                    for verify_structures in (None, True, False):
                        a_lock.verify_lock(
                            exp_q=[],
                            exp_owner_count=exp_owner_count,
                            exp_excl_wait_count=exp_excl_wait_count,
                            timeout=timeout,
                            verify_structures=verify_structures,
                        )

    def test_se_lock_release_unowned_lock(self) -> None:
        """Test release of unowned lock."""
        ################################################################
        # AttemptedReleaseOfUnownedLock
        ################################################################
        with pytest.raises(AttemptedReleaseOfUnownedLock):
            a_lock = SELock()

            a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

            a_lock.release()

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

    def test_se_lock_release_owner_not_alive(self) -> None:
        """Test owner become not alive while waiting for lock."""

        ################################################################
        # SELockOwnerNotAlive
        ################################################################
        def f1() -> None:
            """Function that obtains lock and end still holding it."""
            a_lock.obtain_excl()
            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Exclusive,
                        event_flag=False,
                        thread=f1_thread,
                    ),
                ],
                exp_owner_count=-1,
                exp_excl_wait_count=0,
            )

        a_lock = SELock()
        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

        f1_thread = threading.Thread(target=f1)
        f1_thread.start()
        f1_thread.join()

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f1_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
        )

        with pytest.raises(SELockOwnerNotAlive):
            # f1 obtained the lock and exited
            a_lock.obtain_excl()

        # the application is responsible for doing whatever recovery it
        # needs and then must release the lock
        alpha_thread = threading.current_thread()

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f1_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=alpha_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=1,
        )

    def test_se_lock_release_by_exclusive_waiter(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test release by exclusive waiter."""

        ################################################################
        # AttemptedReleaseByExclusiveWaiter
        ################################################################
        def f2() -> None:
            """Function that gets lock exclusive to cause contention."""
            # a_lock.obtain(mode=SELock._Mode.EXCL)
            f2_log_msg = (
                re.escape(
                    "SELock granted immediate exclusive control to "
                    f"{f2_thread.name}, "
                )
                + "caller threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f2:[0-9]+"
            )

            log_ver.add_pattern(pattern=f2_log_msg)

            a_lock.obtain_excl()

            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Exclusive,
                        event_flag=False,
                        thread=f2_thread,
                    ),
                ],
                exp_owner_count=-1,
                exp_excl_wait_count=0,
            )

            a_event.set()
            a_event2.wait()

        def f3() -> None:
            """Function that tries to release lock while waiting."""
            # a_lock.obtain(mode=SELock._Mode.EXCL)
            f3_log_msg = (
                re.escape(f"Thread {f3_thread.name} waiting for SELock, ")
                + "caller threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f3:[0-9]+"
            )
            log_ver.add_pattern(pattern=f3_log_msg)

            a_lock.obtain_excl()

            f3_exp_q = [
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f2_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=True,
                    thread=f3_thread,
                ),
            ]
            a_lock.verify_lock(
                exp_q=f3_exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=1,
                verify_structures=False,
            )

            f3_error_msg = re.escape(
                "lock_verify raising LockVerifyError. owner_count_error=False, "
                "wait_count_error=False, excl_event_flag_error=True, "
                f"share_event_flag_error=False, exp_q={f3_exp_q}, "
                f"lock_info.queue={f3_exp_q}, exp_owner_count=-1, "
                "lock_info.owner_count=-1, exp_excl_wait_count=1, "
                "lock_info.excl_wait_count=1, timeout=None, "
                "calc_owner_count=-1, calc_excl_wait_count=1, "
                "idx_of_first_excl_wait=1, idx_of_first_excl_event_flag=1, "
                "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=-1."
            )

            log_ver.add_pattern(pattern=f3_error_msg, level=logging.ERROR)
            with pytest.raises(LockVerifyError, match=f3_error_msg):
                a_lock.verify_lock(
                    exp_q=f3_exp_q,
                    exp_owner_count=-1,
                    exp_excl_wait_count=1,
                    verify_structures=True,
                )

            a_event.set()
            a_event3.wait()

            f3_error_msg = re.escape(
                f"Thread {f3_thread.name} raising "
                "AttemptedReleaseByExclusiveWaiter because the entry found for "
                "that thread was still waiting for exclusive control of the lock. "
                f"Request call sequence {call_seq(latest=1, depth=2)}"
            )
            log_ver.add_pattern(pattern=f3_error_msg, level=logging.ERROR)
            with pytest.raises(AttemptedReleaseByExclusiveWaiter, match=f3_error_msg):
                a_lock.release()

            a_lock.verify_lock(
                exp_q=f3_exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=1,
                verify_structures=False,
            )

            f3_error_msg = re.escape(
                "lock_verify raising LockVerifyError. owner_count_error=False, "
                "wait_count_error=False, excl_event_flag_error=True, "
                f"share_event_flag_error=False, exp_q=None, "
                f"lock_info.queue={exp_q}, exp_owner_count=None, "
                "lock_info.owner_count=-1, exp_excl_wait_count=None, "
                "lock_info.excl_wait_count=1, timeout=None, "
                "calc_owner_count=-1, calc_excl_wait_count=1, "
                "idx_of_first_excl_wait=1, idx_of_first_excl_event_flag=1, "
                "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=-1."
            )
            log_ver.add_pattern(pattern=f3_error_msg, level=logging.ERROR)
            with pytest.raises(LockVerifyError, match=f3_error_msg):
                a_lock.verify_lock()

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        a_lock = SELock()

        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
        )

        a_event = threading.Event()
        a_event2 = threading.Event()
        a_event3 = threading.Event()
        f2_thread = threading.Thread(target=f2)
        f3_thread = threading.Thread(target=f3)

        # start f2 to get the lock exclusive
        f2_thread.start()

        # wait for f2 to tell us it has the lock
        a_event.wait()
        a_event.clear()

        # verify lock
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f2_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
        )

        # start f3 to queue up for the lock behind f2
        f3_thread.start()

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f2_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f3_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=1,
            timeout=10,
        )

        # post (prematurely) the event in the SELock for f3
        a_lock.owner_wait_q[1].event.set()

        a_event.wait()
        a_event.clear()

        exp_q = [
            LockItem(
                mode=SELockObtainMode.Exclusive,
                event_flag=False,
                thread=f2_thread,
            ),
            LockItem(
                mode=SELockObtainMode.Exclusive,
                event_flag=True,
                thread=f3_thread,
            ),
        ]

        a_lock.verify_lock(
            exp_q=exp_q,
            exp_owner_count=-1,
            exp_excl_wait_count=1,
            verify_structures=False,  # avoid error for now
        )

        mainline_error_msg = re.escape(
            "lock_verify raising LockVerifyError. owner_count_error=False, "
            "wait_count_error=False, excl_event_flag_error=True, "
            f"share_event_flag_error=False, exp_q={exp_q}, "
            f"lock_info.queue={exp_q}, exp_owner_count=-1, "
            "lock_info.owner_count=-1, exp_excl_wait_count=1, "
            "lock_info.excl_wait_count=1, timeout=None, "
            "calc_owner_count=-1, calc_excl_wait_count=1, "
            "idx_of_first_excl_wait=1, idx_of_first_excl_event_flag=1, "
            "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=-1."
        )
        log_ver.add_pattern(pattern=mainline_error_msg, level=logging.ERROR)
        with pytest.raises(LockVerifyError, match=mainline_error_msg):
            a_lock.verify_lock(
                exp_q=exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=1,
                verify_structures=True,
            )

        # tell f2 and f3 to end - we will leave the lock damaged
        a_event2.set()
        a_event3.set()

        f2_thread.join()
        f3_thread.join()

        a_lock.verify_lock(
            exp_q=exp_q,
            exp_owner_count=-1,
            exp_excl_wait_count=1,
            verify_structures=False,
        )

        mainline_error_msg = re.escape(
            "lock_verify raising LockVerifyError. owner_count_error=False, "
            "wait_count_error=False, excl_event_flag_error=True, "
            f"share_event_flag_error=False, exp_q=None, "
            f"lock_info.queue={exp_q}, exp_owner_count=None, "
            "lock_info.owner_count=-1, exp_excl_wait_count=None, "
            "lock_info.excl_wait_count=1, timeout=None, "
            "calc_owner_count=-1, calc_excl_wait_count=1, "
            "idx_of_first_excl_wait=1, idx_of_first_excl_event_flag=1, "
            "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=-1."
        )

        log_ver.add_pattern(pattern=mainline_error_msg, level=logging.ERROR)
        with pytest.raises(LockVerifyError, match=mainline_error_msg):
            a_lock.verify_lock()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    def test_se_lock_release_by_shared_waiter(self) -> None:
        """Test release by shared waiter."""

        ################################################################
        # AttemptedReleaseBySharedWaiter
        ################################################################
        def f4() -> None:
            """Function that gets lock exclusive to cause contention."""

            f4_log_msg = (
                re.escape(
                    "SELock granted immediate exclusive control to "
                    f"{f4_thread.name}, "
                )
                + "caller threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f4:[0-9]+"
            )

            log_ver.add_pattern(pattern=f4_log_msg)

            # a_lock.obtain(mode=SELock._Mode.EXCL)
            a_lock.obtain_excl()

            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Exclusive,
                        event_flag=False,
                        thread=f4_thread,
                    ),
                ],
                exp_owner_count=-1,
                exp_excl_wait_count=0,
            )

            mainline_wait_event.set()
            f4_wait_event.wait()

        def f5() -> None:
            """Function that tries to release lock while waiting."""

            f5_log_msg = (
                re.escape(f"Thread {f5_thread.name} waiting for SELock, ")
                + "caller threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f5:[0-9]+"
            )
            log_ver.add_pattern(pattern=f5_log_msg)

            # a_lock.obtain(mode=SELock._Mode.SHARE)
            a_lock.obtain_share()

            # we have been woken prematurely
            f5_exp_q = [
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=True,
                    thread=f5_thread,
                ),
            ]
            a_lock.verify_lock(
                exp_q=f5_exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=0,
                verify_structures=False,
            )

            f5_verify_error_msg = re.escape(
                "lock_verify raising LockVerifyError. owner_count_error=False, "
                "wait_count_error=False, excl_event_flag_error=False, "
                f"share_event_flag_error=True, exp_q={f5_exp_q}, "
                f"lock_info.queue={f5_exp_q}, exp_owner_count=-1, "
                "lock_info.owner_count=-1, exp_excl_wait_count=0, "
                "lock_info.excl_wait_count=0, timeout=None, "
                "calc_owner_count=-1, calc_excl_wait_count=0, "
                "idx_of_first_excl_wait=-1, idx_of_first_excl_event_flag=-1, "
                "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=1."
            )

            log_ver.add_pattern(pattern=f5_verify_error_msg, level=logging.ERROR)
            with pytest.raises(LockVerifyError, match=f5_verify_error_msg):
                a_lock.verify_lock(
                    exp_q=f5_exp_q,
                    exp_owner_count=-1,
                    exp_excl_wait_count=0,
                    verify_structures=True,
                )

            f5_release_error_msg = re.escape(
                f"Thread {f5_thread.name} raising "
                "AttemptedReleaseBySharedWaiter because the entry found for that "
                "thread was still waiting for shared control of the lock. "
                f"Request call sequence {call_seq(latest=1, depth=2)}"
            )

            with pytest.raises(
                AttemptedReleaseBySharedWaiter, match=f5_release_error_msg
            ):
                a_lock.release()

            # the lock should not have changed, and the lock_verify
            # should provide the same result as above
            log_ver.add_pattern(pattern=f5_verify_error_msg, level=logging.ERROR)
            with pytest.raises(LockVerifyError, match=f5_verify_error_msg):
                a_lock.verify_lock(
                    exp_q=f5_exp_q,
                    exp_owner_count=-1,
                    exp_excl_wait_count=0,
                    verify_structures=True,
                )

            # tell mainline we are done
            mainline_wait_event.set()
            # wait for mainline to tell us to end
            f5_wait_event.wait()

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        a_lock = SELock()

        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
        )

        mainline_wait_event = threading.Event()
        f4_wait_event = threading.Event()
        f5_wait_event = threading.Event()
        f4_thread = threading.Thread(target=f4)
        f5_thread = threading.Thread(target=f5)

        # start f4 to get the lock exclusive
        f4_thread.start()

        # wait for f4 to tell us it has the lock
        mainline_wait_event.wait()
        mainline_wait_event.clear()

        # verify lock
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
        )

        # start f5 to queue up for the lock behind f4
        f5_thread.start()

        # loop 10 secs until verify_lock sees both locks in the queue
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=False,
                    thread=f5_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
            timeout=10,
        )

        # post (prematurely) the event in the SELock for f5
        a_lock.owner_wait_q[1].event.set()

        # wait for f5 to tell us it did the release
        mainline_wait_event.wait()
        mainline_wait_event.clear()

        exp_q = [
            LockItem(
                mode=SELockObtainMode.Exclusive,
                event_flag=False,
                thread=f4_thread,
            ),
            LockItem(
                mode=SELockObtainMode.Share,
                event_flag=True,
                thread=f5_thread,
            ),
        ]
        a_lock.verify_lock(
            exp_q=exp_q,
            exp_owner_count=-1,
            exp_excl_wait_count=0,
            verify_structures=False,
        )

        mainline_error_msg = re.escape(
            "lock_verify raising LockVerifyError. owner_count_error=False, "
            "wait_count_error=False, excl_event_flag_error=False, "
            f"share_event_flag_error=True, exp_q={exp_q}, "
            f"lock_info.queue={exp_q}, exp_owner_count=-1, "
            "lock_info.owner_count=-1, exp_excl_wait_count=0, "
            "lock_info.excl_wait_count=0, timeout=None, "
            "calc_owner_count=-1, calc_excl_wait_count=0, "
            "idx_of_first_excl_wait=-1, idx_of_first_excl_event_flag=-1, "
            "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=1."
        )

        log_ver.add_pattern(pattern=mainline_error_msg, level=logging.ERROR)
        with pytest.raises(LockVerifyError, match=mainline_error_msg):
            a_lock.verify_lock(
                exp_q=exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

        # tell f4 and f5 to end - we will leave the lock damaged
        f4_wait_event.set()
        f5_wait_event.set()

        f4_thread.join()
        f5_thread.join()

        # the lock should not have changed, and the lock_verify
        # should provide the same result as above, except that we need
        # to set the exp_q here to get the current status of the threads
        # which are now in a stopped state
        exp_q = [
            LockItem(
                mode=SELockObtainMode.Exclusive,
                event_flag=False,
                thread=f4_thread,
            ),
            LockItem(
                mode=SELockObtainMode.Share,
                event_flag=True,
                thread=f5_thread,
            ),
        ]
        log_ver.add_pattern(pattern=mainline_error_msg, level=logging.ERROR)
        with pytest.raises(LockVerifyError, match=mainline_error_msg):
            a_lock.verify_lock(
                exp_q=exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )


########################################################################
# TestSELockBasic class to test SELock methods
########################################################################
class TestSELockBasic:
    """Class TestSELockBasic."""

    ####################################################################
    # log_test_msg
    ####################################################################
    def log_test_msg(self, log_msg: str) -> None:
        """Issue log msgs for test rtn.

        Args:
            log_msg: the message to log

        """
        logger.debug(log_msg, stacklevel=2)

    ####################################################################
    # repr
    ####################################################################
    def test_se_lock_repr(self) -> None:
        """Test the repr of SELock."""
        a_se_lock = SELock()

        expected_repr_str = "SELock()"

        assert repr(a_se_lock) == expected_repr_str

    ####################################################################
    # repr
    ####################################################################
    def test_se_lock_obtain_excl(self) -> None:
        """Test exclusive lock obtain."""

        self.log_test_msg("mainline entry")

        thread_name = threading.current_thread().name

        a_se_lock = SELock()

        self.log_test_msg("about to do step 1")
        a_se_lock.obtain_excl()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -1
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 2")
        a_se_lock.release()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 0
        assert lock_info.owner_count == 0
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 3")
        a_se_lock.obtain_excl_recursive()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -1
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 4")
        a_se_lock.release()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 0
        assert lock_info.owner_count == 0
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 5")
        a_se_lock.obtain_excl()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -1
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 6")
        a_se_lock.obtain_excl_recursive()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -2
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 7")
        a_se_lock.release()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -1
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 8")
        a_se_lock.release()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 0
        assert lock_info.owner_count == 0
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 9")
        a_se_lock.obtain_excl_recursive()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -1
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 10")
        a_se_lock.obtain_excl_recursive()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -2
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 11")
        a_se_lock.release()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -1
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 12")
        a_se_lock.release()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 0
        assert lock_info.owner_count == 0

        self.log_test_msg("about to do step 13")
        a_se_lock.obtain_excl()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -1
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 14")
        a_se_lock.obtain_excl_recursive()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -2
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 15")
        a_se_lock.obtain_excl_recursive()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -3
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 16")
        a_se_lock.release()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -2
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 17")
        a_se_lock.release()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 1
        assert lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert lock_info.queue[0].thread == thread_name
        assert not lock_info.queue[0].event_flag
        assert lock_info.owner_count == -1
        assert lock_info.excl_wait_count == 0

        self.log_test_msg("about to do step 18")
        a_se_lock.release()
        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 0
        assert lock_info.owner_count == 0

        self.log_test_msg("mainline exit")

    def test_se_lock_release_by_excl_owner(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test release by shared waiter."""

        ################################################################
        # AttemptedReleaseBySharedWaiter
        ################################################################
        def f4() -> None:
            """Function that gets lock exclusive to cause contention."""

            f4_log_msg = (
                re.escape(
                    "SELock granted immediate exclusive control to "
                    f"{f4_thread.name}, "
                )
                + "caller threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f4:[0-9]+"
            )

            log_ver.add_pattern(pattern=f4_log_msg)

            # a_lock.obtain(mode=SELock._Mode.EXCL)
            a_lock.obtain_excl()

            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Exclusive,
                        event_flag=False,
                        thread=f4_thread,
                    ),
                ],
                exp_owner_count=-1,
                exp_excl_wait_count=0,
            )

            mainline_wait_event.set()
            f4_wait_event.wait()

            f4_exp_q = [
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=False,
                    thread=f5_thread,
                ),
            ]

            a_lock.verify_lock(
                exp_q=f4_exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

            f4_log_msg = (
                re.escape(
                    f"Thread {threading.current_thread().name} released SELock, mode "
                    f"EXCL, call sequence: "
                )
                + "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f5:[0-9]+"
            )
            log_ver.add_pattern(pattern=f4_log_msg)

            f4_log_msg = (
                re.escape(f"Thread {f5_thread.name} waiting for SELock, ")
                + "caller threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f5:[0-9]+"
            )
            log_ver.add_pattern(pattern=f4_log_msg)

            a_lock.release()

            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Share,
                        event_flag=True,
                        thread=f5_thread,
                    )
                ],
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

            # tell mainline we are done
            mainline_wait_event.set()

        def f5() -> None:
            """Function that tries to release lock while waiting."""

            f5_log_msg = (
                re.escape(f"Thread {f5_thread.name} waiting for SELock, ")
                + "caller threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f5:[0-9]+"
            )
            log_ver.add_pattern(pattern=f5_log_msg)

            # a_lock.obtain(mode=SELock._Mode.SHARE)
            a_lock.obtain_share()

            # we have been woken normally
            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Share,
                        event_flag=True,
                        thread=f5_thread,
                    )
                ],
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

            f5_wait_event.wait()

            a_lock.release()

            a_lock.verify_lock(
                exp_q=[],
                exp_owner_count=0,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

            # tell mainline we are done
            mainline_wait_event.set()

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        a_lock = SELock()

        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
        )

        mainline_wait_event = threading.Event()
        f4_wait_event = threading.Event()
        f5_wait_event = threading.Event()
        f4_thread = threading.Thread(target=f4)
        f5_thread = threading.Thread(target=f5)

        # start f4 to get the lock exclusive
        f4_thread.start()

        # wait for f4 to tell us it has the lock
        mainline_wait_event.wait()
        mainline_wait_event.clear()

        # verify lock
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
        )

        # start f5 to queue up for the lock behind f4
        f5_thread.start()

        # loop 10 secs until verify_lock sees both locks in the queue
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=False,
                    thread=f5_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
            timeout=10,
        )

        # post f4 to release the excl lock
        f4_wait_event.set()

        # wait for f4 to tell us it did the release
        mainline_wait_event.wait()
        mainline_wait_event.clear()

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=True,
                    thread=f5_thread,
                )
            ],
            exp_owner_count=1,
            exp_excl_wait_count=0,
            verify_structures=True,
        )

        # tell f5 to release the lock
        f5_wait_event.set()

        # wait for f5 to tell us the lock is released
        mainline_wait_event.wait()

        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
            verify_structures=True,
        )

        f4_thread.join()
        f5_thread.join()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)


########################################################################
# TestSELock class
########################################################################
class TestSELock:
    """Class TestSELock."""

    ####################################################################
    # test_se_lock_timeout
    ####################################################################
    @pytest.mark.parametrize(
        "timeout_arg",
        [0.1, 0.5, 12],
    )
    @pytest.mark.parametrize(
        "use_timeout_arg",
        [True, False],
    )
    @pytest.mark.parametrize(
        "ml_context_arg",
        [
            ContextArg.NoContext,
            ContextArg.ContextExclShare,
            ContextArg.ContextObtain,
        ],
    )
    @pytest.mark.parametrize(
        "f1_context_arg",
        [
            ContextArg.NoContext,
            ContextArg.ContextExclShare,
            ContextArg.ContextObtain,
        ],
    )
    def test_se_lock_timeout(
        self,
        timeout_arg: float,
        use_timeout_arg: int,
        ml_context_arg: ContextArg,
        f1_context_arg: ContextArg,
    ) -> None:
        """Method to test se_lock timeout cases.

        Args:
            timeout_arg: number of seconds to use for timeout value
            use_timeout_arg: indicates whether to use timeout
            ml_context_arg: specifies how mainline obtains the lock
            f1_context_arg: specifies how f1 obtains the lock

        """

        def f1(use_timeout_tf: bool, f1_context: ContextArg) -> None:
            """Function to get the lock and wait.

            Args:
                use_timeout_tf: indicates whether to specify timeout
                                  on the lock requests
                f1_context: specifies how f1 obtains the lock

            """
            logger.debug("f1 entered")

            ############################################################
            # Excl mode
            ############################################################
            obtaining_log_msg = f"f1 obtaining excl {f1_context=} " f"{use_timeout_tf=}"
            obtained_log_msg = f"f1 obtained excl {f1_context=} " f"{use_timeout_tf=}"
            if f1_context == ContextArg.NoContext:
                if use_timeout_tf:
                    logger.debug(obtaining_log_msg)
                    a_lock.obtain_excl(timeout=timeout_arg)
                    logger.debug(obtained_log_msg)
                else:
                    logger.debug(obtaining_log_msg)
                    a_lock.obtain_excl()
                    logger.debug(obtained_log_msg)

                msgs.queue_msg("alpha")
                msgs.get_msg("beta", timeout=msgs_get_to)

                a_lock.release()

            elif f1_context == ContextArg.ContextExclShare:
                if use_timeout_tf:
                    logger.debug(obtaining_log_msg)
                    with SELockExcl(a_lock, timeout=timeout_arg):
                        logger.debug(obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
                else:
                    logger.debug(obtaining_log_msg)
                    with SELockExcl(a_lock):
                        logger.debug(obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
            else:
                if use_timeout_tf:
                    logger.debug(obtaining_log_msg)
                    with SELockObtain(
                        a_lock,
                        obtain_mode=SELockObtainMode.Exclusive,
                        timeout=timeout_arg,
                    ):
                        logger.debug(obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
                else:
                    logger.debug(obtaining_log_msg)
                    with SELockObtain(a_lock, obtain_mode=SELockObtainMode.Exclusive):
                        logger.debug(obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)

            ############################################################
            # Share mode
            ############################################################
            obtaining_log_msg = (
                f"f1 obtaining share {f1_context=} " f"{use_timeout_tf=}"
            )
            obtained_log_msg = f"f1 obtained share {f1_context=} {use_timeout_tf=}"
            if f1_context == ContextArg.NoContext:
                if use_timeout_tf:
                    logger.debug(obtaining_log_msg)
                    a_lock.obtain_share(timeout=timeout_arg)
                    logger.debug(obtained_log_msg)
                else:
                    logger.debug(obtaining_log_msg)
                    a_lock.obtain_share()
                    logger.debug(obtained_log_msg)

                msgs.queue_msg("alpha")
                msgs.get_msg("beta", timeout=msgs_get_to)

                # a_lock.release()  @sbt why no release?

            elif f1_context == ContextArg.ContextExclShare:
                if use_timeout_tf:
                    logger.debug(obtaining_log_msg)
                    with SELockShare(a_lock, timeout=timeout_arg):
                        logger.debug(obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
                else:
                    logger.debug(obtaining_log_msg)
                    with SELockShare(a_lock):
                        logger.debug(obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
            else:
                if use_timeout_tf:
                    logger.debug(obtaining_log_msg)
                    with SELockObtain(
                        a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
                    ):
                        logger.debug(obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
                else:
                    logger.debug(obtaining_log_msg)
                    with SELockObtain(a_lock, obtain_mode=SELockObtainMode.Share):
                        logger.debug(obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)

            logger.debug("f1 exiting")

        ################################################################
        # Mainline
        ################################################################
        logger.debug("mainline entered")

        msgs = Msgs()
        stop_watch = StopWatch()

        a_lock = SELock()

        to_low = timeout_arg
        to_high = timeout_arg * 1.2

        msgs_get_to = timeout_arg * 4 * 2

        f1_thread = threading.Thread(target=f1, args=(use_timeout_arg, f1_context_arg))
        f1_thread.start()

        logger.debug("mainline about to wait 1")
        msgs.get_msg("alpha")

        logger.debug("mainline about to request excl 1")

        stop_watch.start_clock(clock_iter=1)
        with pytest.raises(SELockObtainTimeout):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_excl(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockExcl(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Exclusive, timeout=timeout_arg
                ):
                    pass

        assert to_low <= stop_watch.duration() <= to_high

        logger.debug("mainline about to request share 1")
        stop_watch.start_clock(clock_iter=2)
        with pytest.raises(SELockObtainTimeout):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_share(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockShare(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        logger.debug("mainline about to request excl 2")
        stop_watch.start_clock(clock_iter=3)
        with pytest.raises(SELockObtainTimeout):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_excl(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockExcl(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Exclusive, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        logger.debug("mainline about to request share 2")
        stop_watch.start_clock(clock_iter=4)
        with pytest.raises(SELockObtainTimeout):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_share(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockShare(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        msgs.queue_msg("beta")

        logger.debug("mainline about to wait 2")
        msgs.get_msg("alpha")

        logger.debug("mainline about to request excl 3")
        stop_watch.start_clock(clock_iter=5)
        with pytest.raises(SELockObtainTimeout):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_excl(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockExcl(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Exclusive, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        logger.debug("mainline about to request share 3")
        if ml_context_arg == ContextArg.NoContext:
            a_lock.obtain_share(timeout=timeout_arg)
            a_lock.release()
        elif ml_context_arg == ContextArg.ContextExclShare:
            with SELockShare(a_lock, timeout=timeout_arg):
                pass
        else:
            with SELockObtain(
                a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
            ):
                pass

        logger.debug("mainline about to request excl 4")
        stop_watch.start_clock(clock_iter=6)
        with pytest.raises(SELockObtainTimeout):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_excl(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockExcl(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Exclusive, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        logger.debug("mainline about to request share 4")
        if ml_context_arg == ContextArg.NoContext:
            a_lock.obtain_share(timeout=timeout_arg)
            a_lock.release()
        elif ml_context_arg == ContextArg.ContextExclShare:
            with SELockShare(a_lock, timeout=timeout_arg):
                pass
        else:
            with SELockObtain(
                a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
            ):
                pass

        msgs.queue_msg("beta")
        f1_thread.join()
        logger.debug("mainline exiting")

    ####################################################################
    # test_se_lock_combos
    ####################################################################
    def test_se_lock_combos(
        self,
        num_share_requests1_arg: int,
        num_excl_requests1_arg: int,
        num_share_requests2_arg: int,
        num_excl_requests2_arg: int,
        release_position_arg: int,
        use_context_arg: int,
    ) -> None:
        """Method to test se_lock excl and share combos.

        The following section tests various scenarios of shared and
        exclusive locking.

        We will try combinations of shared and exclusive obtains and
        verify that the order in requests is maintained.

        Scenario:
           1) obtain 0 to 3 shared - verify
           2) obtain 0 to 3 exclusive - verify
           3) obtain 0 to 3 shared - verify
           4) obtain 0 to 3 exclusive - verify

        Args:
            num_share_requests1_arg: number of first share requests
            num_excl_requests1_arg: number of first excl requests
            num_share_requests2_arg: number of second share requests
            num_excl_requests2_arg: number of second excl requests
            release_position_arg: indicates the position among the lock
                                    owners that will release the lock
            use_context_arg: indicate whether to use context manager
                               to request the lock

        """
        num_groups = 4

        def f1(
            a_event: threading.Event,
            mode: SELock._Mode,
            req_num: int,
            # use_context_tf: bool
            use_context: ContextArg,
        ) -> None:
            """Function to get the lock and wait.

            Args:
                a_event: instance of threading.Event
                mode: shared or exclusive
                req_num: request number assigned
                use_context: indicate whether to use context manager
                    lock obtain or to make the call directly

            """

            def f1_verify() -> None:
                """Verify the thread item contains expected info."""
                for f1_item in thread_event_list:
                    if f1_item.req_num == req_num:
                        assert f1_item.thread is threading.current_thread()
                        assert f1_item.mode == mode
                        assert f1_item.lock_obtained is False
                        f1_item.lock_obtained = True
                        break

            if use_context == ContextArg.NoContext:
                if mode == SELock._Mode.SHARE:
                    a_lock.obtain_share()
                else:
                    a_lock.obtain_excl()
                f1_verify()

                a_event.wait()
                a_lock.release()

            elif use_context == ContextArg.ContextExclShare:
                if mode == SELock._Mode.SHARE:
                    with SELockShare(a_lock):
                        f1_verify()
                        a_event.wait()
                else:
                    with SELockExcl(a_lock):
                        f1_verify()
                        a_event.wait()

            else:
                if mode == SELock._Mode.SHARE:
                    with SELockObtain(a_lock, obtain_mode=SELockObtainMode.Share):
                        f1_verify()
                        a_event.wait()
                else:
                    with SELockObtain(a_lock, obtain_mode=SELockObtainMode.Exclusive):
                        f1_verify()
                        a_event.wait()

        @dataclass
        class ThreadEvent:
            thread: threading.Thread
            event: threading.Event
            mode: SELock._Mode
            req_num: int
            lock_obtained: bool

        a_lock = SELock()

        thread_event_list = []

        request_number = -1
        num_requests_list = [
            num_share_requests1_arg,
            num_excl_requests1_arg,
            num_share_requests2_arg,
            num_excl_requests2_arg,
        ]

        num_initial_owners = 0
        initial_owner_mode: Optional[SELock._Mode] = None
        if num_share_requests1_arg:
            num_initial_owners = num_share_requests1_arg
            initial_owner_mode = SELock._Mode.SHARE
            if num_excl_requests1_arg == 0:
                num_initial_owners += num_share_requests2_arg
        elif num_excl_requests1_arg:
            num_initial_owners = 1
            initial_owner_mode = SELock._Mode.EXCL
        elif num_share_requests2_arg:
            num_initial_owners = num_share_requests2_arg
            initial_owner_mode = SELock._Mode.SHARE
        elif num_excl_requests2_arg:
            num_initial_owners = 1
            initial_owner_mode = SELock._Mode.EXCL

        for shr_excl in range(num_groups):
            num_requests = num_requests_list[shr_excl]
            for idx in range(num_requests):
                request_number += 1
                a_event1 = threading.Event()
                if shr_excl == 0 or shr_excl == 2:
                    req_mode = SELock._Mode.SHARE
                else:
                    req_mode = SELock._Mode.EXCL

                if use_context_arg == 0:
                    # use_context = False
                    use_context = ContextArg.NoContext
                elif use_context_arg == 1:
                    # use_context = True
                    use_context = ContextArg.ContextExclShare
                elif use_context_arg == 2:
                    use_context = ContextArg.ContextObtain
                else:
                    if request_number % 3 == 0:
                        # use_context = False
                        use_context = ContextArg.NoContext
                    elif request_number % 3 == 1:
                        # use_context = True
                        use_context = ContextArg.ContextExclShare
                    else:
                        use_context = ContextArg.ContextObtain

                a_thread = threading.Thread(
                    target=f1, args=(a_event1, req_mode, request_number, use_context)
                )
                # save for verification and release
                thread_event_list.append(
                    ThreadEvent(
                        thread=a_thread,
                        event=a_event1,
                        mode=req_mode,
                        req_num=request_number,
                        lock_obtained=False,
                    )
                )

                a_thread.start()

                # make sure the request has been queued
                while (not a_lock.owner_wait_q) or (
                    not a_lock.owner_wait_q[-1].thread is a_thread
                ):
                    time.sleep(0.1)
                # logger.debug(f'shr_excl = {shr_excl}, '
                #              f'idx = {idx}, '
                #              f'num_requests_made = {request_number}, '
                #              f'len(a_lock) = {len(a_lock)}')
                assert len(a_lock) == request_number + 1

                # verify
                assert a_lock.owner_wait_q[-1].thread is a_thread
                assert not a_lock.owner_wait_q[-1].event.is_set()

        work_shr1 = num_share_requests1_arg
        work_excl1 = num_excl_requests1_arg
        work_shr2 = num_share_requests2_arg
        work_excl2 = num_excl_requests2_arg
        while thread_event_list:
            exp_num_owners = 0
            if work_shr1:
                exp_num_owners = work_shr1
                if work_excl1 == 0:
                    exp_num_owners += work_shr2
            elif work_excl1:
                exp_num_owners = 1
            elif work_shr2:
                exp_num_owners = work_shr2
            elif work_excl2:
                exp_num_owners = 1

            while True:
                exp_num_owners_found = 0
                for idx in range(exp_num_owners):  # wait for next owners
                    if thread_event_list[idx].lock_obtained:
                        exp_num_owners_found += 1
                    else:
                        break
                if exp_num_owners_found == exp_num_owners:
                    break
                time.sleep(0.0001)

            for idx, thread_event in enumerate(thread_event_list):
                assert thread_event.thread == thread_event_list[idx].thread
                assert thread_event.thread == a_lock.owner_wait_q[idx].thread
                assert thread_event.mode == thread_event_list[idx].mode
                assert thread_event.mode == a_lock.owner_wait_q[idx].mode

                if idx + 1 <= num_initial_owners:
                    # we expect the event to not have been posted
                    assert not a_lock.owner_wait_q[idx].event.is_set()
                    assert thread_event.mode == initial_owner_mode
                    assert thread_event.lock_obtained is True
                elif idx + 1 <= exp_num_owners:
                    assert a_lock.owner_wait_q[idx].event.is_set()
                    assert thread_event.lock_obtained is True
                else:
                    assert not a_lock.owner_wait_q[idx].event.is_set()
                    assert thread_event.lock_obtained is False

            release_position = min(release_position_arg, exp_num_owners - 1)
            thread_event = thread_event_list.pop(release_position)

            thread_event.event.set()  # tell owner to release and return
            thread_event.thread.join()  # ensure release is complete
            num_initial_owners -= 1
            request_number -= 1
            if work_shr1:
                work_shr1 -= 1
            elif work_excl1:
                work_excl1 -= 1
            elif work_shr2:
                work_shr2 -= 1
            elif work_excl2:
                work_excl2 -= 1

            assert len(a_lock) == request_number + 1


########################################################################
# TestSELockDocstrings class
########################################################################
class TestSELockDocstrings:
    """Class TestSELockDocstrings."""

    def test_se_lock_with_example_1(self) -> None:
        """Method test_se_lock_with_example_1."""
        flowers("Example of SELock for README:")

        from scottbrian_locking.se_lock import SELock, SELockShare, SELockExcl

        a_lock = SELock()
        # Get lock in exclusive mode
        with SELockExcl(a_lock):  # write to a
            a = 1
            print(f"under exclusive lock, a = {a}")
        # Get lock in shared mode
        with SELockShare(a_lock):  # read a
            print(f"under shared lock, a = {a}")
